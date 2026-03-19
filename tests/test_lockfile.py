"""lockfile モジュールのテスト"""

import json
from pathlib import Path

import pytest

from src.lockfile import (
    FontopsLock,
    LockFont,
    LockStyle,
    load_lock,
    save_lock,
)


class TestLockStyle:
    """LockStyle dataclass のテスト"""

    def test_lockstyle_creation(self):
        """LockStyle が name フィールドを持つこと"""
        style = LockStyle(name="Regular")
        assert style.name == "Regular"

    def test_lockstyle_to_dict(self):
        """to_dict() が正しい辞書を返すこと"""
        style = LockStyle(name="Bold")
        assert style.to_dict() == {"name": "Bold"}

    def test_lockstyle_from_dict(self):
        """from_dict() が辞書から LockStyle を生成すること"""
        style = LockStyle.from_dict({"name": "Italic"})
        assert style.name == "Italic"

    def test_lockstyle_roundtrip(self):
        """to_dict() → from_dict() のラウンドトリップが一致すること"""
        original = LockStyle(name="Bold Italic")
        restored = LockStyle.from_dict(original.to_dict())
        assert restored.name == original.name

    def test_lockstyle_from_dict_invalid_missing_name(self):
        """name フィールドがない場合 ValueError を raise すること"""
        with pytest.raises(ValueError):
            LockStyle.from_dict({})

    def test_lockstyle_from_dict_invalid_type(self):
        """name が文字列でない場合 ValueError を raise すること"""
        with pytest.raises(ValueError):
            LockStyle.from_dict({"name": 123})


class TestLockFont:
    """LockFont dataclass のテスト"""

    def test_lockfont_creation_minimal(self):
        """LockFont が必須フィールドで生成されること"""
        font = LockFont(family="Helvetica", source="local", styles=[])
        assert font.family == "Helvetica"
        assert font.source == "local"
        assert font.styles == []
        assert font.hash is None

    def test_lockfont_creation_with_styles(self):
        """LockFont が styles リストを持つこと"""
        styles = [LockStyle(name="Regular"), LockStyle(name="Bold")]
        font = LockFont(family="Inter", source="google-fonts", styles=styles)
        assert len(font.styles) == 2
        assert font.styles[0].name == "Regular"

    def test_lockfont_creation_with_hash(self):
        """LockFont が hash フィールドを持つこと"""
        font = LockFont(family="Inter", source="google-fonts", styles=[], hash="abc123")
        assert font.hash == "abc123"

    def test_lockfont_valid_sources(self):
        """有効な source 値が受け入れられること"""
        for source in ["local", "adobe-fonts", "google-fonts", "commercial", "system"]:
            font = LockFont(family="Test", source=source, styles=[])
            assert font.source == source

    def test_lockfont_to_dict_without_hash(self):
        """to_dict() が hash=None の場合 hash キーを含めること"""
        font = LockFont(
            family="Helvetica",
            source="local",
            styles=[LockStyle(name="Regular")],
        )
        d = font.to_dict()
        assert d["family"] == "Helvetica"
        assert d["source"] == "local"
        assert d["styles"] == [{"name": "Regular"}]
        assert d["hash"] is None

    def test_lockfont_to_dict_with_hash(self):
        """to_dict() が hash 値を含めること"""
        font = LockFont(family="Inter", source="google-fonts", styles=[], hash="sha256hash")
        d = font.to_dict()
        assert d["hash"] == "sha256hash"

    def test_lockfont_from_dict(self):
        """from_dict() が辞書から LockFont を生成すること"""
        d = {
            "family": "Roboto",
            "source": "google-fonts",
            "styles": [{"name": "Regular"}, {"name": "Bold"}],
            "hash": "deadbeef",
        }
        font = LockFont.from_dict(d)
        assert font.family == "Roboto"
        assert font.source == "google-fonts"
        assert len(font.styles) == 2
        assert font.hash == "deadbeef"

    def test_lockfont_from_dict_missing_family(self):
        """family フィールドがない場合 ValueError を raise すること"""
        with pytest.raises(ValueError):
            LockFont.from_dict({"source": "local", "styles": []})

    def test_lockfont_from_dict_missing_source(self):
        """source フィールドがない場合 ValueError を raise すること"""
        with pytest.raises(ValueError):
            LockFont.from_dict({"family": "Test", "styles": []})

    def test_lockfont_from_dict_missing_styles(self):
        """styles フィールドがない場合 ValueError を raise すること"""
        with pytest.raises(ValueError):
            LockFont.from_dict({"family": "Test", "source": "local"})

    def test_lockfont_roundtrip(self):
        """to_dict() → from_dict() のラウンドトリップが一致すること"""
        original = LockFont(
            family="Inter",
            source="google-fonts",
            styles=[LockStyle(name="Regular"), LockStyle(name="Bold")],
            hash="abc123",
        )
        restored = LockFont.from_dict(original.to_dict())
        assert restored.family == original.family
        assert restored.source == original.source
        assert len(restored.styles) == len(original.styles)
        assert restored.styles[0].name == original.styles[0].name
        assert restored.hash == original.hash


class TestFontopsLock:
    """FontopsLock dataclass のテスト"""

    def test_fontopslock_creation(self):
        """FontopsLock が必須フィールドで生成されること"""
        lock = FontopsLock(
            fontops_version="1.0",
            project_name="my-project",
            fonts=[],
        )
        assert lock.fontops_version == "1.0"
        assert lock.project_name == "my-project"
        assert lock.fonts == []

    def test_fontopslock_with_fonts(self):
        """FontopsLock が fonts リストを持つこと"""
        fonts = [LockFont(family="Helvetica", source="local", styles=[])]
        lock = FontopsLock(fontops_version="1.0", project_name="proj", fonts=fonts)
        assert len(lock.fonts) == 1

    def test_fontopslock_to_dict(self):
        """to_dict() が正しい辞書を返すこと"""
        lock = FontopsLock(
            fontops_version="1.0",
            project_name="my-project",
            fonts=[LockFont(family="Helvetica", source="local", styles=[])],
        )
        d = lock.to_dict()
        assert d["fontops_version"] == "1.0"
        assert d["project_name"] == "my-project"
        assert len(d["fonts"]) == 1
        assert d["fonts"][0]["family"] == "Helvetica"

    def test_fontopslock_to_dict_empty_fonts(self):
        """to_dict() が空 fonts 配列を正しく返すこと"""
        lock = FontopsLock(fontops_version="1.0", project_name="empty", fonts=[])
        d = lock.to_dict()
        assert d["fonts"] == []

    def test_fontopslock_from_dict(self):
        """from_dict() が辞書から FontopsLock を生成すること"""
        d = {
            "fontops_version": "1.0",
            "project_name": "test-project",
            "fonts": [
                {
                    "family": "Roboto",
                    "source": "google-fonts",
                    "styles": [{"name": "Regular"}],
                    "hash": None,
                }
            ],
        }
        lock = FontopsLock.from_dict(d)
        assert lock.fontops_version == "1.0"
        assert lock.project_name == "test-project"
        assert len(lock.fonts) == 1
        assert lock.fonts[0].family == "Roboto"

    def test_fontopslock_from_dict_missing_fontops_version(self):
        """fontops_version がない場合 ValueError を raise すること"""
        with pytest.raises(ValueError):
            FontopsLock.from_dict({"project_name": "proj", "fonts": []})

    def test_fontopslock_from_dict_missing_project_name(self):
        """project_name がない場合 ValueError を raise すること"""
        with pytest.raises(ValueError):
            FontopsLock.from_dict({"fontops_version": "1.0", "fonts": []})

    def test_fontopslock_from_dict_missing_fonts(self):
        """fonts フィールドがない場合 ValueError を raise すること"""
        with pytest.raises(ValueError):
            FontopsLock.from_dict({"fontops_version": "1.0", "project_name": "proj"})

    def test_fontopslock_from_dict_fonts_not_list(self):
        """fonts がリストでない場合 ValueError を raise すること"""
        with pytest.raises(ValueError):
            FontopsLock.from_dict(
                {"fontops_version": "1.0", "project_name": "proj", "fonts": "not-a-list"}
            )

    def test_fontopslock_roundtrip(self):
        """to_dict() → from_dict() のラウンドトリップが一致すること"""
        original = FontopsLock(
            fontops_version="1.0",
            project_name="design-system",
            fonts=[
                LockFont(
                    family="Inter",
                    source="google-fonts",
                    styles=[LockStyle(name="Regular"), LockStyle(name="Bold")],
                    hash="sha256abc",
                ),
                LockFont(
                    family="Helvetica",
                    source="system",
                    styles=[],
                    hash=None,
                ),
            ],
        )
        restored = FontopsLock.from_dict(original.to_dict())
        assert restored.fontops_version == original.fontops_version
        assert restored.project_name == original.project_name
        assert len(restored.fonts) == 2
        assert restored.fonts[0].family == "Inter"
        assert restored.fonts[0].hash == "sha256abc"
        assert len(restored.fonts[0].styles) == 2
        assert restored.fonts[1].family == "Helvetica"
        assert restored.fonts[1].hash is None


class TestLoadSaveLock:
    """load_lock / save_lock のテスト"""

    def test_save_lock_creates_file(self, temp_dir: Path):
        """save_lock() がファイルを作成すること"""
        lock = FontopsLock(fontops_version="1.0", project_name="proj", fonts=[])
        lock_path = temp_dir / "fontops.lock"
        save_lock(lock, lock_path)
        assert lock_path.exists()

    def test_save_lock_writes_valid_json(self, temp_dir: Path):
        """save_lock() が有効な JSON を書き込むこと"""
        lock = FontopsLock(fontops_version="1.0", project_name="proj", fonts=[])
        lock_path = temp_dir / "fontops.lock"
        save_lock(lock, lock_path)
        content = lock_path.read_text()
        data = json.loads(content)
        assert data["project_name"] == "proj"

    def test_save_lock_uses_indent_2(self, temp_dir: Path):
        """save_lock() が indent=2 でフォーマットすること"""
        lock = FontopsLock(fontops_version="1.0", project_name="proj", fonts=[])
        lock_path = temp_dir / "fontops.lock"
        save_lock(lock, lock_path)
        content = lock_path.read_text()
        # indent=2 なら行頭に 2 スペースが含まれる
        assert "  " in content

    def test_load_lock_reads_file(self, temp_dir: Path):
        """load_lock() がファイルを読み込み FontopsLock を返すこと"""
        lock = FontopsLock(
            fontops_version="1.0",
            project_name="test-proj",
            fonts=[LockFont(family="Helvetica", source="local", styles=[], hash=None)],
        )
        lock_path = temp_dir / "fontops.lock"
        save_lock(lock, lock_path)

        loaded = load_lock(lock_path)
        assert loaded.fontops_version == "1.0"
        assert loaded.project_name == "test-proj"
        assert len(loaded.fonts) == 1
        assert loaded.fonts[0].family == "Helvetica"

    def test_load_lock_roundtrip(self, temp_dir: Path):
        """save_lock() → load_lock() のラウンドトリップが一致すること"""
        original = FontopsLock(
            fontops_version="1.0",
            project_name="roundtrip-test",
            fonts=[
                LockFont(
                    family="Inter",
                    source="google-fonts",
                    styles=[LockStyle(name="Regular")],
                    hash="abc123",
                )
            ],
        )
        lock_path = temp_dir / "fontops.lock"
        save_lock(original, lock_path)
        restored = load_lock(lock_path)

        assert restored.fontops_version == original.fontops_version
        assert restored.project_name == original.project_name
        assert restored.fonts[0].family == original.fonts[0].family
        assert restored.fonts[0].hash == original.fonts[0].hash
        assert restored.fonts[0].styles[0].name == original.fonts[0].styles[0].name

    def test_load_lock_file_not_found(self, temp_dir: Path):
        """load_lock() がファイルなしのとき FileNotFoundError を raise すること"""
        with pytest.raises(FileNotFoundError):
            load_lock(temp_dir / "nonexistent.lock")

    def test_load_lock_invalid_json(self, temp_dir: Path):
        """load_lock() が不正 JSON のとき ValueError を raise すること"""
        lock_path = temp_dir / "fontops.lock"
        lock_path.write_text("{ not valid json }")
        with pytest.raises(ValueError):
            load_lock(lock_path)

    def test_load_lock_invalid_schema(self, temp_dir: Path):
        """load_lock() が不正スキーマのとき ValueError を raise すること"""
        lock_path = temp_dir / "fontops.lock"
        lock_path.write_text(json.dumps({"unexpected": "structure"}))
        with pytest.raises(ValueError):
            load_lock(lock_path)

    def test_load_lock_empty_fonts(self, temp_dir: Path):
        """load_lock() が空 fonts の lock ファイルを正しく読み込むこと"""
        lock_path = temp_dir / "fontops.lock"
        lock_path.write_text(
            json.dumps(
                {"fontops_version": "1.0", "project_name": "empty", "fonts": []},
                indent=2,
            )
        )
        loaded = load_lock(lock_path)
        assert loaded.fonts == []
