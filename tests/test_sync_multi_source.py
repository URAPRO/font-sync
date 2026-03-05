"""sync コマンドのmulti-source対応テスト"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.main import app


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def multi_source_env(mock_home_dir: Path, monkeypatch, tmp_path):
    """マルチソース環境セットアップ"""
    from src.font_manager import FontManager

    # フォントインストールディレクトリをモック
    font_install_dir = tmp_path / "Library" / "Fonts"
    font_install_dir.mkdir(parents=True)

    original_fm_init = FontManager.__init__

    def mock_fm_init(self):
        original_fm_init(self)
        self.font_install_dir = font_install_dir

    monkeypatch.setattr(FontManager, "__init__", mock_fm_init)

    # 2つの同期元フォルダを作成
    source1 = tmp_path / "source1"
    source1.mkdir()
    source2 = tmp_path / "source2"
    source2.mkdir()

    # config.json (v2) を作成
    config_dir = mock_home_dir / ".fontsync"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    config_data = {
        "schema_version": 2,
        "sources": [
            {
                "id": "source-id-1",
                "label": "Source 1",
                "path": str(source1),
                "enabled": True,
            },
            {
                "id": "source-id-2",
                "label": "Source 2",
                "path": str(source2),
                "enabled": True,
            },
        ],
        "installed_fonts": {},
        "version": "1.0",
    }
    with open(config_file, "w") as f:
        json.dump(config_data, f)

    return {
        "source1": source1,
        "source2": source2,
        "config_file": config_file,
        "font_install_dir": font_install_dir,
    }


class TestSyncCommandMultiSource:
    """sync コマンドのマルチソース対応テスト"""

    def test_sync_json_output_includes_sources_key(
        self, runner, multi_source_env
    ):
        """--json出力にsourcesフィールドが含まれる"""
        result = runner.invoke(app, ["sync", "--json"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "sources" in output

    def test_sync_json_output_each_source_has_source_id(
        self, runner, multi_source_env
    ):
        """--json出力のsourcesの各エントリにsource_idが含まれる"""
        result = runner.invoke(app, ["sync", "--json"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert len(output["sources"]) == 2
        for src in output["sources"]:
            assert "source_id" in src

    def test_sync_with_source_option_syncs_only_specified(
        self, runner, multi_source_env
    ):
        """--source指定時はそのソースのみ同期する"""
        # source1にダミーフォントを追加
        font_file = multi_source_env["source1"] / "TestFont.otf"
        font_file.write_bytes(b"OTF dummy data")

        result = runner.invoke(app, ["sync", "--json", "--source", "source-id-1"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        # sourcesの結果は1件のみ
        assert len(output["sources"]) == 1
        assert output["sources"][0]["source_id"] == "source-id-1"

    def test_sync_with_invalid_source_option_fails(
        self, runner, multi_source_env
    ):
        """存在しない--sourceを指定するとエラー"""
        result = runner.invoke(app, ["sync", "--json", "--source", "nonexistent-id"])
        assert result.exit_code != 0
        output = json.loads(result.output)
        assert output["success"] is False

    def test_sync_skips_disabled_sources(
        self, runner, multi_source_env
    ):
        """disabledなソースはスキップされる"""
        import json

        # source2をdisabledに変更
        with open(multi_source_env["config_file"]) as f:
            config = json.load(f)
        for src in config["sources"]:
            if src["id"] == "source-id-2":
                src["enabled"] = False
        with open(multi_source_env["config_file"], "w") as f:
            json.dump(config, f)

        result = runner.invoke(app, ["sync", "--json"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        source_ids = [s["source_id"] for s in output["sources"]]
        assert "source-id-1" in source_ids
        assert "source-id-2" not in source_ids

    def test_sync_v1_config_is_migrated_and_synced(
        self, runner, mock_home_dir: Path, monkeypatch, tmp_path
    ):
        """v1 config (sync_folder) でも正常に動作する（マイグレーション後）"""
        from src.font_manager import FontManager

        font_install_dir = tmp_path / "Library" / "Fonts"
        font_install_dir.mkdir(parents=True)

        original_fm_init = FontManager.__init__

        def mock_fm_init(self):
            original_fm_init(self)
            self.font_install_dir = font_install_dir

        monkeypatch.setattr(FontManager, "__init__", mock_fm_init)

        sync_folder = tmp_path / "shared-fonts"
        sync_folder.mkdir()

        config_dir = mock_home_dir / ".fontsync"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        v1_config = {
            "sync_folder": str(sync_folder),
            "installed_fonts": {},
            "version": "1.0",
        }
        with open(config_file, "w") as f:
            json.dump(v1_config, f)

        result = runner.invoke(app, ["sync", "--json"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["success"] is True
        assert "sources" in output
