"""adoptコマンドのテスト

~/Library/Fonts/ 内フォントを同期元フォルダに取り込む adopt コマンドのテスト。
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from src.commands.adopt import _is_excluded, adopt_command
from src.font_manager import FontManager

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _make_mock_fm_init(font_dir: Path):
    """FontManager.__init__ をモックする関数を返す"""
    def mock_init(self, use_cache: bool = True):
        self.font_install_dir = font_dir
        self.font_extensions = (".otf", ".ttf", ".OTF", ".TTF")
        self.use_cache = False
        self.cache = None
        self.max_font_size_mb = 200
        self.chunk_size = 8192
    return mock_init


def create_dummy_font(directory: Path, name: str) -> Path:
    """ダミーフォントファイルを作成"""
    font_path = directory / name
    font_path.write_bytes(b"dummy font data " + name.encode())
    return font_path


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def source_dir(tmp_path):
    """同期元ソースフォルダ"""
    d = tmp_path / "source"
    d.mkdir()
    return d


@pytest.fixture
def user_font_dir(tmp_path):
    """~/Library/Fonts/ 相当のフォルダ"""
    d = tmp_path / "Library" / "Fonts"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def config_with_one_source(tmp_path, source_dir, monkeypatch):
    """1ソースを持つ設定をセットアップ"""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    config_dir = home / ".fontsync"
    config_dir.mkdir()
    config_file = config_dir / "config.json"

    config_data = {
        "schema_version": 2,
        "sources": [
            {
                "id": "test-source-id",
                "label": "Test Source",
                "path": str(source_dir),
                "enabled": True,
            }
        ],
        "installed_fonts": {},
    }
    with open(config_file, "w") as f:
        json.dump(config_data, f)

    return {"home": home, "config_dir": config_dir, "source_dir": source_dir}


@pytest.fixture
def config_with_two_sources(tmp_path, monkeypatch):
    """2ソースを持つ設定をセットアップ"""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    source1 = tmp_path / "source1"
    source1.mkdir()
    source2 = tmp_path / "source2"
    source2.mkdir()

    config_dir = home / ".fontsync"
    config_dir.mkdir()
    config_file = config_dir / "config.json"

    config_data = {
        "schema_version": 2,
        "sources": [
            {"id": "id1", "label": "Source 1", "path": str(source1), "enabled": True},
            {"id": "id2", "label": "Source 2", "path": str(source2), "enabled": True},
        ],
        "installed_fonts": {},
    }
    with open(config_file, "w") as f:
        json.dump(config_data, f)

    return {"home": home, "source1": source1, "source2": source2}


# ---------------------------------------------------------------------------
# _is_excluded のテスト
# ---------------------------------------------------------------------------

class TestIsExcluded:
    """_is_excluded 関数のテスト"""

    def test_system_library_fonts_excluded(self, tmp_path):
        """/System/Library/Fonts/ へのシンボリックリンクは除外"""
        font = tmp_path / "SystemFont.otf"
        font.write_bytes(b"fake")
        with patch("os.path.realpath", return_value="/System/Library/Fonts/Helvetica.ttc"):
            assert _is_excluded(font) is True

    def test_library_fonts_excluded(self, tmp_path):
        """/Library/Fonts/ へのシンボリックリンクは除外"""
        font = tmp_path / "LibFont.otf"
        font.write_bytes(b"fake")
        with patch("os.path.realpath", return_value="/Library/Fonts/SomeFont.otf"):
            assert _is_excluded(font) is True

    def test_adobe_corysync_excluded(self, tmp_path):
        """Adobe CoreSync フォントは除外"""
        font = tmp_path / "AdobeFont.otf"
        font.write_bytes(b"fake")
        with patch(
            "os.path.realpath",
            return_value=(
                "/Users/user/Library/Application Support/Adobe/CoreSync"
                "/plugins/livetype/.r/SomeFont.otf"
            ),
        ):
            assert _is_excluded(font) is True

    def test_user_font_not_excluded(self, tmp_path):
        """通常のユーザーフォントは除外しない"""
        font = tmp_path / "MyFont.otf"
        font.write_bytes(b"fake")
        with patch("os.path.realpath", return_value=str(font)):
            assert _is_excluded(font) is False

    def test_cloud_drive_font_not_excluded(self, tmp_path):
        """クラウドドライブ内のフォントは除外しない"""
        font = tmp_path / "CloudFont.otf"
        font.write_bytes(b"fake")
        with patch(
            "os.path.realpath",
            return_value="/Users/user/Library/Mobile Documents/com~apple~CloudDocs/Fonts/CloudFont.otf",
        ):
            assert _is_excluded(font) is False


# ---------------------------------------------------------------------------
# adopt_command のテスト
# ---------------------------------------------------------------------------

class TestAdoptCommand:
    """adopt_command のテスト"""

    def test_dry_run_no_copy(self, config_with_one_source, user_font_dir, monkeypatch, capsys):
        """dry-run では実際のコピーは行わない"""
        create_dummy_font(user_font_dir, "MyFont.otf")
        source_dir = config_with_one_source["source_dir"]

        monkeypatch.setattr(FontManager, "__init__", _make_mock_fm_init(user_font_dir))

        adopt_command(source_id="test-source-id", dry_run=True, json_output=True)

        # ソースフォルダにファイルがコピーされていないこと
        assert not (source_dir / "MyFont.otf").exists()

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())
        assert result["success"] is True
        assert result["adopted"] == 0

    def test_copy_font(self, config_with_one_source, user_font_dir, monkeypatch, capsys):
        """フォントが正常にコピーされる"""
        create_dummy_font(user_font_dir, "MyFont.otf")
        source_dir = config_with_one_source["source_dir"]

        monkeypatch.setattr(FontManager, "__init__", _make_mock_fm_init(user_font_dir))

        adopt_command(source_id="test-source-id", dry_run=False, json_output=True)

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())

        assert result["success"] is True
        assert result["adopted"] == 1
        assert (source_dir / "MyFont.otf").exists()
        # 元ファイルが残っていること（コピーなので）
        assert (user_font_dir / "MyFont.otf").exists()

    def test_move_font(self, config_with_one_source, user_font_dir, monkeypatch, capsys):
        """--move でフォントが移動される（元ファイル削除）"""
        font = create_dummy_font(user_font_dir, "MyFont.otf")
        source_dir = config_with_one_source["source_dir"]

        monkeypatch.setattr(FontManager, "__init__", _make_mock_fm_init(user_font_dir))

        adopt_command(
            source_id="test-source-id",
            dry_run=False,
            json_output=True,
            move=True,
            yes=True,
        )

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())

        assert result["success"] is True
        assert result["adopted"] == 1
        assert (source_dir / "MyFont.otf").exists()
        # 元ファイルが削除されていること
        assert not font.exists()

    def test_exclude_system_symlink(self, config_with_one_source, user_font_dir, monkeypatch, capsys):
        """システムフォントへのシンボリックリンクは除外される"""
        create_dummy_font(user_font_dir, "SystemFont.otf")
        source_dir = config_with_one_source["source_dir"]

        monkeypatch.setattr(FontManager, "__init__", _make_mock_fm_init(user_font_dir))
        monkeypatch.setattr(
            "os.path.realpath",
            lambda p: "/System/Library/Fonts/SystemFont.otf"
            if "SystemFont" in str(p)
            else str(p),
        )

        adopt_command(source_id="test-source-id", dry_run=False, json_output=True)

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())

        assert result["adopted"] == 0
        assert not (source_dir / "SystemFont.otf").exists()

    def test_skip_existing_filename(self, config_with_one_source, user_font_dir, monkeypatch, capsys):
        """ソースに既存ファイルがある場合はスキップ"""
        create_dummy_font(user_font_dir, "ExistingFont.otf")
        source_dir = config_with_one_source["source_dir"]
        # ソースに同名ファイルを事前配置
        (source_dir / "ExistingFont.otf").write_bytes(b"already in source")

        monkeypatch.setattr(FontManager, "__init__", _make_mock_fm_init(user_font_dir))

        adopt_command(source_id="test-source-id", dry_run=False, json_output=True)

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())

        assert result["adopted"] == 0
        assert result["skipped"] == 1
        # ソース内のファイルが上書きされていないこと
        assert (source_dir / "ExistingFont.otf").read_bytes() == b"already in source"

    def test_json_output_structure(self, config_with_one_source, user_font_dir, monkeypatch, capsys):
        """JSON 出力のフィールド構造を確認"""
        create_dummy_font(user_font_dir, "FontA.otf")
        create_dummy_font(user_font_dir, "FontB.ttf")
        source_dir = config_with_one_source["source_dir"]
        # FontB はソースに既存
        (source_dir / "FontB.ttf").write_bytes(b"existing")

        monkeypatch.setattr(FontManager, "__init__", _make_mock_fm_init(user_font_dir))

        adopt_command(source_id="test-source-id", dry_run=False, json_output=True)

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())

        assert "success" in result
        assert "adopted" in result
        assert "skipped" in result
        assert "errors" in result
        assert "fonts" in result
        assert isinstance(result["fonts"], list)
        assert result["adopted"] == 1
        assert result["skipped"] == 1

        # fonts リストに action フィールドがあること
        for font_entry in result["fonts"]:
            assert "name" in font_entry
            assert "action" in font_entry

    def test_multiple_sources_without_source_option_errors(
        self, config_with_two_sources, user_font_dir, monkeypatch, capsys
    ):
        """複数ソースがある場合に --source 未指定でエラー"""
        monkeypatch.setattr(FontManager, "__init__", _make_mock_fm_init(user_font_dir))

        with pytest.raises(typer.Exit):
            adopt_command(source_id=None, dry_run=False, json_output=True)

        captured = capsys.readouterr()
        output = captured.out.strip()
        assert output  # 何か出力されること
        result = json.loads(output)
        assert result["success"] is False

    def test_single_source_auto_selected(self, config_with_one_source, user_font_dir, monkeypatch, capsys):
        """ソースが1つの場合は --source 未指定でも自動選択"""
        create_dummy_font(user_font_dir, "MyFont.otf")
        source_dir = config_with_one_source["source_dir"]

        monkeypatch.setattr(FontManager, "__init__", _make_mock_fm_init(user_font_dir))

        # --source を指定しない
        adopt_command(source_id=None, dry_run=False, json_output=True)

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())

        assert result["success"] is True
        assert result["adopted"] == 1
        assert (source_dir / "MyFont.otf").exists()

    def test_move_with_json_requires_yes(self, config_with_one_source, user_font_dir, monkeypatch, capsys):
        """--move --json の組み合わせでは --yes が必要"""
        create_dummy_font(user_font_dir, "MyFont.otf")
        monkeypatch.setattr(FontManager, "__init__", _make_mock_fm_init(user_font_dir))

        with pytest.raises(typer.Exit):
            adopt_command(
                source_id="test-source-id",
                dry_run=False,
                json_output=True,
                move=True,
                yes=False,  # --yes なし
            )

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())
        assert result["success"] is False

    def test_adopt_multiple_fonts(self, config_with_one_source, user_font_dir, monkeypatch, capsys):
        """複数フォントを一括取り込み"""
        create_dummy_font(user_font_dir, "FontA.otf")
        create_dummy_font(user_font_dir, "FontB.ttf")
        create_dummy_font(user_font_dir, "FontC.OTF")
        source_dir = config_with_one_source["source_dir"]

        monkeypatch.setattr(FontManager, "__init__", _make_mock_fm_init(user_font_dir))

        adopt_command(source_id="test-source-id", dry_run=False, json_output=True)

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())

        assert result["success"] is True
        assert result["adopted"] == 3
        assert (source_dir / "FontA.otf").exists()
        assert (source_dir / "FontB.ttf").exists()
        assert (source_dir / "FontC.OTF").exists()
