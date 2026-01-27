"""listコマンドの実装

同期元フォルダ内のフォント一覧を表示するコマンドです。
"""

import json
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..config import ConfigManager
from ..font_manager import FontManager
from ..main import handle_errors

console = Console()


@handle_errors
def list_command(status: Optional[str], format: Optional[str]) -> None:
    """フォント一覧を表示

    Args:
        status (Optional[str]): フィルタリングオプション (all, installed, not-installed)
        format (Optional[str]): 出力形式 (table, json)
    """
    config_manager = ConfigManager()
    font_manager = FontManager()

    # 設定ファイルの確認
    if not config_manager.config_exists():
        console.print("[red]エラー: 設定ファイルが見つかりません。[/red]")
        console.print("[yellow]ヒント: 'font-sync init' で初期設定を行ってください。[/yellow]")
        raise typer.Exit(1)

    # 設定を読み込む
    try:
        config = config_manager.load_config()
    except Exception as e:
        console.print(f"[red]エラー: 設定ファイルの読み込みに失敗しました: {e}[/red]")
        raise typer.Exit(1)

    sync_folder = config.get("sync_folder")
    if not sync_folder:
        console.print("[red]エラー: 同期元フォルダが設定されていません。[/red]")
        raise typer.Exit(1)

    # フォントのスキャン
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        scan_task = progress.add_task("フォントをスキャン中...", total=None)

        try:
            source_fonts = font_manager.scan_fonts(sync_folder)
        except Exception as e:
            console.print(f"[red]エラー: フォントのスキャンに失敗しました: {e}[/red]")
            raise typer.Exit(1)

        progress.update(scan_task, completed=True)

    if not source_fonts:
        console.print("[yellow]同期元フォルダにフォントファイルが見つかりませんでした。[/yellow]")
        raise typer.Exit(0)

    # フォント情報を収集
    font_list = []
    installed_fonts = config_manager.get_installed_fonts()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        info_task = progress.add_task("フォント情報を収集中...", total=None)

        for font_path in source_fonts:
            font_name = font_path.name

            # フォント情報を取得
            try:
                info = font_manager.get_font_info(font_path)
            except Exception as e:
                console.print(f"[red]警告: {font_name} の情報取得に失敗しました: {e}[/red]")
                continue

            # インストール状態を確認
            is_installed = font_name in installed_fonts
            installed_info = installed_fonts.get(font_name, {})

            # ハッシュを計算して最新かどうか確認
            needs_update = False
            if is_installed:
                try:
                    current_hash = font_manager.calculate_hash(font_path)
                    stored_hash = installed_info.get("hash")
                    needs_update = current_hash != stored_hash
                except Exception:
                    pass

            font_data = {
                "name": font_name,
                "path": str(font_path),
                "size": info["size"],
                "size_mb": info["size_mb"],
                "modified": datetime.fromtimestamp(info["modified"]),
                "is_installed": is_installed,
                "needs_update": needs_update,
                "installed_at": installed_info.get("installed_at")
            }

            font_list.append(font_data)

        progress.update(info_task, completed=True)

    # フィルタリング
    if status == "installed":
        font_list = [f for f in font_list if f["is_installed"]]
    elif status == "not-installed":
        font_list = [f for f in font_list if not f["is_installed"]]

    # ソート（名前順）
    font_list.sort(key=lambda x: x["name"].lower())

    # 出力
    if format == "json":
        # JSON形式で出力
        output = {
            "sync_folder": sync_folder,
            "total_fonts": len(font_list),
            "fonts": [
                {
                    "name": f["name"],
                    "size_mb": f["size_mb"],
                    "modified": f["modified"].isoformat(),
                    "is_installed": f["is_installed"],
                    "needs_update": f["needs_update"],
                    "installed_at": f["installed_at"]
                }
                for f in font_list
            ]
        }
        console.print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # テーブル形式で出力
        table = Table(title=f"フォント一覧 - {sync_folder}")

        table.add_column("状態", style="cyan", width=8)
        table.add_column("フォント名", style="white")
        table.add_column("サイズ", justify="right", style="blue")
        table.add_column("更新日時", style="green")
        table.add_column("メモ", style="yellow")

        for font in font_list:
            # 状態アイコン
            if font["is_installed"]:
                if font["needs_update"]:
                    status_icon = "⚠️"
                else:
                    status_icon = "✓"
            else:
                status_icon = "✗"

            # メモ
            notes = []
            if font["needs_update"]:
                notes.append("要更新")
            if font["is_installed"] and font["installed_at"]:
                try:
                    installed_date = datetime.fromisoformat(font["installed_at"]).strftime("%Y-%m-%d")
                    notes.append(f"インストール: {installed_date}")
                except Exception:
                    pass

            table.add_row(
                status_icon,
                font["name"],
                f"{font['size_mb']} MB",
                font["modified"].strftime("%Y-%m-%d %H:%M"),
                ", ".join(notes) if notes else "-"
            )

        console.print(table)

        # サマリー
        console.print()
        total = len(font_list)
        installed = sum(1 for f in font_list if f["is_installed"])
        not_installed = total - installed
        needs_update = sum(1 for f in font_list if f["needs_update"])

        console.print(f"[bold]合計:[/bold] {total}個のフォント")
        console.print(f"  [green]✓ インストール済み:[/green] {installed}個")
        if needs_update > 0:
            console.print(f"  [yellow]⚠️  要更新:[/yellow] {needs_update}個")
        console.print(f"  [red]✗ 未インストール:[/red] {not_installed}個")

        if not_installed > 0 or needs_update > 0:
            console.print("\n[dim]ヒント: 'font-sync sync' でフォントを同期できます。[/dim]")
