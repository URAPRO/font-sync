"""importコマンドの実装

既存のフォントを同期元フォルダにインポートするコマンドです。
"""

import shutil
from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm

from ..config import ConfigManager
from ..font_manager import FontManager
from ..main import handle_errors

console = Console()


@handle_errors
def import_command(font_path: Optional[str], move: bool) -> None:
    """フォントを同期元フォルダにインポート
    
    Args:
        font_path (Optional[str]): インポートするフォントのパス
        move (bool): コピーではなく移動するかどうか
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
    
    sync_folder_path = Path(sync_folder)
    
    # インポート元のパスを取得
    if not font_path:
        # 対話的に入力を求める
        console.print("[bold]フォントのインポート[/bold]\n")
        console.print("インポートするフォントファイルまたはディレクトリのパスを入力してください。")
        console.print("例: ~/Downloads/MyFont.otf または ~/Downloads/fonts/")
        
        font_path = Prompt.ask("パス")
    
    import_path = Path(font_path).expanduser()
    
    # パスの存在確認
    if not import_path.exists():
        console.print(f"[red]エラー: 指定されたパスが存在しません: {import_path}[/red]")
        raise typer.Exit(1)
    
    # インポート対象のフォントを収集
    fonts_to_import: List[Path] = []
    
    if import_path.is_file():
        # 単一ファイルの場合
        if font_manager.validate_font_file(import_path):
            fonts_to_import.append(import_path)
        else:
            console.print(f"[red]エラー: 有効なフォントファイルではありません: {import_path}[/red]")
            console.print("[yellow]対応形式: .otf, .ttf[/yellow]")
            raise typer.Exit(1)
    else:
        # ディレクトリの場合
        console.print(f"[blue]ディレクトリをスキャン中: {import_path}[/blue]")
        
        for ext in font_manager.font_extensions:
            fonts_to_import.extend(import_path.rglob(f"*{ext}"))
        
        # 隠しファイルを除外
        fonts_to_import = [f for f in fonts_to_import if not f.name.startswith(".")]
        
        if not fonts_to_import:
            console.print("[yellow]指定されたディレクトリにフォントファイルが見つかりませんでした。[/yellow]")
            raise typer.Exit(0)
    
    # インポート対象の確認
    console.print(f"\n[bold]{len(fonts_to_import)}個のフォントが見つかりました:[/bold]")
    for font in fonts_to_import[:10]:  # 最初の10個まで表示
        console.print(f"  • {font.name}")
    if len(fonts_to_import) > 10:
        console.print(f"  ... 他 {len(fonts_to_import) - 10}個")
    
    # 操作の確認
    operation = "移動" if move else "コピー"
    console.print(f"\n同期元フォルダに{operation}します: [cyan]{sync_folder_path}[/cyan]")
    
    if not Confirm.ask(f"{operation}を実行しますか？"):
        console.print("[yellow]操作をキャンセルしました。[/yellow]")
        raise typer.Exit(0)
    
    # インポートの実行
    success_count = 0
    error_count = 0
    errors = []
    skipped_count = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        import_task = progress.add_task(f"フォントを{operation}中...", total=len(fonts_to_import))
        
        for font_path in fonts_to_import:
            font_name = font_path.name
            dest_path = sync_folder_path / font_name
            
            progress.update(import_task, description=f"{operation}中: {font_name}")
            
            # 既存ファイルのチェック
            if dest_path.exists():
                # 同じファイルか確認
                try:
                    src_hash = font_manager.calculate_hash(font_path)
                    dest_hash = font_manager.calculate_hash(dest_path)
                    
                    if src_hash == dest_hash:
                        skipped_count += 1
                        progress.update(import_task, advance=1)
                        continue
                except Exception:
                    pass
                
                # 異なるファイルの場合は番号を付けて保存
                counter = 1
                while dest_path.exists():
                    stem = font_path.stem
                    suffix = font_path.suffix
                    dest_path = sync_folder_path / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            try:
                if move:
                    shutil.move(str(font_path), str(dest_path))
                else:
                    shutil.copy2(str(font_path), str(dest_path))
                success_count += 1
            except Exception as e:
                error_count += 1
                errors.append(f"{font_name}: {str(e)}")
            
            progress.update(import_task, advance=1)
    
    # 結果を表示
    console.print()
    if success_count > 0:
        console.print(f"[green]✓ {success_count}個のフォントを{operation}しました。[/green]")
    
    if skipped_count > 0:
        console.print(f"[blue]ℹ {skipped_count}個のフォントは既に存在するためスキップしました。[/blue]")
    
    if error_count > 0:
        console.print(f"[red]✗ {error_count}個のフォントの{operation}に失敗しました。[/red]")
        console.print("\n[red]エラー詳細:[/red]")
        for error in errors[:5]:  # 最初の5個まで表示
            console.print(f"  - {error}")
        if len(errors) > 5:
            console.print(f"  ... 他 {len(errors) - 5}個のエラー")
    
    if success_count > 0:
        console.print(f"\n[dim]ヒント: 'font-sync sync' で新しいフォントを他のMacに同期できます。[/dim]") 