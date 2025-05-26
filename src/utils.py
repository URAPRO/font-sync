"""ユーティリティ関数とエラーハンドリング

エッジケース処理、リトライ機構、ファイル検証などを提供します。
"""

import time
import os
from pathlib import Path
from typing import Callable, TypeVar, Optional, Dict, Any, List
from functools import wraps
import errno

T = TypeVar('T')


class FontSyncError(Exception):
    """font-sync固有のエラー基底クラス"""
    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__(message)
        self.hint = hint


class FileLockedError(FontSyncError):
    """ファイルがロックされている場合のエラー"""
    pass


class FontValidationError(FontSyncError):
    """フォントファイルの検証エラー"""
    pass


class NetworkSyncError(FontSyncError):
    """ネットワーク同期に関するエラー"""
    pass


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (IOError, OSError, FileLockedError)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """エラー時にリトライするデコレータ
    
    Args:
        max_retries: 最大リトライ回数
        delay: 初回リトライまでの待機時間（秒）
        backoff: リトライごとの待機時間倍率
        exceptions: リトライ対象の例外
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        raise
            
            # このコードには到達しないはずだが、念のため
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def is_file_locked(file_path: Path) -> bool:
    """ファイルがロックされているか確認
    
    Args:
        file_path: チェック対象のファイルパス
        
    Returns:
        ロックされている場合True
    """
    if not file_path.exists():
        return False
        
    try:
        # ファイルを読み取り専用で開けるか確認
        with open(file_path, 'rb'):
            pass
        return False
    except IOError as e:
        if e.errno in (errno.EACCES, errno.EPERM, errno.EBUSY):
            return True
        return False


def wait_for_file_unlock(file_path: Path, timeout: int = 30) -> bool:
    """ファイルのロックが解除されるまで待機
    
    Args:
        file_path: 待機対象のファイルパス
        timeout: タイムアウト時間（秒）
        
    Returns:
        ロックが解除された場合True、タイムアウトした場合False
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if not is_file_locked(file_path):
            return True
        time.sleep(0.5)
    
    return False


def validate_font_file_advanced(file_path: Path) -> Dict[str, Any]:
    """フォントファイルの詳細な検証
    
    Args:
        file_path: 検証対象のフォントファイルパス
        
    Returns:
        検証結果の辞書
        
    Raises:
        FontValidationError: 検証に失敗した場合
    """
    result = {
        "valid": True,
        "warnings": [],
        "file_size_mb": 0,
        "is_locked": False
    }
    
    # ファイルの存在確認
    if not file_path.exists():
        raise FontValidationError(
            f"フォントファイルが存在しません: {file_path}",
            hint="ファイルパスを確認してください"
        )
    
    # ファイルかどうか確認
    if not file_path.is_file():
        raise FontValidationError(
            f"指定されたパスはファイルではありません: {file_path}",
            hint="ディレクトリではなくファイルを指定してください"
        )
    
    # 拡張子チェック
    valid_extensions = ('.otf', '.ttf', '.OTF', '.TTF')
    if file_path.suffix not in valid_extensions:
        raise FontValidationError(
            f"サポートされていないファイル形式です: {file_path.suffix}",
            hint="対応形式: .otf, .ttf"
        )
    
    # ファイルサイズチェック
    file_size = file_path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)
    result["file_size_mb"] = round(file_size_mb, 2)
    
    if file_size == 0:
        raise FontValidationError(
            f"ファイルが空です: {file_path}",
            hint="ファイルが破損している可能性があります"
        )
    
    if file_size_mb > 100:
        result["warnings"].append(f"ファイルサイズが大きすぎます ({file_size_mb:.1f}MB)")
        result["valid"] = True  # 警告のみ、エラーにはしない
    
    # ファイル名の検証
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    filename = file_path.name
    if any(char in filename for char in invalid_chars):
        raise FontValidationError(
            f"ファイル名に無効な文字が含まれています: {filename}",
            hint="ファイル名から特殊文字を取り除いてください"
        )
    
    # ファイルロックチェック
    if is_file_locked(file_path):
        result["is_locked"] = True
        result["warnings"].append("ファイルが他のアプリケーションで使用中です")
    
    # 基本的なバイナリチェック（フォント形式の簡易検証）
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
            
            # OTF/TTFの基本的なマジックナンバーチェック
            valid_headers = [
                b'OTTO',  # OTF
                b'\x00\x01\x00\x00',  # TTF
                b'true',  # TTF
                b'typ1',  # TTF
            ]
            
            if not any(header.startswith(h) for h in valid_headers):
                result["warnings"].append("フォントファイルの形式が不明です")
    except Exception:
        result["warnings"].append("ファイルヘッダーの読み取りに失敗しました")
    
    return result


def get_safe_filename(filename: str) -> str:
    """安全なファイル名に変換
    
    Args:
        filename: 元のファイル名
        
    Returns:
        安全なファイル名
    """
    # 無効な文字を置換
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    safe_name = filename
    
    for char in invalid_chars:
        safe_name = safe_name.replace(char, '_')
    
    # 先頭・末尾の空白とドットを削除
    safe_name = safe_name.strip('. ')
    
    # 空になった場合はデフォルト名を使用
    if not safe_name:
        safe_name = "unnamed_font"
    
    return safe_name


def check_disk_space(path: Path, required_mb: float) -> Dict[str, Any]:
    """ディスク容量をチェック
    
    Args:
        path: チェック対象のパス
        required_mb: 必要な容量（MB）
        
    Returns:
        容量情報の辞書
    """
    try:
        stat = os.statvfs(path)
        free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
        total_mb = (stat.f_blocks * stat.f_frsize) / (1024 * 1024)
        used_percent = ((total_mb - free_mb) / total_mb) * 100
        
        return {
            "free_mb": round(free_mb, 2),
            "total_mb": round(total_mb, 2),
            "used_percent": round(used_percent, 1),
            "has_enough_space": free_mb >= required_mb
        }
    except Exception:
        # エラーの場合は十分な容量があると仮定
        return {
            "free_mb": -1,
            "total_mb": -1,
            "used_percent": -1,
            "has_enough_space": True
        }


def is_cloud_storage_syncing(path: Path) -> bool:
    """クラウドストレージが同期中かチェック
    
    Args:
        path: チェック対象のパス
        
    Returns:
        同期中の場合True
    """
    # Dropboxの同期チェック
    dropbox_attrs = ['.dropbox.attr', '.dropbox']
    for attr in dropbox_attrs:
        if (path.parent / attr).exists():
            # より詳細なチェックは実装が複雑なため、簡易的に判断
            return False
    
    # iCloud Driveの同期チェック
    if '.icloud' in str(path):
        return True
    
    # 一般的な同期中を示すファイル名パターン
    sync_indicators = ['.tmp', '.download', '.partial', '~']
    return any(str(path).endswith(ind) for ind in sync_indicators)


def batch_process(
    items: List[Any],
    process_func: Callable[[Any], Any],
    batch_size: int = 50,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[Any]:
    """大量のアイテムをバッチ処理
    
    Args:
        items: 処理対象のアイテムリスト
        process_func: 各アイテムを処理する関数
        batch_size: バッチサイズ
        progress_callback: 進捗コールバック (current, total)
        
    Returns:
        処理結果のリスト
    """
    results = []
    total = len(items)
    
    for i in range(0, total, batch_size):
        batch = items[i:i + batch_size]
        
        for idx, item in enumerate(batch):
            try:
                result = process_func(item)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "item": item})
            
            if progress_callback:
                progress_callback(i + idx + 1, total)
    
    return results 