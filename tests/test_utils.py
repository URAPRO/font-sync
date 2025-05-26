"""utils.pyのテスト"""

import pytest
from pathlib import Path
import time
import tempfile
import os

from src.utils import (
    FontSyncError, FileLockedError, FontValidationError,
    retry_on_error, is_file_locked, wait_for_file_unlock,
    validate_font_file_advanced, get_safe_filename,
    check_disk_space, is_cloud_storage_syncing,
    batch_process
)


class TestCustomErrors:
    """カスタムエラークラスのテスト"""
    
    def test_font_sync_error_with_hint(self):
        """FontSyncErrorがヒントを保持することを確認"""
        error = FontSyncError("エラーメッセージ", hint="解決方法")
        assert str(error) == "エラーメッセージ"
        assert error.hint == "解決方法"
    
    def test_font_sync_error_without_hint(self):
        """FontSyncErrorがヒントなしでも動作することを確認"""
        error = FontSyncError("エラーメッセージ")
        assert str(error) == "エラーメッセージ"
        assert error.hint is None


class TestRetryDecorator:
    """リトライデコレータのテスト"""
    
    def test_retry_on_success(self):
        """成功時はリトライしないことを確認"""
        call_count = 0
        
        @retry_on_error(max_retries=3)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = success_func()
        assert result == "success"
        assert call_count == 1
    
    def test_retry_on_failure(self):
        """失敗時にリトライすることを確認"""
        call_count = 0
        
        @retry_on_error(max_retries=3, delay=0.1)
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise IOError("テストエラー")
            return "success"
        
        result = failing_func()
        assert result == "success"
        assert call_count == 3
    
    def test_retry_exhausted(self):
        """リトライ回数を超えた場合の例外を確認"""
        call_count = 0
        
        @retry_on_error(max_retries=2, delay=0.1)
        def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise IOError("常に失敗")
        
        with pytest.raises(IOError):
            always_failing_func()
        assert call_count == 3  # 初回 + 2回リトライ


class TestFileOperations:
    """ファイル操作関連のテスト"""
    
    def test_safe_filename_conversion(self):
        """安全なファイル名への変換をテスト"""
        assert get_safe_filename("normal.otf") == "normal.otf"
        assert get_safe_filename("file:with*invalid?chars.otf") == "file_with_invalid_chars.otf"
        assert get_safe_filename("file/with\\slashes.otf") == "file_with_slashes.otf"
        assert get_safe_filename("..hidden..") == "hidden"
        assert get_safe_filename("   spaces   .otf") == "spaces   .otf"
        assert get_safe_filename("") == "unnamed_font"
    
    def test_cloud_storage_syncing_detection(self):
        """クラウドストレージの同期状態検出をテスト"""
        # iCloudファイル
        assert is_cloud_storage_syncing(Path("test.icloud"))
        assert is_cloud_storage_syncing(Path("/path/.icloud/file.otf"))
        
        # 一時ファイル
        assert is_cloud_storage_syncing(Path("file.tmp"))
        assert is_cloud_storage_syncing(Path("file.download"))
        assert is_cloud_storage_syncing(Path("file.partial"))
        assert is_cloud_storage_syncing(Path("file~"))
        
        # 通常のファイル
        assert not is_cloud_storage_syncing(Path("normal.otf"))


class TestFontValidation:
    """フォント検証のテスト"""
    
    def test_validate_nonexistent_file(self):
        """存在しないファイルの検証"""
        with pytest.raises(FontValidationError) as exc_info:
            validate_font_file_advanced(Path("/nonexistent/file.otf"))
        assert "存在しません" in str(exc_info.value)
        assert exc_info.value.hint is not None
    
    def test_validate_directory(self):
        """ディレクトリを指定した場合の検証"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FontValidationError) as exc_info:
                validate_font_file_advanced(Path(tmpdir))
            assert "ファイルではありません" in str(exc_info.value)
    
    def test_validate_invalid_extension(self):
        """無効な拡張子の検証"""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmpfile:
            with pytest.raises(FontValidationError) as exc_info:
                validate_font_file_advanced(Path(tmpfile.name))
            assert "サポートされていない" in str(exc_info.value)
    
    def test_validate_empty_file(self):
        """空ファイルの検証"""
        with tempfile.NamedTemporaryFile(suffix=".otf") as tmpfile:
            # ファイルを空にする
            tmpfile.truncate(0)
            tmpfile.flush()
            
            with pytest.raises(FontValidationError) as exc_info:
                validate_font_file_advanced(Path(tmpfile.name))
            assert "ファイルが空" in str(exc_info.value)
    
    def test_validate_valid_font(self):
        """有効なフォントファイルの検証"""
        with tempfile.NamedTemporaryFile(suffix=".otf") as tmpfile:
            # OTFヘッダーと追加データを書き込む（10KB以上にする）
            tmpfile.write(b'OTTO' + b'\x00' * (10 * 1024))
            tmpfile.flush()
            
            result = validate_font_file_advanced(Path(tmpfile.name))
            assert result["valid"] is True
            assert result["file_size_mb"] >= 0.01  # 10KB = 0.01MB
            assert not result["is_locked"]
    
    def test_validate_large_file_warning(self):
        """大きなファイルの警告"""
        with tempfile.NamedTemporaryFile(suffix=".otf") as tmpfile:
            # 101MBのダミーデータ
            tmpfile.write(b'OTTO' + b'\x00' * (101 * 1024 * 1024 - 4))
            tmpfile.flush()
            
            result = validate_font_file_advanced(Path(tmpfile.name))
            assert result["valid"] is True
            assert any("大きすぎます" in w for w in result["warnings"])


class TestDiskSpace:
    """ディスク容量チェックのテスト"""
    
    def test_check_disk_space_valid_path(self):
        """有効なパスでのディスク容量チェック"""
        result = check_disk_space(Path.home(), 1.0)
        assert "free_mb" in result
        assert "total_mb" in result
        assert "used_percent" in result
        assert "has_enough_space" in result
        assert result["free_mb"] > 0
        assert result["total_mb"] > 0
    
    def test_check_disk_space_invalid_path(self):
        """無効なパスでのディスク容量チェック（エラーハンドリング）"""
        result = check_disk_space(Path("/nonexistent/path"), 1.0)
        assert result["free_mb"] == -1
        assert result["has_enough_space"] is True  # 安全側に倒す


class TestBatchProcessing:
    """バッチ処理のテスト"""
    
    def test_batch_process_success(self):
        """正常なバッチ処理"""
        items = list(range(10))
        
        def process_func(item):
            return item * 2
        
        results = batch_process(items, process_func, batch_size=3)
        assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]
    
    def test_batch_process_with_errors(self):
        """エラーを含むバッチ処理"""
        items = list(range(5))
        
        def process_func(item):
            if item == 2:
                raise ValueError("テストエラー")
            return item * 2
        
        results = batch_process(items, process_func, batch_size=2)
        assert len(results) == 5
        assert results[0] == 0
        assert results[1] == 2
        assert "error" in results[2]
        assert results[3] == 6
        assert results[4] == 8
    
    def test_batch_process_with_progress(self):
        """進捗コールバック付きバッチ処理"""
        items = list(range(10))
        progress_calls = []
        
        def process_func(item):
            return item
        
        def progress_callback(current, total):
            progress_calls.append((current, total))
        
        batch_process(items, process_func, batch_size=3, 
                     progress_callback=progress_callback)
        
        assert len(progress_calls) == 10
        assert progress_calls[0] == (1, 10)
        assert progress_calls[-1] == (10, 10) 