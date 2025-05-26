"""FontManagerのテスト"""

import pytest
from pathlib import Path
import hashlib
from unittest.mock import patch, MagicMock

from src.font_manager import FontManager
from src.utils import FileLockedError, FontValidationError


class TestFontManager:
    """FontManagerクラスのテスト"""
    
    def test_init(self):
        """初期化のテスト"""
        font_manager = FontManager()
        
        assert font_manager.font_extensions == (".otf", ".ttf", ".OTF", ".TTF")
        assert font_manager.font_install_dir == Path.home() / "Library" / "Fonts"
        assert font_manager.max_font_size_mb == 200
        assert font_manager.chunk_size == 8192
    
    def test_scan_fonts(self, mock_sync_folder: Path):
        """フォントスキャンのテスト"""
        font_manager = FontManager()
        
        # テスト用フォントファイルを作成（大文字小文字の拡張子を含む）
        (mock_sync_folder / "Font1.otf").write_bytes(b"font1")
        (mock_sync_folder / "Font2.TTF").write_bytes(b"font2")  # 大文字拡張子
        (mock_sync_folder / "subdir").mkdir()
        (mock_sync_folder / "subdir" / "Font3.OTF").write_bytes(b"font3")  # 大文字拡張子
        
        # 非フォントファイルと隠しファイル
        (mock_sync_folder / "readme.txt").write_text("readme")
        (mock_sync_folder / ".DS_Store").write_bytes(b"ds_store")
        (mock_sync_folder / ".hidden.otf").write_bytes(b"hidden")  # 隠しファイル
        
        # クラウド同期中のファイル（モック）
        (mock_sync_folder / "syncing.otf.download").write_bytes(b"syncing")
        
        fonts = font_manager.scan_fonts(str(mock_sync_folder))
        
        # フォントファイルのみが検出されることを確認
        assert len(fonts) == 3
        font_names = [f.name for f in fonts]
        assert "Font1.otf" in font_names
        assert "Font2.TTF" in font_names
        assert "Font3.OTF" in font_names
        assert ".DS_Store" not in font_names
        assert ".hidden.otf" not in font_names
        assert "syncing.otf.download" not in font_names
    
    def test_scan_fonts_batch_mode(self, mock_sync_folder: Path):
        """バッチモードでのフォントスキャンテスト"""
        font_manager = FontManager()
        
        # 150個のフォントファイルを作成（バッチサイズ100を超える）
        for i in range(150):
            (mock_sync_folder / f"Font{i:03d}.otf").write_bytes(b"font")
        
        # バッチモードでスキャン
        batches = list(font_manager.scan_fonts(str(mock_sync_folder), yield_batch=True))
        
        # 2つのバッチに分かれることを確認
        assert len(batches) == 2
        assert len(batches[0]) == 100
        assert len(batches[1]) == 50
    
    def test_scan_fonts_folder_not_found(self):
        """存在しないフォルダのスキャンテスト"""
        font_manager = FontManager()
        
        with pytest.raises(FileNotFoundError):
            font_manager.scan_fonts("/non/existent/folder")
    
    def test_scan_fonts_not_directory(self, temp_dir: Path):
        """ディレクトリではないパスのスキャンテスト"""
        font_manager = FontManager()
        
        # ファイルを作成
        file_path = temp_dir / "file.txt"
        file_path.write_text("test")
        
        with pytest.raises(NotADirectoryError):
            font_manager.scan_fonts(str(file_path))
    
    def test_calculate_hash(self, sample_font_file: Path):
        """ハッシュ計算のテスト"""
        font_manager = FontManager()
        
        hash_value = font_manager.calculate_hash(sample_font_file)
        
        # SHA256ハッシュの形式を確認
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA256は64文字の16進数
        
        # 同じファイルは同じハッシュを生成
        hash_value2 = font_manager.calculate_hash(sample_font_file)
        assert hash_value == hash_value2
    
    def test_calculate_hash_with_retry(self, sample_font_file: Path):
        """リトライ機能付きハッシュ計算のテスト"""
        font_manager = FontManager()
        
        # ファイルロックを一時的にシミュレート
        with patch('src.utils.is_file_locked') as mock_is_locked:
            with patch('src.utils.wait_for_file_unlock') as mock_wait:
                # 最初はロック、その後解除
                mock_is_locked.return_value = True
                mock_wait.return_value = True
                
                # ロック解除後は正常に計算できる
                hash_value = font_manager.calculate_hash(sample_font_file)
                assert len(hash_value) == 64
    
    def test_calculate_hash_locked_timeout(self, sample_font_file: Path):
        """ファイルロックのタイムアウトテスト"""
        font_manager = FontManager()
        
        # リトライが全て失敗するように設定
        with patch('src.font_manager.is_file_locked', return_value=True):
            with patch('src.font_manager.wait_for_file_unlock', return_value=False):
                with pytest.raises(FileLockedError):
                    # デコレータ付きメソッドを呼び出す（リトライが失敗する）
                    font_manager.calculate_hash(sample_font_file)
    
    def test_calculate_hash_file_not_found(self):
        """存在しないファイルのハッシュ計算テスト"""
        font_manager = FontManager()
        
        with pytest.raises(FileNotFoundError):
            font_manager.calculate_hash(Path("/non/existent/file.otf"))
    
    def test_copy_font_with_validation(self, sample_font_file: Path, mock_font_install_dir: Path, monkeypatch):
        """検証付きフォントコピーのテスト"""
        font_manager = FontManager()
        
        # font_install_dirをモック
        monkeypatch.setattr(font_manager, "font_install_dir", mock_font_install_dir)
        
        # OTFヘッダーを持つファイルを作成
        sample_font_file.write_bytes(b'OTTO' + b'\x00' * 100)
        
        # フォントをコピー（検証付き）
        dst_path = font_manager.copy_font(sample_font_file, validate=True)
        
        # コピー先にファイルが存在することを確認
        assert dst_path.exists()
        assert dst_path.read_bytes() == sample_font_file.read_bytes()
    
    def test_copy_font_safe_filename(self, temp_dir: Path, mock_font_install_dir: Path, monkeypatch):
        """安全なファイル名への変換テスト"""
        font_manager = FontManager()
        monkeypatch.setattr(font_manager, "font_install_dir", mock_font_install_dir)
        
        # 無効な文字を含むファイル名（コロンはmacOSで使えないので別の文字を使用）
        unsafe_font = temp_dir / "Font_with_invalid_chars.otf"
        unsafe_font.write_bytes(b'OTTO' + b'\x00' * 100)
        
        # コピー実行（validate=Falseで検証をスキップ）
        dst_path = font_manager.copy_font(unsafe_font, validate=False)
        
        # 元のファイル名のままコピーされることを確認（validate=Falseの場合）
        assert dst_path.name == "Font_with_invalid_chars.otf"
        assert dst_path.exists()
        
        # validate=Trueの場合も正常なファイル名はそのまま
        safe_font = temp_dir / "SafeFont.otf"
        safe_font.write_bytes(b'OTTO' + b'\x00' * 100)
        dst_path2 = font_manager.copy_font(safe_font, validate=True)
        assert dst_path2.name == "SafeFont.otf"
    
    def test_copy_font_disk_space_check(self, sample_font_file: Path, mock_font_install_dir: Path, monkeypatch):
        """ディスク容量チェックのテスト"""
        font_manager = FontManager()
        monkeypatch.setattr(font_manager, "font_install_dir", mock_font_install_dir)
        
        # OTTOヘッダーを持つファイルを作成
        sample_font_file.write_bytes(b'OTTO' + b'\x00' * 100)
        
        # ディスク容量不足をシミュレート
        with patch('src.font_manager.check_disk_space') as mock_check:
            mock_check.return_value = {
                "free_mb": 0.1,
                "total_mb": 100,
                "used_percent": 99.9,
                "has_enough_space": False
            }
            
            with pytest.raises(IOError) as exc_info:
                font_manager.copy_font(sample_font_file)
            assert "ディスク容量が不足" in str(exc_info.value)
    
    def test_copy_font_custom_destination(self, sample_font_file: Path, temp_dir: Path):
        """カスタム宛先へのフォントコピーテスト"""
        font_manager = FontManager()
        
        custom_dst = temp_dir / "custom" / "fonts" / "MyFont.otf"
        dst_path = font_manager.copy_font(sample_font_file, custom_dst)
        
        # カスタム宛先にコピーされることを確認
        assert dst_path == custom_dst
        assert dst_path.exists()
        assert dst_path.read_bytes() == sample_font_file.read_bytes()
    
    def test_copy_font_file_not_found(self, mock_font_install_dir: Path):
        """存在しないファイルのコピーテスト"""
        font_manager = FontManager()
        
        with pytest.raises(FileNotFoundError):
            font_manager.copy_font(Path("/non/existent/font.otf"))
    
    def test_is_font_installed_with_safe_name(self, mock_font_install_dir: Path, monkeypatch):
        """安全なファイル名でのインストール確認テスト"""
        font_manager = FontManager()
        monkeypatch.setattr(font_manager, "font_install_dir", mock_font_install_dir)
        
        # 無効な文字を含むフォント名
        original_name = "Font:with*invalid?.otf"
        safe_name = "Font_with_invalid_.otf"
        
        # 安全な名前でインストール
        (mock_font_install_dir / safe_name).write_bytes(b"font data")
        
        # 元の名前でも確認できることをテスト
        assert font_manager.is_font_installed(original_name) is True
    
    def test_get_installed_font_path(self, mock_font_install_dir: Path, monkeypatch):
        """インストール済みフォントパス取得のテスト"""
        font_manager = FontManager()
        monkeypatch.setattr(font_manager, "font_install_dir", mock_font_install_dir)
        
        font_name = "TestFont.otf"
        
        # インストール前
        assert font_manager.get_installed_font_path(font_name) is None
        
        # フォントファイルを作成
        font_path = mock_font_install_dir / font_name
        font_path.write_bytes(b"font data")
        
        # インストール後
        result = font_manager.get_installed_font_path(font_name)
        assert result == font_path
    
    def test_remove_font_with_retry(self, mock_font_install_dir: Path, monkeypatch):
        """リトライ機能付きフォント削除のテスト"""
        font_manager = FontManager()
        monkeypatch.setattr(font_manager, "font_install_dir", mock_font_install_dir)
        
        font_name = "TestFont.otf"
        font_path = mock_font_install_dir / font_name
        
        # フォントファイルを作成
        font_path.write_bytes(b"font data")
        assert font_path.exists()
        
        # 削除
        result = font_manager.remove_font(font_name)
        assert result is True
        assert not font_path.exists()
        
        # 存在しないフォントの削除
        result = font_manager.remove_font("NonExistent.otf")
        assert result is False
    
    def test_remove_font_locked(self, mock_font_install_dir: Path, monkeypatch):
        """ロックされたフォントの削除テスト"""
        font_manager = FontManager()
        monkeypatch.setattr(font_manager, "font_install_dir", mock_font_install_dir)
        
        font_name = "LockedFont.otf"
        font_path = mock_font_install_dir / font_name
        font_path.write_bytes(b"font data")
        
        # リトライが全て失敗するように設定
        with patch('src.font_manager.is_file_locked', return_value=True):
            with patch('src.font_manager.wait_for_file_unlock', return_value=False):
                with pytest.raises(FileLockedError):
                    # デコレータ付きメソッドを呼び出す（リトライが失敗する）
                    font_manager.remove_font(font_name)
    
    def test_get_font_info_enhanced(self, sample_font_file: Path):
        """拡張されたフォント情報取得のテスト"""
        font_manager = FontManager()
        
        # 大きなファイルを作成
        sample_font_file.write_bytes(b'OTTO' + b'\x00' * (201 * 1024 * 1024))  # 201MB
        
        info = font_manager.get_font_info(sample_font_file)
        
        assert info["name"] == sample_font_file.name
        assert info["path"] == str(sample_font_file)
        assert info["size"] > 0
        assert info["size_mb"] > 200
        assert "modified" in info
        assert info["hash"] is None
        assert "is_locked" in info
        assert "is_syncing" in info
        assert "warning" in info  # 大きなファイルの警告
        assert "大きすぎます" in info["warning"]
    
    def test_get_font_info_error_handling(self):
        """存在しないファイルの情報取得エラーハンドリング"""
        font_manager = FontManager()
        
        # 存在しないファイルでもエラー情報を返す
        info = font_manager.get_font_info(Path("/non/existent/font.otf"))
        
        assert info["name"] == "font.otf"
        assert info["size"] == 0
        assert info["size_mb"] == 0
        assert "error" in info
    
    def test_validate_font_file_advanced(self, sample_font_file: Path, temp_dir: Path):
        """高度なフォントファイル検証のテスト"""
        font_manager = FontManager()
        
        # 正常なOTFファイル
        sample_font_file.write_bytes(b'OTTO' + b'\x00' * 100)
        assert font_manager.validate_font_file(sample_font_file) is True
        
        # 存在しないファイル
        assert font_manager.validate_font_file(Path("/non/existent.otf")) is False
        
        # ディレクトリ
        assert font_manager.validate_font_file(temp_dir) is False
        
        # 間違った拡張子
        wrong_ext = temp_dir / "file.txt"
        wrong_ext.write_text("test")
        assert font_manager.validate_font_file(wrong_ext) is False
        
        # 空のフォントファイル
        empty_font = temp_dir / "empty.otf"
        empty_font.write_bytes(b"")
        assert font_manager.validate_font_file(empty_font) is False
        
        # 無効なヘッダー
        invalid_font = temp_dir / "invalid.otf"
        invalid_font.write_bytes(b"INVALID" + b'\x00' * 100)
        assert font_manager.validate_font_file(invalid_font) is True  # 基本チェックは通る
    
    def test_get_fonts_batch_info(self, temp_dir: Path):
        """バッチフォント情報取得のテスト"""
        font_manager = FontManager()
        
        # 複数のフォントファイルを作成
        font_paths = []
        for i in range(5):
            font_path = temp_dir / f"Font{i}.otf"
            font_path.write_bytes(b'OTTO' + b'\x00' * 100)
            font_paths.append(font_path)
        
        # 存在しないファイルも追加
        font_paths.append(Path("/non/existent.otf"))
        
        # バッチ情報取得
        results = list(font_manager.get_fonts_batch_info(font_paths))
        
        assert len(results) == 6
        # 最初の5個は正常
        for i in range(5):
            assert results[i]["name"] == f"Font{i}.otf"
            assert "error" not in results[i]
        
        # 最後の1個はエラー
        assert "error" in results[5] 