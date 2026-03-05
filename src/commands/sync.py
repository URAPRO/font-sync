"""syncコマンドの実装

同期元フォルダから新しいフォントを同期するコマンドです。
複数ソース (sources[]) に対応しています。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from ..config import ConfigManager
from ..font_manager import FontManager
from ..main import handle_errors
from ..parallel import ParallelProcessor
from ..utils import batch_process, check_disk_space

console = Console()


def _output_json(
    success: bool,
    added: int = 0,
    updated: int = 0,
    skipped: int = 0,
    errors: list = None,
    sources: list = None,
) -> None:
    """JSON形式で結果を出力"""
    result = {
        "success": success,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "errors": errors or [],
        "sources": sources or [],
    }
    print(json.dumps(result, ensure_ascii=False))


def _sync_source(
    source: Dict[str, Any],
    config_manager: ConfigManager,
    font_manager: FontManager,
    json_output: bool,
) -> Dict[str, Any]:
    """1つのソースに対して同期処理を実行し、結果を返す

    Args:
        source: ソース情報 (id, label, path, enabled)
        config_manager: ConfigManager インスタンス
        font_manager: FontManager インスタンス
        json_output: JSON出力モードかどうか

    Returns:
        Dict: {source_id, added, updated, skipped, errors}
    """
    source_id = source["id"]
    source_label = source.get("label", source_id)
    sync_folder = source["path"]

    added_count = 0
    updated_count = 0
    skipped_count = 0
    errors: List[str] = []

    if not json_output:
        console.print(f"\n[bold]ソース:[/bold] [cyan]{source_label}[/cyan] ({sync_folder})")

    # フォントのスキャン
    all_source_fonts = []

    if json_output:
        try:
            for font_batch in font_manager.scan_fonts(sync_folder, yield_batch=True):
                all_source_fonts.extend(font_batch)
        except Exception as e:
            return {
                "source_id": source_id,
                "added": 0,
                "updated": 0,
                "skipped": 0,
                "errors": [f"フォントのスキャンに失敗しました: {e}"],
            }
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            scan_task = progress.add_task("フォントをスキャン中...", total=None)
            try:
                for font_batch in font_manager.scan_fonts(sync_folder, yield_batch=True):
                    all_source_fonts.extend(font_batch)
                    progress.update(
                        scan_task,
                        description=f"フォントをスキャン中... ({len(all_source_fonts)}個)",
                    )
            except Exception as e:
                console.print(f"[red]エラー: フォントのスキャンに失敗しました: {e}[/red]")
                return {
                    "source_id": source_id,
                    "added": 0,
                    "updated": 0,
                    "skipped": 0,
                    "errors": [f"フォントのスキャンに失敗しました: {e}"],
                }
            progress.update(scan_task, completed=True)

    if not all_source_fonts:
        if not json_output:
            console.print("[yellow]同期元フォルダにフォントファイルが見つかりませんでした。[/yellow]")
        return {
            "source_id": source_id,
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [],
        }

    if not json_output:
        console.print(f"[blue]ℹ {len(all_source_fonts)}個のフォントファイルが見つかりました。[/blue]")

    # 差分チェック
    fonts_to_sync = []
    fonts_to_update = []
    fonts_up_to_date = []
    total_size_mb = 0.0
    installed_fonts = config_manager.get_installed_fonts()
    use_parallel = len(all_source_fonts) > 50

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        diff_task = progress.add_task("差分を確認中...", total=len(all_source_fonts))

        if use_parallel and not json_output:
            parallel = ParallelProcessor()

            def progress_callback(completed: int, total: int):
                progress.update(diff_task, completed=completed)

            hash_results = parallel.calculate_hashes_parallel(
                all_source_fonts, font_manager.calculate_hash, progress_callback
            )
            for font_path in all_source_fonts:
                font_name = font_path.name
                info = font_manager.get_font_info(font_path)
                size_mb = info["size_mb"]
                if info.get("is_locked") or info.get("is_syncing"):
                    continue
                font_hash = hash_results.get(font_path)
                if font_hash is None:
                    continue
                if font_name not in installed_fonts:
                    fonts_to_sync.append((font_path, font_hash))
                    total_size_mb += size_mb
                elif installed_fonts[font_name].get("hash") != font_hash:
                    fonts_to_update.append((font_path, font_hash))
                    total_size_mb += size_mb
                else:
                    fonts_up_to_date.append(font_path)
        else:
            def check_font_diff(font_path: Path) -> Dict:
                font_name = font_path.name
                result = {"path": font_path, "action": "none", "hash": None, "size_mb": 0}
                try:
                    info = font_manager.get_font_info(font_path)
                    result["size_mb"] = info["size_mb"]
                    if info.get("is_locked") or info.get("is_syncing"):
                        return result
                    font_hash = font_manager.calculate_hash(font_path)
                    result["hash"] = font_hash
                    if font_name not in installed_fonts:
                        result["action"] = "install"
                    elif installed_fonts[font_name].get("hash") != font_hash:
                        result["action"] = "update"
                    else:
                        result["action"] = "up-to-date"
                except Exception as e:
                    if not json_output:
                        console.print(f"[red]エラー: {font_name} の処理中にエラーが発生しました: {e}[/red]")
                progress.update(diff_task, advance=1)
                return result

            results = batch_process(all_source_fonts, check_font_diff, batch_size=50)
            for result in results:
                if isinstance(result, dict) and not result.get("error"):
                    if result["action"] == "install":
                        fonts_to_sync.append((result["path"], result["hash"]))
                        total_size_mb += result["size_mb"]
                    elif result["action"] == "update":
                        fonts_to_update.append((result["path"], result["hash"]))
                        total_size_mb += result["size_mb"]
                    elif result["action"] == "up-to-date":
                        fonts_up_to_date.append(result["path"])

    total_to_sync = len(fonts_to_sync) + len(fonts_to_update)
    skipped_count = len(fonts_up_to_date)

    if total_to_sync == 0:
        if not json_output:
            console.print("[green]✓ すべてのフォントは最新です。[/green]")
        return {
            "source_id": source_id,
            "added": 0,
            "updated": 0,
            "skipped": skipped_count,
            "errors": [],
        }

    # ディスク容量チェック
    disk_info = check_disk_space(Path.home() / "Library" / "Fonts", total_size_mb * 1.1)
    if not disk_info["has_enough_space"]:
        err = f"ディスク容量が不足しています。必要: {total_size_mb:.1f}MB, 空き: {disk_info['free_mb']:.1f}MB"
        if not json_output:
            console.print(f"[red]エラー: {err}[/red]")
        return {
            "source_id": source_id,
            "added": 0,
            "updated": 0,
            "skipped": skipped_count,
            "errors": [err],
        }

    # 同期実行
    if not json_output:
        console.print(f"[bold]{total_to_sync}個のフォント（合計 {total_size_mb:.1f}MB）を同期します。[/bold]")

    def install_font(font_path, font_hash):
        nonlocal added_count, updated_count
        font_name = font_path.name
        try:
            font_manager.copy_font(font_path, validate=True)
            config_manager.add_installed_font(font_name, font_hash)
            return True
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "hint") and e.hint:
                error_msg += f" ({e.hint})"
            errors.append(f"{font_name}: {error_msg}")
            return False

    if json_output:
        for font_path, font_hash in fonts_to_sync:
            if install_font(font_path, font_hash):
                added_count += 1
        for font_path, font_hash in fonts_to_update:
            if install_font(font_path, font_hash):
                updated_count += 1
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            sync_task = progress.add_task("フォントを同期中...", total=total_to_sync)
            for font_path, font_hash in fonts_to_sync:
                progress.update(sync_task, description=f"インストール中: {font_path.name}")
                if install_font(font_path, font_hash):
                    added_count += 1
                progress.update(sync_task, advance=1)
            for font_path, font_hash in fonts_to_update:
                progress.update(sync_task, description=f"更新中: {font_path.name}")
                if install_font(font_path, font_hash):
                    updated_count += 1
                progress.update(sync_task, advance=1)

    return {
        "source_id": source_id,
        "added": added_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "errors": errors,
    }


@handle_errors
def sync_command(json_output: bool = False, source_id: Optional[str] = None) -> None:
    """フォントの同期を実行

    Args:
        json_output: JSON形式で出力するかどうか
        source_id: 特定ソースのみ同期する場合のソースID (None = 全ソース)
    """
    config_manager = ConfigManager()
    font_manager = FontManager()

    if not config_manager.config_exists():
        if json_output:
            _output_json(False, errors=["設定ファイルが見つかりません。'font-sync init' で初期設定を行ってください。"])
            raise typer.Exit(1)
        console.print("[red]エラー: 設定ファイルが見つかりません。[/red]")
        console.print("[yellow]ヒント: 'font-sync init' で初期設定を行ってください。[/yellow]")
        raise typer.Exit(1)

    try:
        config_manager.load_config()
    except Exception as e:
        if json_output:
            _output_json(False, errors=[f"設定ファイルの読み込みに失敗しました: {e}"])
            raise typer.Exit(1)
        console.print(f"[red]エラー: 設定ファイルの読み込みに失敗しました: {e}[/red]")
        raise typer.Exit(1)

    # ソース一覧を取得
    enabled_sources = config_manager.get_enabled_sources()

    # --source オプションで絞り込み
    if source_id is not None:
        all_sources = config_manager.get_sources()
        matched = [s for s in all_sources if s["id"] == source_id]
        if not matched:
            if json_output:
                _output_json(False, errors=[f"指定されたソースが見つかりません: {source_id}"])
                raise typer.Exit(1)
            console.print(f"[red]エラー: 指定されたソースが見つかりません: {source_id}[/red]")
            raise typer.Exit(1)
        enabled_sources = matched

    if not enabled_sources:
        if json_output:
            _output_json(True, sources=[])
            raise typer.Exit(0)
        console.print("[yellow]有効な同期元ソースがありません。[/yellow]")
        raise typer.Exit(0)

    if not json_output:
        console.print(f"[bold]{len(enabled_sources)}個のソースを同期します。[/bold]")

    # 各ソースを同期
    source_results = []
    total_added = 0
    total_updated = 0
    total_skipped = 0
    all_errors: List[str] = []

    for source in enabled_sources:
        result = _sync_source(source, config_manager, font_manager, json_output)
        source_results.append(result)
        total_added += result["added"]
        total_updated += result["updated"]
        total_skipped += result["skipped"]
        all_errors.extend(result.get("errors", []))

    # 設定を保存
    try:
        config_manager.save_config()
    except Exception as e:
        if not json_output:
            console.print(f"[red]警告: 設定の保存に失敗しました: {e}[/red]")
        all_errors.append(f"設定の保存に失敗: {e}")

    if json_output:
        _output_json(
            success=len(all_errors) == 0,
            added=total_added,
            updated=total_updated,
            skipped=total_skipped,
            errors=all_errors,
            sources=source_results,
        )
    else:
        console.print()
        success_count = total_added + total_updated
        if success_count > 0:
            console.print(f"[green]✓ {success_count}個のフォントを正常に同期しました。[/green]")
        if all_errors:
            console.print(f"[red]✗ {len(all_errors)}個のエラーが発生しました。[/red]")
            for error in all_errors[:10]:
                console.print(f"  - {error}")
        console.print(f"\n[dim]同期完了: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
