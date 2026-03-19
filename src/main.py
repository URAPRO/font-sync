"""font-sync CLIアプリケーションのエントリーポイント"""

from typing import Optional

import typer
from rich.console import Console

# バージョン情報をインポート
from . import __version__

# コマンドモジュールのインポート（後で追加）
# from .commands import init, sync, list_fonts, import_fonts, clean
from .utils import FontSyncError

# Typerアプリケーションの作成
app = typer.Typer(
    name="font-sync",
    help="macOS専用のCLIフォント同期ツール。Dropbox等の共有フォルダ経由で複数のMac間でフォントを自動同期します。",
    add_completion=False,
)

# Richコンソールの作成（美しい出力用）
console = Console()


def version_callback(value: bool) -> None:
    """バージョン情報を表示するコールバック"""
    if value:
        console.print(f"font-sync version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="バージョン情報を表示",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """
    font-sync - macOS専用のCLIフォント同期ツール

    Dropbox等の共有フォルダを介して、複数のMac間でフォントを簡単に同期できます。
    """
    pass


@app.command()
def init(
    sync_folder: Optional[str] = typer.Option(
        None,
        "--folder",
        "-f",
        help="同期元フォルダのパス（例: ~/Dropbox/shared-fonts/）",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="既存の設定を上書きする",
    ),
) -> None:
    """
    font-syncの初期設定を行います。

    同期元フォルダのパスを指定して、設定ファイルを作成します。
    """
    from .commands.init import init_command
    init_command(sync_folder, force)


@app.command()
def sync(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="JSON形式で出力（GUI連携用）",
    ),
    source: Optional[str] = typer.Option(
        None,
        "--source",
        help="特定ソースのIDを指定して同期（省略時は全有効ソース）",
    ),
) -> None:
    """
    同期元フォルダから新しいフォントを同期します。

    設定された同期元フォルダをスキャンし、新規または更新されたフォントを
    ~/Library/Fonts/ にインストールします。
    """
    from .commands.sync import sync_command
    sync_command(json_output=json_output, source_id=source)


@app.command(name="list")
def list_fonts(
    status: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="フィルタリング: all（全て）, installed（インストール済み）, not-installed（未インストール）",
    ),
    format: Optional[str] = typer.Option(
        "table",
        "--format",
        "-f",
        help="出力形式: table（テーブル）, json（JSON）",
    ),
) -> None:
    """
    同期元フォルダ内のフォント一覧を表示します。

    各フォントのインストール状態、サイズ、更新日時を確認できます。
    """
    from .commands.list import list_command
    list_command(status, format)


@app.command(name="import")
def import_fonts(
    font_path: Optional[str] = typer.Argument(
        None,
        help="インポートするフォントファイルまたはディレクトリのパス",
    ),
    move: bool = typer.Option(
        False,
        "--move",
        "-m",
        help="コピーではなく移動する",
    ),
) -> None:
    """
    既存のフォントを同期元フォルダにインポートします。

    指定したフォントファイルまたはディレクトリ内のフォントを
    同期元フォルダにコピー（または移動）します。
    """
    from .commands.import_fonts import import_command
    import_command(font_path, move)


@app.command()
def adopt(
    source: Optional[str] = typer.Option(
        None,
        "--source",
        help="取り込み先のソースID（省略時はソースが1つなら自動選択）",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="実際にはコピーせず、対象フォント一覧を表示のみ",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="JSON形式で出力（GUI連携用）",
    ),
    move: bool = typer.Option(
        False,
        "--move",
        help="コピーではなく移動する（元ファイルを削除）",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="--move の確認プロンプトをスキップ",
    ),
) -> None:
    """
    ~/Library/Fonts/ 内のフォントを同期元フォルダに取り込みます。

    システムフォントや Adobe Fonts は自動的に除外されます。
    同期元フォルダに既に同名ファイルがある場合はスキップされます。
    """
    from .commands.adopt import adopt_command
    adopt_command(
        source_id=source,
        dry_run=dry_run,
        json_output=json_output,
        move=move,
        yes=yes,
    )


@app.command()
def clean(
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--execute",
        help="実際には削除せず、削除対象を表示のみ",
    ),
) -> None:
    """
    同期元から削除されたフォントをシステムからも削除します。

    同期元フォルダに存在しないが、システムにインストールされている
    フォントを検出して削除します。
    """
    from .commands.clean import clean_command
    clean_command(dry_run)


# エラーハンドリング用のデコレータ
def handle_errors(func):
    """共通エラーハンドリングデコレータ"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except typer.Exit:
            # typer.Exitはそのまま再発生させる（正常終了も含む）
            raise
        except FontSyncError as e:
            # カスタムエラーの処理
            console.print(f"[red]エラー: {e}[/red]")
            if e.hint:
                console.print(f"[yellow]💡 ヒント: {e.hint}[/yellow]")
            raise typer.Exit(1)
        except FileNotFoundError as e:
            console.print(f"[red]エラー: {e}[/red]")
            console.print("[yellow]💡 ヒント: ファイルパスを確認してください[/yellow]")
            raise typer.Exit(1)
        except PermissionError as e:
            console.print(f"[red]権限エラー: {e}[/red]")
            console.print("[yellow]💡 ヒント: 管理者権限で実行するか、以下のコマンドを試してください:[/yellow]")
            console.print("[dim]  sudo font-sync <コマンド>[/dim]")
            raise typer.Exit(1)
        except IOError as e:
            console.print(f"[red]入出力エラー: {e}[/red]")
            console.print("[yellow]💡 ヒント: ディスク容量やファイルアクセス権限を確認してください[/yellow]")
            raise typer.Exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]操作がキャンセルされました[/yellow]")
            raise typer.Exit(130)
        except Exception as e:
            console.print(f"[red]予期しないエラーが発生しました: {e}[/red]")
            console.print("[yellow]💡 ヒント: 問題が解決しない場合は、以下の情報とともにissueを作成してください:[/yellow]")
            console.print(f"[dim]  エラータイプ: {type(e).__name__}[/dim]")
            console.print(f"[dim]  エラー詳細: {e}[/dim]")
            raise typer.Exit(1)
    return wrapper


# lock サブコマンドを登録（handle_errors 定義後にインポートして循環参照を回避）
from .commands.lock_cmd import lock_app  # noqa: E402

app.add_typer(lock_app, name="lock", help="fontops.lock の管理")


# apply コマンドを登録（handle_errors 定義後にインポートして循環参照を回避）
from .commands.apply import apply_command as _apply_command  # noqa: E402


@app.command("apply", help="fontops.lock に基づいてフォント環境の状態を確認します")
def apply_cmd(
    resolve: bool = typer.Option(
        False,
        "--resolve",
        help="不足フォントを自動解決する（未実装、m5-f3 で実装予定）",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="実行内容を確認のみ（--resolve と組み合わせて使用）",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="JSON 形式で出力",
    ),
) -> None:
    """fontops.lock に基づいてフォント環境の状態を確認します。"""
    _apply_command(resolve=resolve, dry_run=dry_run, json_output=json_output)


if __name__ == "__main__":
    app()
