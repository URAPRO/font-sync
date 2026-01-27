"""ConfigManagerのテスト"""

import json
import os
from pathlib import Path

import pytest

from src.config import ConfigManager


class TestConfigManager:
    """ConfigManagerクラスのテスト"""

    def test_init(self, mock_home_dir: Path):
        """初期化のテスト"""
        config_manager = ConfigManager()

        assert config_manager.config_dir == mock_home_dir / ".fontsync"
        assert config_manager.config_file == mock_home_dir / ".fontsync" / "config.json"
        assert config_manager.config == {}

    def test_initialize_config(self, mock_home_dir: Path, mock_sync_folder: Path):
        """設定初期化のテスト"""
        config_manager = ConfigManager()
        config_manager.initialize_config(str(mock_sync_folder))

        # 設定ファイルが作成されていることを確認
        assert config_manager.config_file.exists()

        # 設定内容を確認
        assert config_manager.config["sync_folder"] == str(mock_sync_folder)
        assert config_manager.config["installed_fonts"] == {}
        assert "created_at" in config_manager.config
        assert config_manager.config["version"] == "1.0"

    def test_load_config(self, mock_home_dir: Path, sample_config: Path):
        """設定読み込みのテスト"""
        config_manager = ConfigManager()
        loaded_config = config_manager.load_config()

        assert "sync_folder" in loaded_config
        assert "installed_fonts" in loaded_config
        assert loaded_config["version"] == "1.0"

    def test_load_config_file_not_found(self, mock_home_dir: Path):
        """設定ファイルが存在しない場合のテスト"""
        config_manager = ConfigManager()

        with pytest.raises(FileNotFoundError):
            config_manager.load_config()

    def test_save_config(self, mock_home_dir: Path):
        """設定保存のテスト"""
        config_manager = ConfigManager()
        config_manager.config = {
            "sync_folder": "/test/path",
            "installed_fonts": {},
            "version": "1.0"
        }

        config_manager.save_config()

        # ファイルが作成されていることを確認
        assert config_manager.config_file.exists()

        # 保存された内容を確認
        with open(config_manager.config_file, "r") as f:
            saved_config = json.load(f)

        assert saved_config == config_manager.config

    def test_get_sync_folder(self, mock_home_dir: Path, sample_config: Path):
        """同期元フォルダ取得のテスト"""
        config_manager = ConfigManager()
        config_manager.load_config()

        sync_folder = config_manager.get_sync_folder()
        assert sync_folder is not None
        assert "shared-fonts" in sync_folder

    def test_set_sync_folder(self, mock_home_dir: Path, monkeypatch):
        """同期元フォルダ設定のテスト"""
        config_manager = ConfigManager()
        test_path = "~/test/fonts"

        # os.path.expanduserをモック
        def mock_expanduser(path):
            if path.startswith("~/"):
                return str(mock_home_dir / path[2:])
            return path

        monkeypatch.setattr(os.path, "expanduser", mock_expanduser)

        config_manager.set_sync_folder(test_path)

        # パスが展開されていることを確認
        expected_path = str(mock_home_dir / "test/fonts")
        assert config_manager.config["sync_folder"] == expected_path

    def test_add_installed_font(self, mock_home_dir: Path):
        """インストール済みフォント追加のテスト"""
        config_manager = ConfigManager()
        font_name = "TestFont.otf"
        font_hash = "abc123"

        config_manager.add_installed_font(font_name, font_hash)

        # フォント情報が追加されていることを確認
        assert font_name in config_manager.config["installed_fonts"]
        assert config_manager.config["installed_fonts"][font_name]["hash"] == font_hash
        assert "installed_at" in config_manager.config["installed_fonts"][font_name]

    def test_remove_installed_font(self, mock_home_dir: Path):
        """インストール済みフォント削除のテスト"""
        config_manager = ConfigManager()
        font_name = "TestFont.otf"

        # まず追加
        config_manager.add_installed_font(font_name, "abc123")
        assert font_name in config_manager.config["installed_fonts"]

        # 削除
        config_manager.remove_installed_font(font_name)
        assert font_name not in config_manager.config["installed_fonts"]

    def test_is_font_installed(self, mock_home_dir: Path):
        """フォントインストール状態確認のテスト"""
        config_manager = ConfigManager()
        font_name = "TestFont.otf"

        # インストール前
        assert not config_manager.is_font_installed(font_name)

        # インストール後
        config_manager.add_installed_font(font_name, "abc123")
        assert config_manager.is_font_installed(font_name)

    def test_get_font_hash(self, mock_home_dir: Path):
        """フォントハッシュ取得のテスト"""
        config_manager = ConfigManager()
        font_name = "TestFont.otf"
        font_hash = "abc123"

        # インストール前
        assert config_manager.get_font_hash(font_name) is None

        # インストール後
        config_manager.add_installed_font(font_name, font_hash)
        assert config_manager.get_font_hash(font_name) == font_hash

    def test_config_exists(self, mock_home_dir: Path):
        """設定ファイル存在確認のテスト"""
        config_manager = ConfigManager()

        # 存在しない場合
        assert not config_manager.config_exists()

        # 存在する場合
        config_manager.initialize_config("/test/path")
        assert config_manager.config_exists()
