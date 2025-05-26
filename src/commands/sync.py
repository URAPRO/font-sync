"""syncコマンドの実装

同期元フォルダから新しいフォントを同期するコマンドです。
"""

from pathlib import Path
from typing import List, Tuple, Dict
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from datetime import datetime

from ..config import ConfigManager
from ..font_manager import FontManager
from ..main import handle_errors
from ..utils import check_disk_space, batch_process
from ..parallel import ParallelProcessor, ParallelConfig

console = Console()


@handle_errors
def sync_command() -> None:
    """フォントの同期を実行"""
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
    
    # フォントのスキャン（大量フォント対応）
    all_source_fonts = []
    font_count = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        scan_task = progress.add_task("フォントをスキャン中...", total=None)
        
        try:
            # バッチモードでスキャン（メモリ効率向上）
            for font_batch in font_manager.scan_fonts(sync_folder, yield_batch=True):
                all_source_fonts.extend(font_batch)
                font_count = len(all_source_fonts)
                progress.update(scan_task, description=f"フォントをスキャン中... ({font_count}個)")
        except Exception as e:
            console.print(f"[red]エラー: フォントのスキャンに失敗しました: {e}[/red]")
            raise typer.Exit(1)
        
        progress.update(scan_task, completed=True)
    
    if not all_source_fonts:
        console.print("[yellow]同期元フォルダにフォントファイルが見つかりませんでした。[/yellow]")
        raise typer.Exit(0)
    
    console.print(f"[blue]ℹ {len(all_source_fonts)}個のフォントファイルが見つかりました。[/blue]\n")
    
    # 大量フォントの警告
    if len(all_source_fonts) > 500:
        console.print(f"[yellow]⚠️  大量のフォント（{len(all_source_fonts)}個）が検出されました。処理に時間がかかる場合があります。[/yellow]\n")
    
    # 同期が必要なフォントを特定
    fonts_to_sync = []
    fonts_to_update = []
    fonts_up_to_date = []
    
    installed_fonts = config_manager.get_installed_fonts()
    
    # 必要な容量を計算
    total_size_mb = 0
    
    # 並列処理の設定
    use_parallel = len(all_source_fonts) > 50  # 50個以上で並列処理を使用
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        diff_task = progress.add_task("差分を確認中...", total=len(all_source_fonts))
        
        if use_parallel:
            # 並列処理でハッシュ計算
            console.print("[dim]並列処理モードで実行中...[/dim]")
            parallel = ParallelProcessor()
            
            # 進捗更新コールバック
            def progress_callback(completed: int, total: int):
                progress.update(diff_task, completed=completed)
            
            # 並列でハッシュ計算
            hash_results = parallel.calculate_hashes_parallel(
                all_source_fonts,
                font_manager.calculate_hash,
                progress_callback
            )
            
            # 結果を処理
            for font_path in all_source_fonts:
                font_name = font_path.name
                info = font_manager.get_font_info(font_path)
                size_mb = info["size_mb"]
                
                # ファイルがロックされている場合はスキップ
                if info.get("is_locked"):
                    console.print(f"[yellow]警告: {font_name} はロックされているためスキップします[/yellow]")
                    continue
                
                # クラウド同期中の場合はスキップ
                if info.get("is_syncing"):
                    console.print(f"[yellow]警告: {font_name} は同期中のためスキップします[/yellow]")
                    continue
                
                font_hash = hash_results.get(font_path)
                if font_hash is None:
                    console.print(f"[red]エラー: {font_name} のハッシュ計算に失敗しました[/red]")
                    continue
                
                if font_name not in installed_fonts:
                    fonts_to_sync.append((font_path, font_hash))
                    total_size_mb += size_mb
                else:
                    stored_hash = installed_fonts[font_name].get("hash")
                    if stored_hash != font_hash:
                        fonts_to_update.append((font_path, font_hash))
                        total_size_mb += size_mb
                    else:
                        fonts_up_to_date.append(font_path)
        else:
            # 従来のバッチ処理
            def check_font_diff(font_path: Path) -> Dict:
                font_name = font_path.name
                result = {"path": font_path, "action": "none", "hash": None, "size_mb": 0}
                
                try:
                    # フォント情報取得
                    info = font_manager.get_font_info(font_path)
                    result["size_mb"] = info["size_mb"]
                    
                    # ファイルがロックされている場合はスキップ
                    if info.get("is_locked"):
                        console.print(f"[yellow]警告: {font_name} はロックされているためスキップします[/yellow]")
                        return result
                    
                    # クラウド同期中の場合はスキップ
                    if info.get("is_syncing"):
                        console.print(f"[yellow]警告: {font_name} は同期中のためスキップします[/yellow]")
                        return result
                    
                    # ハッシュ計算
                    font_hash = font_manager.calculate_hash(font_path)
                    result["hash"] = font_hash
                    
                    if font_name not in installed_fonts:
                        result["action"] = "install"
                    else:
                        stored_hash = installed_fonts[font_name].get("hash")
                        if stored_hash != font_hash:
                            result["action"] = "update"
                        else:
                            result["action"] = "up-to-date"
                            
                except Exception as e:
                    console.print(f"[red]エラー: {font_name} の処理中にエラーが発生しました: {e}[/red]")
                    
                progress.update(diff_task, advance=1)
                return result
            
            # バッチ処理実行
            results = batch_process(
                all_source_fonts,
                check_font_diff,
                batch_size=50
            )
            
            # 結果を分類
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
    
    # 同期対象がない場合
    total_to_sync = len(fonts_to_sync) + len(fonts_to_update)
    if total_to_sync == 0:
        console.print("[green]✓ すべてのフォントは最新です。[/green]")
        console.print(f"[dim]インストール済み: {len(fonts_up_to_date)}個[/dim]")
        raise typer.Exit(0)
    
    # ディスク容量チェック
    disk_info = check_disk_space(Path.home() / "Library" / "Fonts", total_size_mb * 1.1)
    if not disk_info["has_enough_space"]:
        console.print(f"[red]エラー: ディスク容量が不足しています[/red]")
        console.print(f"[yellow]必要な容量: {total_size_mb:.1f}MB[/yellow]")
        console.print(f"[yellow]空き容量: {disk_info['free_mb']:.1f}MB[/yellow]")
        raise typer.Exit(1)
    
    # 同期対象を表示
    table = Table(title="同期対象のフォント", show_header=True, header_style="bold magenta")
    table.add_column("状態", style="cyan", width=12)
    table.add_column("フォント名", style="white")
    table.add_column("サイズ", style="green", width=10)
    
    for font_path, _ in fonts_to_sync:
        info = font_manager.get_font_info(font_path)
        table.add_row("新規", info["name"], f"{info['size_mb']} MB")
    
    for font_path, _ in fonts_to_update:
        info = font_manager.get_font_info(font_path)
        table.add_row("更新", info["name"], f"{info['size_mb']} MB")
    
    console.print(table)
    console.print()
    
    # 同期の実行
    console.print(f"[bold]{total_to_sync}個のフォント（合計 {total_size_mb:.1f}MB）を同期します。[/bold]\n")
    
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
        sync_task = progress.add_task("フォントを同期中...", total=total_to_sync)
        
        # 新規フォントのインストール
        for font_path, font_hash in fonts_to_sync:
            font_name = font_path.name
            progress.update(sync_task, description=f"インストール中: {font_name}")
            
            try:
                # フォントをコピー（検証付き）
                font_manager.copy_font(font_path, validate=True)
                # 設定に記録
                config_manager.add_installed_font(font_name, font_hash)
                success_count += 1
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                # カスタムエラーの場合はヒントも含める
                if hasattr(e, 'hint') and e.hint:
                    error_msg += f" ({e.hint})"
                errors.append(f"{font_name}: {error_msg}")
            
            progress.update(sync_task, advance=1)
        
        # 更新フォントのインストール
        for font_path, font_hash in fonts_to_update:
            font_name = font_path.name
            progress.update(sync_task, description=f"更新中: {font_name}")
            
            try:
                # フォントを上書きコピー（検証付き）
                font_manager.copy_font(font_path, validate=True)
                # 設定を更新
                config_manager.add_installed_font(font_name, font_hash)
                success_count += 1
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                if hasattr(e, 'hint') and e.hint:
                    error_msg += f" ({e.hint})"
                errors.append(f"{font_name}: {error_msg}")
            
            progress.update(sync_task, advance=1)
    
    # 設定を保存
    try:
        config_manager.save_config()
    except Exception as e:
        console.print(f"[red]警告: 設定の保存に失敗しました: {e}[/red]")
    
    # 結果を表示
    console.print()
    if success_count > 0:
        console.print(f"[green]✓ {success_count}個のフォントを正常に同期しました。[/green]")
    
    if error_count > 0:
        console.print(f"[red]✗ {error_count}個のフォントの同期に失敗しました。[/red]")
        console.print("\n[red]エラー詳細:[/red]")
        # エラーは最大10個まで表示
        for i, error in enumerate(errors[:10]):
            console.print(f"  - {error}")
        if len(errors) > 10:
            console.print(f"  ... 他 {len(errors) - 10}個のエラー")
            console.print("[dim]すべてのエラーを確認するには、--verbose オプションを使用してください[/dim]")
    
    # 統計情報
    console.print(f"\n[dim]同期完了: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
    if disk_info["free_mb"] > 0:
        console.print(f"[dim]残りディスク容量: {disk_info['free_mb']:.1f}MB ({100 - disk_info['used_percent']:.1f}%)[/dim]") 