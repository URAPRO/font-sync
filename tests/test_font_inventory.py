"""font_inventory モジュールのテスト"""

import hashlib
import os
from pathlib import Path

import src.font_inventory as inv_module
from src.font_inventory import (
    InstalledFont,
    _classify_source,
    calculate_font_hash,
    clear_cache,
    enumerate_installed_fonts,
)


def _create_test_font(
    path: Path, family: str = "TestFamily", style: str = "Regular"
) -> None:
    """fontTools で最小 TTF ファイルを生成する（テスト用）。"""
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables._n_a_m_e import table__n_a_m_e

    font = TTFont()
    name_table = table__n_a_m_e()
    name_table.names = []
    # Platform 3 (Windows), platEncID 1 (Unicode BMP), langID 0x409 (English US)
    name_table.setName(family, 1, 3, 1, 0x409)
    name_table.setName(style, 2, 3, 1, 0x409)
    font["name"] = name_table
    font.save(str(path))


class TestInstalledFont:
    def test_fields_are_accessible(self, temp_dir):
        """InstalledFont が正しいフィールドを持つこと"""
        font = InstalledFont(
            family="TestFamily",
            style="Regular",
            path=temp_dir / "font.ttf",
            source="local",
        )
        assert font.family == "TestFamily"
        assert font.style == "Regular"
        assert font.path == temp_dir / "font.ttf"
        assert font.source == "local"

    def test_adobe_source_accepted(self, temp_dir):
        """InstalledFont が 'adobe-fonts' ソースを持てること"""
        font = InstalledFont(
            family="AdobeFont",
            style="Regular",
            path=temp_dir / "font.otf",
            source="adobe-fonts",
        )
        assert font.source == "adobe-fonts"


class TestCalculateFontHash:
    def test_returns_64_char_hex_string(self, temp_dir):
        """SHA-256 hex 文字列 (64 文字) を返すこと"""
        test_file = temp_dir / "test.bin"
        test_file.write_bytes(b"hello world")
        result = calculate_font_hash(test_file)
        assert isinstance(result, str)
        assert len(result) == 64

    def test_correct_sha256_value(self, temp_dir):
        """正確な SHA-256 hash を返すこと"""
        data = b"font data test"
        test_file = temp_dir / "test.bin"
        test_file.write_bytes(data)
        expected = hashlib.sha256(data).hexdigest()
        assert calculate_font_hash(test_file) == expected

    def test_deterministic(self, temp_dir):
        """同じファイルに対して同じ hash を返すこと"""
        test_file = temp_dir / "test.bin"
        test_file.write_bytes(b"reproducible data")
        h1 = calculate_font_hash(test_file)
        h2 = calculate_font_hash(test_file)
        assert h1 == h2

    def test_different_content_different_hash(self, temp_dir):
        """異なる内容のファイルは異なる hash を返すこと"""
        file1 = temp_dir / "a.bin"
        file2 = temp_dir / "b.bin"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B")
        assert calculate_font_hash(file1) != calculate_font_hash(file2)


class TestClassifySource:
    def test_local_for_regular_path(self, tmp_path, monkeypatch):
        """通常パスは 'local' を返すこと"""
        font_path = tmp_path / "font.ttf"
        monkeypatch.setattr(os.path, "realpath", lambda p: str(font_path))
        assert _classify_source(font_path) == "local"

    def test_adobe_for_corysync_slash(self, tmp_path, monkeypatch):
        """'Adobe/CoreSync' を含むパスは 'adobe-fonts' を返すこと"""
        adobe_path = (
            "/Users/user/Library/Application Support/Adobe/CoreSync/plugins/livetype/.r/font.ttf"
        )
        monkeypatch.setattr(os.path, "realpath", lambda p: adobe_path)
        assert _classify_source(tmp_path / "font.ttf") == "adobe-fonts"

    def test_adobe_for_corysync_space(self, tmp_path, monkeypatch):
        """'Adobe CoreSync' (スペース区切り) を含むパスは 'adobe-fonts' を返すこと"""
        adobe_path = "/Users/user/Library/Application Support/Adobe CoreSync/font.ttf"
        monkeypatch.setattr(os.path, "realpath", lambda p: adobe_path)
        assert _classify_source(tmp_path / "font.ttf") == "adobe-fonts"

    def test_local_for_user_library_fonts(self, tmp_path, monkeypatch):
        """~/Library/Fonts/ 配下は 'local' を返すこと"""
        font_path = "/Users/user/Library/Fonts/MyFont.ttf"
        monkeypatch.setattr(os.path, "realpath", lambda p: font_path)
        assert _classify_source(tmp_path / "font.ttf") == "local"


class TestEnumerateInstalledFonts:
    def test_finds_ttf_font_in_dir(self, temp_dir):
        """temp_dir 内の TTF フォントが列挙されること"""
        clear_cache()
        _create_test_font(temp_dir / "TestFont.ttf", "MyFamily", "Regular")
        fonts = enumerate_installed_fonts(dirs=[temp_dir], use_cache=False)
        assert len(fonts) >= 1
        families = [f.family for f in fonts]
        assert "MyFamily" in families

    def test_returns_correct_style(self, temp_dir):
        """正しいスタイル名が返されること"""
        clear_cache()
        _create_test_font(temp_dir / "TestFont.ttf", "MyFamily", "BoldItalic")
        fonts = enumerate_installed_fonts(dirs=[temp_dir], use_cache=False)
        assert any(f.style == "BoldItalic" for f in fonts)

    def test_path_field_is_set(self, temp_dir):
        """InstalledFont.path が正しいファイルパスを持つこと"""
        clear_cache()
        font_file = temp_dir / "PathTest.ttf"
        _create_test_font(font_file, "PathFamily", "Regular")
        fonts = enumerate_installed_fonts(dirs=[temp_dir], use_cache=False)
        paths = [f.path for f in fonts]
        assert font_file in paths

    def test_skips_empty_files(self, temp_dir):
        """0 バイトのファイルはスキップされること"""
        clear_cache()
        empty_file = temp_dir / "empty.ttf"
        empty_file.write_bytes(b"")
        fonts = enumerate_installed_fonts(dirs=[temp_dir], use_cache=False)
        assert not any(f.path == empty_file for f in fonts)

    def test_skips_broken_files_no_exception(self, temp_dir):
        """破損ファイルはスキップされ、例外が raise されないこと"""
        clear_cache()
        broken_file = temp_dir / "broken.ttf"
        broken_file.write_bytes(b"this is not a valid font file at all")
        # 例外なし、かつ broken_file は結果に含まれないこと
        fonts = enumerate_installed_fonts(dirs=[temp_dir], use_cache=False)
        assert isinstance(fonts, list)
        assert not any(f.path == broken_file for f in fonts)

    def test_adobe_source_classification(self, temp_dir, monkeypatch):
        """Adobe ソースのフォントが 'adobe-fonts' に分類されること"""
        clear_cache()
        _create_test_font(temp_dir / "AdobeFont.ttf", "AdobeFamily", "Regular")
        adobe_real_path = (
            "/Users/user/Library/Application Support/Adobe/CoreSync/plugins/livetype/.r/AdobeFont.ttf"
        )
        original_realpath = os.path.realpath

        def mock_realpath(path):
            if "AdobeFont" in str(path):
                return adobe_real_path
            return original_realpath(path)

        monkeypatch.setattr(os.path, "realpath", mock_realpath)

        fonts = enumerate_installed_fonts(dirs=[temp_dir], use_cache=False)
        adobe_fonts = [f for f in fonts if f.family == "AdobeFamily"]
        assert len(adobe_fonts) >= 1
        assert adobe_fonts[0].source == "adobe-fonts"

    def test_nonexistent_dir_returns_empty(self, temp_dir):
        """存在しないディレクトリは空リストを返すこと"""
        clear_cache()
        nonexistent = temp_dir / "nonexistent"
        fonts = enumerate_installed_fonts(dirs=[nonexistent], use_cache=False)
        assert fonts == []

    def test_ignores_non_font_files(self, temp_dir):
        """非フォントファイルは無視されること"""
        clear_cache()
        (temp_dir / "readme.txt").write_text("not a font")
        (temp_dir / "image.png").write_bytes(b"\x89PNG")
        fonts = enumerate_installed_fonts(dirs=[temp_dir], use_cache=False)
        assert fonts == []


class TestCaching:
    def test_clear_cache_sets_none(self):
        """clear_cache() が _cache を None にリセットすること"""
        inv_module._cache = [
            InstalledFont("dummy", "Regular", Path("/tmp/dummy.ttf"), "local")
        ]
        clear_cache()
        assert inv_module._cache is None

    def test_use_cache_returns_preloaded_data(self, temp_dir):
        """_cache にデータがある場合、実スキャンをスキップして返すこと"""
        clear_cache()
        expected = [InstalledFont("CachedFont", "Bold", temp_dir / "f.ttf", "local")]
        inv_module._cache = expected

        result = enumerate_installed_fonts(use_cache=True)
        assert result == expected

        clear_cache()

    def test_dirs_specified_bypasses_cache(self, temp_dir):
        """dirs 指定時はキャッシュを使わず実スキャンすること"""
        clear_cache()
        # _cache に dummy データをセット
        inv_module._cache = [
            InstalledFont("CachedFont", "Regular", temp_dir / "f.ttf", "local")
        ]
        _create_test_font(temp_dir / "RealFont.ttf", "RealFamily", "Regular")

        # dirs 指定 → キャッシュをバイパスして実スキャン
        fonts = enumerate_installed_fonts(dirs=[temp_dir], use_cache=True)
        families = [f.family for f in fonts]
        assert "RealFamily" in families
        assert "CachedFont" not in families

        clear_cache()
