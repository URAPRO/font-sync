"""adoptコマンドの実装

~/Library/Fonts/ 内フォントを同期元フォルダに逆同期（取り込み）します。
システムフォント・Adobe Fonts は realpath チェックで除外します。
"""

import json
import os
import shutil
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from ..config import ConfigManager
from ..font_manager import FontManager
from ..main import handle_errors

console = Console()

# 除外対象のパスプレフィックス
_EXCLUDED_PREFIXES = (
    "/System/Library/Fonts/",
    "/Library/Fonts/",
)

# Adobe CoreSync のパス断片
_ADOBE_CORYSYNC_MARKERS = ("Adobe/CoreSync", "Adobe CoreSync")


def _is_excluded(font_path: Path) -> bool:
    """フォントがシステム/Adobe フォントかどうかを判定

    シンボリックリンクの realpath を確認し、
    /System/Library/Fonts/ や /Library/Fonts/、Adobe CoreSync を指す場合は除外。

    Args:
        font_path: フォントファイルのパス

    Returns:
        True → 除外対象（システム/Adobe フォント）
    """
    try:
        real = os.path.realpath(font_path)
    except Exception:
        return False

    for prefix in _EXCLUDED_PREFIXES:
        if real.startswith(prefix):
            return True

    for marker in _ADOBE_CORYSYNC_MARKERS:
        if marker in real:
            return True

    return False


def _output_adopt_json(
    success: bool,
    adopted: int = 0,
    skipped: int = 0,
    errors: list = None,
    fonts: list = None,
) -> None:
    """JSON形式でadopt結果を出力"""
    result = {
        "success": success,
        "adopted": adopted,
        "skipped": skipped,
        "errors": errors or [],
        "fonts": fonts or [],
    }
    print(json.dumps(result, ensure_ascii=False))


@handle_errors
def adopt_command(
    source_id: Optional[str] = None,
    dry_run: bool = False,
    json_output: bool = False,
    move: bool = False,
    yes: bool = False,
) -> None:
    """~/Library/Fonts/ 内フォントを同期元フォルダに取り込む

    Args:
        source_id: 対象ソースの ID（None の場合は自動選択または選択プロンプト）
        dry_run: True の場合はファイル操作を行わず対象を表示するのみ
        json_output: True の場合は JSON 形式で出力
        move: True の場合はコピーではなく移動
        yes: True の場合は --move の確認プロンプトをスキップ
    """
    config_manager = ConfigManager()
    font_manager = FontManager(use_cache=False)

    # 設定ファイル確認
    if not config_manager.config_exists():
        if json_output:
            _output_adopt_json(
                False,
                errors=["設定ファイルが見つかりません。'font-sync init' で初期設定を行ってください。"],
            )
            raise typer.Exit(1)
        console.print("[red]エラー: 設定ファイルが見つかりません。[/red]")
        console.print("[yellow]ヒント: 'font-sync init' で初期設定を行ってください。[/yellow]")
        raise typer.Exit(1)

    try:
        config_manager.load_config()
    except Exception as e:
        if json_output:
            _output_adopt_json(False, errors=[f"設定ファイルの読み込みに失敗しました: {e}"])
            raise typer.Exit(1)
        console.print(f"[red]エラー: 設定ファイルの読み込みに失敗しました: {e}[/red]")
        raise typer.Exit(1)

    # ターゲットソースを特定
    all_sources = config_manager.get_sources()

    if source_id is not None:
        matched = [s for s in all_sources if s["id"] == source_id]
        if not matched:
            if json_output:
                _output_adopt_json(False, errors=[f"指定されたソースが見つかりません: {source_id}"])
                raise typer.Exit(1)
            console.print(f"[red]エラー: 指定されたソースが見つかりません: {source_id}[/red]")
            raise typer.Exit(1)
        target_source = matched[0]
    else:
        if len(all_sources) == 0:
            if json_output:
                _output_adopt_json(False, errors=["同期元ソースが設定されていません。"])
                raise typer.Exit(1)
            console.print("[red]エラー: 同期元ソースが設定されていません。[/red]")
            raise typer.Exit(1)
        elif len(all_sources) == 1:
            target_source = all_sources[0]
        else:
            # 複数ソース → エラー（一覧表示）
            if json_output:
                _output_adopt_json(
                    False,
                    errors=["--source オプションでソースIDを指定してください。"],
                )
                raise typer.Exit(1)
            console.print("[red]エラー: 複数のソースがあります。--source オプションでソースIDを指定してください。[/red]")
            console.print("[bold]利用可能なソース:[/bold]")
            for s in all_sources:
                console.print(f"  [cyan]{s['id']}[/cyan]  {s.get('label', '')}  ({s['path']})")
            raise typer.Exit(1)

    source_folder = Path(target_source["path"])

    if not source_folder.exists():
        if json_output:
            _output_adopt_json(False, errors=[f"ソースフォルダが存在しません: {source_folder}"])
            raise typer.Exit(1)
        console.print(f"[red]エラー: ソースフォルダが存在しません: {source_folder}[/red]")
        raise typer.Exit(1)

    # --move --json の場合は --yes が必須
    if move and json_output and not yes:
        _output_adopt_json(
            False,
            errors=["--move --json の組み合わせでは --yes が必要です。"],
        )
        raise typer.Exit(1)

    # ~/Library/Fonts/ 内のフォントを収集
    user_font_dir = font_manager.font_install_dir

    if not user_font_dir.exists():
        if json_output:
            _output_adopt_json(True, adopted=0, skipped=0)
        else:
            console.print("[yellow]~/Library/Fonts/ が存在しません。[/yellow]")
        return

    candidate_fonts: List[Path] = []
    for font_path in sorted(user_font_dir.iterdir()):
        if font_path.suffix.lower() in (".otf", ".ttf") and not font_path.name.startswith("."):
            candidate_fonts.append(font_path)

    # ソースフォルダ内の既存ファイル名を取得（dedup 用）
    existing_in_source = {p.name for p in source_folder.iterdir() if p.is_file()}

    # フィルタリング
    to_adopt: List[Path] = []
    skipped_entries: List[dict] = []

    for font_path in candidate_fonts:
        # システム/Adobe フォント除外
        if _is_excluded(font_path):
            skipped_entries.append({"name": font_path.name, "action": "skipped", "reason": "system/adobe"})
            continue

        # 同名ファイルが既にソースにある場合はスキップ
        if font_path.name in existing_in_source:
            skipped_entries.append({"name": font_path.name, "action": "skipped", "reason": "already_exists"})
            continue

        to_adopt.append(font_path)

    if not json_output:
        console.print(f"[bold]{len(to_adopt)}個のフォントを取り込み対象として検出しました。[/bold]")

    # dry-run モード
    if dry_run:
        action_word = "would_move" if move else "would_copy"
        fonts_output = [{"name": f.name, "action": action_word} for f in to_adopt]
        fonts_output += [{"name": s["name"], "action": "skipped"} for s in skipped_entries]

        if json_output:
            _output_adopt_json(
                True,
                adopted=0,
                skipped=len(skipped_entries),
                fonts=fonts_output,
            )
        else:
            console.print("[yellow]--dry-run モード: 実際のファイル操作は行いません[/yellow]")
            for f in to_adopt:
                label = "移動" if move else "コピー"
                console.print(f"  {label}: {f.name}")
        return

    # --move の確認プロンプト（--json モード以外 + --yes なし）
    if move and not yes:
        console.print(
            f"[yellow]警告: {len(to_adopt)}個のフォントを ~/Library/Fonts/ から削除して[/yellow]"
        )
        console.print(f"[yellow]{source_folder} に移動します。[/yellow]")
        if not typer.confirm("続行しますか？", default=False):
            console.print("[yellow]キャンセルしました。[/yellow]")
            return

    # 実行
    adopted_count = 0
    error_list: List[str] = []
    fonts_result: List[dict] = []

    for font_path in to_adopt:
        dest = source_folder / font_path.name
        try:
            if move:
                shutil.move(str(font_path), str(dest))
                action = "moved"
            else:
                shutil.copy2(str(font_path), str(dest))
                action = "copied"
            adopted_count += 1
            fonts_result.append({"name": font_path.name, "action": action})
        except Exception as e:
            error_msg = f"{font_path.name}: {e}"
            error_list.append(error_msg)
            fonts_result.append({"name": font_path.name, "action": "error"})
            if not json_output:
                console.print(f"[red]エラー: {error_msg}[/red]")

    if json_output:
        _output_adopt_json(
            success=len(error_list) == 0,
            adopted=adopted_count,
            skipped=len(skipped_entries),
            errors=error_list,
            fonts=fonts_result,
        )
    else:
        if adopted_count > 0:
            label = "移動" if move else "コピー"
            console.print(f"[green]✓ {adopted_count}個のフォントを{label}しました。[/green]")
        if error_list:
            console.print(f"[red]✗ {len(error_list)}個のエラーが発生しました。[/red]")
            for err in error_list[:10]:
                console.print(f"  - {err}")
