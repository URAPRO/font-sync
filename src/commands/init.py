"""initコマンドの実装

font-syncの初期設定を行うコマンドです。
"""

import os
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm

from ..config import ConfigManager
from ..main import handle_errors

console = Console()


@handle_errors
def init_command(sync_folder: Optional[str], force: bool) -> None:
    """font-syncの初期設定を実行
    
    Args:
        sync_folder (Optional[str]): 同期元フォルダのパス
        force (bool): 既存設定を上書きするかどうか
    """
    config_manager = ConfigManager()
    
    # 既存の設定ファイルをチェック
    if config_manager.config_exists() and not force:
        console.print("[yellow]既に設定ファイルが存在します。[/yellow]")
        
        # 既存の設定を表示
        try:
            config = config_manager.load_config()
            current_folder = config.get("sync_folder", "未設定")
            console.print(f"現在の同期元フォルダ: [cyan]{current_folder}[/cyan]")
        except Exception:
            console.print("[red]既存の設定ファイルの読み込みに失敗しました。[/red]")
        
        if not Confirm.ask("設定を上書きしますか？"):
            console.print("[yellow]初期設定をキャンセルしました。[/yellow]")
            raise typer.Exit(0)
    
    # 同期元フォルダのパスを取得
    if not sync_folder:
        # 対話的に入力を求める
        console.print("[bold]font-syncの初期設定を開始します。[/bold]\n")
        console.print("同期元フォルダのパスを入力してください。")
        console.print("例: ~/Dropbox/shared-fonts/")
        
        default_path = "~/Dropbox/shared-fonts/"
        sync_folder = Prompt.ask(
            "同期元フォルダのパス",
            default=default_path
        )
    
    # パスの検証
    sync_folder_path = Path(os.path.expanduser(sync_folder))
    
    # フォルダの存在確認
    if not sync_folder_path.exists():
        console.print(f"[yellow]警告: 指定されたフォルダが存在しません: {sync_folder_path}[/yellow]")
        
        if Confirm.ask("フォルダを作成しますか？"):
            try:
                sync_folder_path.mkdir(parents=True, exist_ok=True)
                console.print(f"[green]フォルダを作成しました: {sync_folder_path}[/green]")
            except Exception as e:
                console.print(f"[red]フォルダの作成に失敗しました: {e}[/red]")
                raise typer.Exit(1)
        else:
            console.print("[red]有効なフォルダパスを指定してください。[/red]")
            raise typer.Exit(1)
    
    # ディレクトリかどうか確認
    if not sync_folder_path.is_dir():
        console.print(f"[red]エラー: 指定されたパスはディレクトリではありません: {sync_folder_path}[/red]")
        raise typer.Exit(1)
    
    # アクセス権限の確認
    if not os.access(sync_folder_path, os.R_OK):
        console.print(f"[red]エラー: フォルダへの読み取り権限がありません: {sync_folder_path}[/red]")
        raise typer.Exit(1)
    
    # 設定を保存
    try:
        config_manager.initialize_config(str(sync_folder_path))
        console.print(f"\n[green]✓ 設定を保存しました。[/green]")
        console.print(f"設定ファイル: [cyan]{config_manager.config_file}[/cyan]")
        console.print(f"同期元フォルダ: [cyan]{sync_folder_path}[/cyan]")
        
        # フォント数をカウント
        font_count = count_fonts_in_folder(sync_folder_path)
        if font_count > 0:
            console.print(f"\n[blue]ℹ {font_count}個のフォントファイルが見つかりました。[/blue]")
            console.print("'font-sync sync' コマンドでフォントを同期できます。")
        else:
            console.print("\n[yellow]警告: 同期元フォルダにフォントファイルが見つかりませんでした。[/yellow]")
            console.print("'.otf' または '.ttf' ファイルを同期元フォルダに配置してください。")
            
    except Exception as e:
        console.print(f"[red]エラー: 設定の保存に失敗しました: {e}[/red]")
        raise typer.Exit(1)
    
    console.print("\n[green]初期設定が完了しました！[/green]")


def count_fonts_in_folder(folder_path: Path) -> int:
    """フォルダ内のフォントファイル数をカウント
    
    Args:
        folder_path (Path): カウント対象のフォルダパス
        
    Returns:
        int: フォントファイルの数
    """
    font_extensions = (".otf", ".ttf")
    count = 0
    
    try:
        for ext in font_extensions:
            count += len(list(folder_path.rglob(f"*{ext}")))
    except Exception:
        # エラーが発生しても0を返す
        pass
    
    return count 