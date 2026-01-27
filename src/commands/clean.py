"""cleanコマンドの実装

同期元から削除されたフォントをシステムからも削除するコマンドです。
"""

from typing import List, Tuple

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from ..config import ConfigManager
from ..font_manager import FontManager
from ..main import handle_errors

console = Console()


@handle_errors
def clean_command(dry_run: bool) -> None:
    """不要なフォントを削除

    Args:
        dry_run (bool): 実際には削除せず、削除対象を表示のみ
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

    console.print(f"[bold]同期元フォルダ:[/bold] [cyan]{sync_folder}[/cyan]\n")

    # 現在の同期元フォントをスキャン
    try:
        source_fonts = font_manager.scan_fonts(sync_folder)
        source_font_names = {font.name for font in source_fonts}
    except Exception as e:
        console.print(f"[red]エラー: フォントのスキャンに失敗しました: {e}[/red]")
        raise typer.Exit(1)

    # インストール済みフォントを取得
    installed_fonts = config_manager.get_installed_fonts()

    if not installed_fonts:
        console.print("[green]✓ クリーンアップ対象のフォントはありません。[/green]")
        raise typer.Exit(0)

    # 削除対象のフォントを特定
    fonts_to_remove: List[Tuple[str, str]] = []  # (font_name, reason)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        check_task = progress.add_task("削除対象を確認中...", total=None)

        for font_name, font_info in installed_fonts.items():
            # 同期元に存在しないフォント
            if font_name not in source_font_names:
                fonts_to_remove.append((font_name, "同期元から削除済み"))
                continue

            # システム上に存在しないフォント（設定には残っているが実体がない）
            if not font_manager.is_font_installed(font_name):
                fonts_to_remove.append((font_name, "システム上に存在しない"))

        progress.update(check_task, completed=True)

    if not fonts_to_remove:
        console.print("[green]✓ クリーンアップ対象のフォントはありません。[/green]")
        raise typer.Exit(0)

    # 削除対象の表示
    table = Table(title=f"削除対象のフォント（{len(fonts_to_remove)}個）")
    table.add_column("フォント名", style="white")
    table.add_column("理由", style="yellow")
    table.add_column("インストール日", style="dim")

    for font_name, reason in fonts_to_remove:
        installed_at = installed_fonts.get(font_name, {}).get("installed_at", "不明")
        if installed_at != "不明":
            try:
                from datetime import datetime
                installed_at = datetime.fromisoformat(installed_at).strftime("%Y-%m-%d")
            except Exception:
                pass

        table.add_row(font_name, reason, installed_at)

    console.print(table)

    if dry_run:
        console.print("\n[yellow]これはドライランモードです。実際の削除は行われません。[/yellow]")
        console.print("[dim]実際に削除するには '--execute' オプションを使用してください。[/dim]")
        raise typer.Exit(0)

    # 削除の確認
    console.print()
    if not Confirm.ask(f"[red]{len(fonts_to_remove)}個のフォントを削除しますか？[/red]"):
        console.print("[yellow]削除をキャンセルしました。[/yellow]")
        raise typer.Exit(0)

    # 削除の実行
    success_count = 0
    error_count = 0
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        delete_task = progress.add_task("フォントを削除中...", total=len(fonts_to_remove))

        for font_name, reason in fonts_to_remove:
            progress.update(delete_task, description=f"削除中: {font_name}")

            # システムからフォントを削除（存在する場合）
            if font_manager.is_font_installed(font_name):
                try:
                    font_manager.remove_font(font_name)
                except Exception as e:
                    error_count += 1
                    errors.append(f"{font_name}: {str(e)}")
                    progress.update(delete_task, advance=1)
                    continue

            # 設定から削除
            config_manager.remove_installed_font(font_name)
            success_count += 1

            progress.update(delete_task, advance=1)

    # 設定を保存
    try:
        config_manager.save_config()
    except Exception as e:
        console.print(f"[red]警告: 設定の保存に失敗しました: {e}[/red]")

    # 結果を表示
    console.print()
    if success_count > 0:
        console.print(f"[green]✓ {success_count}個のフォントを削除しました。[/green]")

    if error_count > 0:
        console.print(f"[red]✗ {error_count}個のフォントの削除に失敗しました。[/red]")
        console.print("\n[red]エラー詳細:[/red]")
        for error in errors[:5]:  # 最初の5個まで表示
            console.print(f"  - {error}")
        if len(errors) > 5:
            console.print(f"  ... 他 {len(errors) - 5}個のエラー")

    console.print("\n[dim]クリーンアップ完了[/dim]")
