"""fontops.lock 管理コマンドの実装"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..font_inventory import enumerate_installed_fonts
from ..lockfile import FontopsLock, LockFont, LockStyle, load_lock, save_lock
from ..main import handle_errors

console = Console()

lock_app = typer.Typer(
    name="lock",
    help="fontops.lock の管理",
    add_completion=False,
)

_FONTOPS_VERSION = "1"
_LOCK_FILE = Path("fontops.lock")


# ---------------------------------------------------------------------------
# Typer コマンド（シグネチャ解析が必要なため @handle_errors は内部関数に適用）
# ---------------------------------------------------------------------------


@lock_app.command("init")
def lock_init_cmd(
    name: str = typer.Option(
        ...,
        "--name",
        "-n",
        help="プロジェクト名",
    ),
    all_fonts: bool = typer.Option(
        False,
        "--all",
        help="全フォントを lock に追加する",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="既存の fontops.lock を上書きする",
    ),
) -> None:
    """fontops.lock を初期化します。"""
    lock_init_command(name=name, all_fonts=all_fonts, force=force)


@lock_app.command("add")
def lock_add_cmd(
    family: str = typer.Argument(..., help="追加するフォントファミリー名"),
    source: str = typer.Option(
        "local",
        "--source",
        "-s",
        help="ソース種別 (local, adobe-fonts, google-fonts, commercial, system)",
    ),
    styles: Optional[str] = typer.Option(
        None,
        "--styles",
        help="カンマ区切りのスタイル一覧（例: 'Regular,Bold'）",
    ),
) -> None:
    """フォントを fontops.lock に追加します。"""
    lock_add_command(family=family, source=source, styles=styles)


@lock_app.command("remove")
def lock_remove_cmd(
    family: str = typer.Argument(..., help="削除するフォントファミリー名"),
) -> None:
    """フォントを fontops.lock から削除します。"""
    lock_remove_command(family=family)


# ---------------------------------------------------------------------------
# 内部実装（@handle_errors 適用）
# ---------------------------------------------------------------------------


@handle_errors
def lock_init_command(name: str, all_fonts: bool, force: bool) -> None:
    """fontops.lock 初期化の実装。"""
    if _LOCK_FILE.exists() and not force:
        console.print("[red]エラー: fontops.lock が既に存在します。[/red]")
        console.print("[yellow]💡 ヒント: --force オプションで上書きできます[/yellow]")
        raise typer.Exit(1)

    fonts = enumerate_installed_fonts()

    if not all_fonts:
        _print_fonts_preview_table(fonts)
        console.print("[yellow]💡 すべて追加するには --all オプションを使用してください[/yellow]")
        return

    # ファミリーごとにまとめて LockFont リストを構築
    family_map: dict = {}
    for font in fonts:
        if font.family not in family_map:
            family_map[font.family] = LockFont(
                family=font.family,
                source=font.source,
                styles=[LockStyle(name=font.style)],
            )
        else:
            existing_styles = [s.name for s in family_map[font.family].styles]
            if font.style not in existing_styles:
                family_map[font.family].styles.append(LockStyle(name=font.style))

    lock_fonts = list(family_map.values())
    lock = FontopsLock(
        fontops_version=_FONTOPS_VERSION,
        project_name=name,
        fonts=lock_fonts,
    )
    save_lock(lock, _LOCK_FILE)

    _print_init_results_table(lock_fonts)
    console.print(
        f"[green]✓ fontops.lock を作成しました（{len(lock_fonts)} フォントファミリー）[/green]"
    )


@handle_errors
def lock_add_command(family: str, source: str, styles: Optional[str]) -> None:
    """フォント追加の実装。"""
    if not _LOCK_FILE.exists():
        console.print(
            "[red]エラー: fontops.lock が見つかりません。'font-sync lock init' を実行してください。[/red]"
        )
        raise typer.Exit(1)

    lock = load_lock(_LOCK_FILE)

    if any(lf.family.lower() == family.lower() for lf in lock.fonts):
        console.print(f"[red]エラー: '{family}' は既に fontops.lock に存在します[/red]")
        raise typer.Exit(1)

    lock_styles = []
    if styles:
        for style_name in styles.split(","):
            style_name = style_name.strip()
            if style_name:
                lock_styles.append(LockStyle(name=style_name))

    lock.fonts.append(LockFont(family=family, source=source, styles=lock_styles))
    save_lock(lock, _LOCK_FILE)

    console.print(
        f"[green]✓ '{family}' を追加しました"
        f"（ソース: {source}, スタイル: {len(lock_styles)}件）[/green]"
    )


@handle_errors
def lock_remove_command(family: str) -> None:
    """フォント削除の実装。"""
    if not _LOCK_FILE.exists():
        console.print(
            "[red]エラー: fontops.lock が見つかりません。'font-sync lock init' を実行してください。[/red]"
        )
        raise typer.Exit(1)

    lock = load_lock(_LOCK_FILE)
    original_count = len(lock.fonts)
    lock.fonts = [lf for lf in lock.fonts if lf.family.lower() != family.lower()]

    if len(lock.fonts) == original_count:
        console.print(f"[red]エラー: '{family}' が fontops.lock に見つかりません[/red]")
        raise typer.Exit(1)

    save_lock(lock, _LOCK_FILE)
    console.print(f"[green]✓ '{family}' を削除しました[/green]")


# ---------------------------------------------------------------------------
# テーブル表示ヘルパー
# ---------------------------------------------------------------------------


def _print_fonts_preview_table(fonts: list) -> None:
    """フォント一覧プレビューテーブルを表示。"""
    if not fonts:
        console.print("[yellow]フォントが見つかりませんでした[/yellow]")
        return

    family_map: dict = {}
    for font in fonts:
        if font.family not in family_map:
            family_map[font.family] = {"source": font.source, "styles": set()}
        family_map[font.family]["styles"].add(font.style)

    table = Table(title="インストール済みフォント（プレビュー）")
    table.add_column("ファミリー", style="cyan")
    table.add_column("ソース", style="magenta")
    table.add_column("スタイル数", justify="right")

    for family_name, info in sorted(family_map.items()):
        table.add_row(family_name, info["source"], str(len(info["styles"])))

    console.print(table)


def _print_init_results_table(lock_fonts: list) -> None:
    """init 結果テーブルを表示。"""
    table = Table(title="fontops.lock 作成結果")
    table.add_column("ファミリー", style="cyan")
    table.add_column("ソース", style="magenta")
    table.add_column("スタイル数", justify="right")

    for lf in lock_fonts:
        table.add_row(lf.family, lf.source, str(len(lf.styles)))

    console.print(table)
