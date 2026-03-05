"""ConfigManager multi-source機能のテスト"""

import json
import uuid
from pathlib import Path

from src.config import ConfigManager


class TestConfigManagerMultiSource:
    """multi-source対応のConfigManagerテスト"""

    def test_get_sources_returns_empty_list_initially(self, mock_home_dir: Path):
        """sourcesが未設定のときget_sourcesは空リストを返す"""
        config_manager = ConfigManager()
        config_manager.config = {}
        assert config_manager.get_sources() == []

    def test_add_source_appends_to_sources(self, mock_home_dir: Path):
        """add_sourceはsources[]に新しいエントリを追加する"""
        config_manager = ConfigManager()
        config_manager.config = {}
        config_manager.add_source("個人 iCloud", "/Users/test/iCloud/Fonts")
        sources = config_manager.get_sources()
        assert len(sources) == 1
        assert sources[0]["label"] == "個人 iCloud"
        assert sources[0]["path"] == "/Users/test/iCloud/Fonts"
        assert sources[0]["enabled"] is True

    def test_add_source_returns_source_with_id(self, mock_home_dir: Path):
        """add_sourceはidを持つsourceオブジェクトを返す"""
        config_manager = ConfigManager()
        config_manager.config = {}
        source = config_manager.add_source("Studio 共有", "/Volumes/shared/fonts")
        assert "id" in source
        assert len(source["id"]) > 0
        # UUIDフォーマットの確認
        uuid.UUID(source["id"])  # ValueError if invalid

    def test_add_source_multiple_creates_unique_ids(self, mock_home_dir: Path):
        """複数のadd_sourceで各エントリがユニークなidを持つ"""
        config_manager = ConfigManager()
        config_manager.config = {}
        s1 = config_manager.add_source("Source 1", "/path/1")
        s2 = config_manager.add_source("Source 2", "/path/2")
        assert s1["id"] != s2["id"]

    def test_remove_source_removes_by_id(self, mock_home_dir: Path):
        """remove_sourceはidで指定したソースを削除する"""
        config_manager = ConfigManager()
        config_manager.config = {}
        source = config_manager.add_source("テスト", "/path/test")
        source_id = source["id"]
        result = config_manager.remove_source(source_id)
        assert result is True
        assert config_manager.get_sources() == []

    def test_remove_source_returns_false_for_missing_id(self, mock_home_dir: Path):
        """存在しないidのremove_sourceはFalseを返す"""
        config_manager = ConfigManager()
        config_manager.config = {"sources": []}
        result = config_manager.remove_source("nonexistent-id")
        assert result is False

    def test_remove_source_keeps_other_sources(self, mock_home_dir: Path):
        """remove_sourceは指定以外のソースを削除しない"""
        config_manager = ConfigManager()
        config_manager.config = {}
        s1 = config_manager.add_source("Source 1", "/path/1")
        s2 = config_manager.add_source("Source 2", "/path/2")
        config_manager.remove_source(s1["id"])
        sources = config_manager.get_sources()
        assert len(sources) == 1
        assert sources[0]["id"] == s2["id"]

    def test_update_source_updates_label(self, mock_home_dir: Path):
        """update_sourceはlabelを更新できる"""
        config_manager = ConfigManager()
        config_manager.config = {}
        source = config_manager.add_source("旧ラベル", "/path")
        result = config_manager.update_source(source["id"], {"label": "新ラベル"})
        assert result is True
        assert config_manager.get_sources()[0]["label"] == "新ラベル"

    def test_update_source_updates_enabled(self, mock_home_dir: Path):
        """update_sourceはenabledを更新できる"""
        config_manager = ConfigManager()
        config_manager.config = {}
        source = config_manager.add_source("Source", "/path")
        config_manager.update_source(source["id"], {"enabled": False})
        assert config_manager.get_sources()[0]["enabled"] is False

    def test_update_source_returns_false_for_missing_id(self, mock_home_dir: Path):
        """存在しないidのupdate_sourceはFalseを返す"""
        config_manager = ConfigManager()
        config_manager.config = {"sources": []}
        result = config_manager.update_source("nonexistent", {"label": "test"})
        assert result is False

    def test_get_enabled_sources_returns_only_enabled(self, mock_home_dir: Path):
        """get_enabled_sourcesはenabledがTrueのソースのみ返す"""
        config_manager = ConfigManager()
        config_manager.config = {}
        s1 = config_manager.add_source("Enabled", "/path/1")
        s2 = config_manager.add_source("Disabled", "/path/2")
        config_manager.update_source(s2["id"], {"enabled": False})
        enabled = config_manager.get_enabled_sources()
        assert len(enabled) == 1
        assert enabled[0]["id"] == s1["id"]

    def test_get_enabled_sources_returns_all_when_all_enabled(self, mock_home_dir: Path):
        """全てenabledの場合、全ソースを返す"""
        config_manager = ConfigManager()
        config_manager.config = {}
        config_manager.add_source("Source 1", "/path/1")
        config_manager.add_source("Source 2", "/path/2")
        enabled = config_manager.get_enabled_sources()
        assert len(enabled) == 2


class TestConfigManagerMigration:
    """v1→v2マイグレーションのテスト"""

    def test_load_config_migrates_v1_sync_folder_to_sources(
        self, mock_home_dir: Path, mock_config_dir: Path
    ):
        """v1 config（sync_folderのみ）をロードするとsources[]に変換される"""
        config_file = mock_config_dir / "config.json"
        v1_config = {
            "sync_folder": "/Users/test/iCloud/Fonts",
            "installed_fonts": {},
            "version": "1.0"
        }
        with open(config_file, "w") as f:
            json.dump(v1_config, f)

        config_manager = ConfigManager()
        config_manager.load_config()

        sources = config_manager.get_sources()
        assert len(sources) == 1
        assert sources[0]["path"] == "/Users/test/iCloud/Fonts"
        assert sources[0]["enabled"] is True
        assert config_manager.config.get("schema_version") == 2

    def test_load_config_migration_preserves_sync_folder(
        self, mock_home_dir: Path, mock_config_dir: Path
    ):
        """マイグレーション後もsync_folderフィールドは保持される（後方互換）"""
        config_file = mock_config_dir / "config.json"
        v1_config = {
            "sync_folder": "/Users/test/shared",
            "installed_fonts": {},
            "version": "1.0"
        }
        with open(config_file, "w") as f:
            json.dump(v1_config, f)

        config_manager = ConfigManager()
        config_manager.load_config()

        # sync_folderは残す（後方互換のため）
        assert config_manager.config.get("sync_folder") == "/Users/test/shared"

    def test_load_config_v2_is_not_migrated(
        self, mock_home_dir: Path, mock_config_dir: Path
    ):
        """既にv2のconfigはマイグレーションされない（冪等性）"""
        source_id = str(uuid.uuid4())
        config_file = mock_config_dir / "config.json"
        v2_config = {
            "schema_version": 2,
            "sources": [
                {
                    "id": source_id,
                    "label": "既存ソース",
                    "path": "/path/existing",
                    "enabled": True
                }
            ],
            "installed_fonts": {},
            "version": "1.0"
        }
        with open(config_file, "w") as f:
            json.dump(v2_config, f)

        config_manager = ConfigManager()
        config_manager.load_config()

        sources = config_manager.get_sources()
        assert len(sources) == 1
        assert sources[0]["id"] == source_id

    def test_load_config_no_sync_folder_no_migration(
        self, mock_home_dir: Path, mock_config_dir: Path
    ):
        """sync_folderなしのv1 configはsourcesが空のまま"""
        config_file = mock_config_dir / "config.json"
        v1_config = {
            "installed_fonts": {},
            "version": "1.0"
        }
        with open(config_file, "w") as f:
            json.dump(v1_config, f)

        config_manager = ConfigManager()
        config_manager.load_config()

        sources = config_manager.get_sources()
        assert sources == []
