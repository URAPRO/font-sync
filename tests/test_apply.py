"""apply コマンドの E2E テスト

font-sync apply コマンドの結合テスト。
CliRunner + monkeypatch.chdir(tmp_path) で環境分離。
enumerate_installed_fonts をモックして各シナリオを検証する。
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.font_inventory import InstalledFont
from src.lockfile import FontopsLock, LockFont, LockStyle, save_lock
from src.main import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# テスト用定数・ヘルパー
# ---------------------------------------------------------------------------

_MOCK_FONTS_INSTALLED = [
    InstalledFont(
        family="Inter",
        style="Regular",
        path=Path("/Library/Fonts/Inter-Regular.ttf"),
        source="local",
    ),
    InstalledFont(
        family="Roboto",
        style="Regular",
        path=Path("/Library/Fonts/Roboto-Regular.ttf"),
        source="local",
    ),
]

_LOCK_FILE_NAME = "fontops.lock"


def _make_lock(fonts: list[LockFont], project_name: str = "test-project") -> FontopsLock:
    """テスト用 FontopsLock を生成するヘルパー"""
    return FontopsLock(fontops_version="1", project_name=project_name, fonts=fonts)


def _make_lock_font(
    family: str,
    source: str = "local",
    styles: list[str] | None = None,
) -> LockFont:
    """テスト用 LockFont を生成するヘルパー"""
    style_objs = [LockStyle(name=s) for s in (styles or [])]
    return LockFont(family=family, source=source, styles=style_objs)


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """作業ディレクトリを tmp_path に変更するフィクスチャ"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def lock_with_mixed_fonts(work_dir):
    """installed/not-installed が混在する fontops.lock を用意"""
    lock = _make_lock([
        _make_lock_font("Inter", "local"),           # _MOCK_FONTS_INSTALLED にある → installed
        _make_lock_font("Roboto", "google-fonts"),   # _MOCK_FONTS_INSTALLED にある → installed
        _make_lock_font("Noto Sans", "google-fonts"),# インストール未 → resolvable
        _make_lock_font("MyFont", "commercial"),     # インストール未 → purchasable
        _make_lock_font("OldFont", "local"),         # インストール未 → unavailable
    ])
    save_lock(lock, work_dir / _LOCK_FILE_NAME)
    return work_dir


@pytest.fixture
def lock_all_installed(work_dir):
    """全フォントがインストール済みの fontops.lock を用意"""
    lock = _make_lock([
        _make_lock_font("Inter", "local"),
        _make_lock_font("Roboto", "adobe-fonts"),
    ])
    save_lock(lock, work_dir / _LOCK_FILE_NAME)
    return work_dir


@pytest.fixture
def lock_empty_fonts(work_dir):
    """fonts が空の fontops.lock を用意"""
    lock = _make_lock([])
    save_lock(lock, work_dir / _LOCK_FILE_NAME)
    return work_dir


# ---------------------------------------------------------------------------
# 基本動作テスト
# ---------------------------------------------------------------------------


class TestApplyBasic:
    """apply コマンドの基本動作テスト"""

    def test_apply_renders_rich_table(self, lock_with_mixed_fonts):
        """apply が Rich テーブルを出力すること"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply"])

        assert result.exit_code == 0, result.output
        # Rich テーブルのカラム見出しが出力に含まれること
        assert "Font Family" in result.output
        assert "Source" in result.output
        assert "Status" in result.output
        assert "Action" in result.output

    def test_apply_shows_font_names(self, lock_with_mixed_fonts):
        """apply がフォント名を出力に含むこと"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply"])

        assert result.exit_code == 0, result.output
        assert "Inter" in result.output
        assert "Noto Sans" in result.output

    def test_apply_mixed_status(self, lock_with_mixed_fonts):
        """apply が mixed 状態で各ステータスアイコンを表示すること"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply"])

        assert result.exit_code == 0, result.output
        # installed アイコン (✓) と unavailable アイコン (✗) が両方含まれること
        assert "✓" in result.output
        assert "✗" in result.output


# ---------------------------------------------------------------------------
# JSON 出力テスト
# ---------------------------------------------------------------------------


class TestApplyJsonOutput:
    """apply --json の出力構造テスト"""

    def test_apply_json_valid_structure(self, lock_with_mixed_fonts):
        """apply --json が有効な JSON を出力すること"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "fontops_version" in data
        assert "results" in data
        assert "summary" in data

    def test_apply_json_results_array(self, lock_with_mixed_fonts):
        """apply --json の results が lock のフォント数と一致すること"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply", "--json"])

        data = json.loads(result.output)
        assert len(data["results"]) == 5  # lock_with_mixed_fonts は 5 フォント

    def test_apply_json_result_fields(self, lock_with_mixed_fonts):
        """apply --json の各 result が必要フィールドを持つこと"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply", "--json"])

        data = json.loads(result.output)
        for entry in data["results"]:
            assert "family" in entry
            assert "source" in entry
            assert "status" in entry
            assert "action" in entry
            assert "styles" in entry

    def test_apply_json_summary_has_all_status_keys(self, lock_with_mixed_fonts):
        """apply --json の summary が全 FontStatus キーを持つこと"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply", "--json"])

        data = json.loads(result.output)
        summary = data["summary"]
        expected_keys = {"installed", "resolvable", "activatable", "purchasable", "unavailable"}
        assert expected_keys.issubset(set(summary.keys()))

    def test_apply_json_summary_counts(self, lock_with_mixed_fonts):
        """apply --json のサマリーカウントが正確であること"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply", "--json"])

        data = json.loads(result.output)
        summary = data["summary"]
        # Inter(local-installed) + Roboto(google-fonts-installed) = 2 installed
        assert summary["installed"] == 2
        # Noto Sans (google-fonts, not installed) = 1 resolvable
        assert summary["resolvable"] == 1
        # MyFont (commercial, not installed) = 1 purchasable
        assert summary["purchasable"] == 1
        # OldFont (local, not installed) = 1 unavailable
        assert summary["unavailable"] == 1


# ---------------------------------------------------------------------------
# エラーケーステスト
# ---------------------------------------------------------------------------


class TestApplyErrorCases:
    """apply コマンドのエラーケーステスト"""

    def test_apply_no_lock_file_exits_nonzero(self, work_dir):
        """fontops.lock が存在しない場合 exit_code != 0 であること"""
        result = runner.invoke(app, ["apply"])
        assert result.exit_code != 0

    def test_apply_no_lock_file_shows_error_message(self, work_dir):
        """fontops.lock が存在しない場合エラーメッセージを表示すること"""
        result = runner.invoke(app, ["apply"])
        assert "fontops.lock" in result.output

    def test_apply_empty_fonts_lock_shows_message(self, lock_empty_fonts):
        """fonts が空の lock で apply が 'フォントが定義されていません' を表示すること"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply"])

        assert result.exit_code == 0, result.output
        assert "フォントが定義されていません" in result.output


# ---------------------------------------------------------------------------
# 全 installed ケーステスト
# ---------------------------------------------------------------------------


class TestApplyAllInstalled:
    """全フォントが installed の場合のテスト"""

    def test_apply_all_installed_summary(self, lock_all_installed):
        """全フォント installed の場合、installed カウントが正しいこと"""
        all_installed = [
            InstalledFont(
                family="Inter",
                style="Regular",
                path=Path("/Library/Fonts/Inter.ttf"),
                source="local",
            ),
            InstalledFont(
                family="Roboto",
                style="Regular",
                path=Path("/Library/Fonts/Roboto.ttf"),
                source="adobe-fonts",
            ),
        ]
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=all_installed):
            result = runner.invoke(app, ["apply", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["summary"]["installed"] == 2
        assert data["summary"]["unavailable"] == 0
        assert data["summary"]["resolvable"] == 0

    def test_apply_all_installed_shows_installed_icon(self, lock_all_installed):
        """全フォント installed の場合、installed アイコンのみ表示されること"""
        all_installed = [
            InstalledFont(
                family="Inter",
                style="Regular",
                path=Path("/Library/Fonts/Inter.ttf"),
                source="local",
            ),
            InstalledFont(
                family="Roboto",
                style="Regular",
                path=Path("/Library/Fonts/Roboto.ttf"),
                source="adobe-fonts",
            ),
        ]
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=all_installed):
            result = runner.invoke(app, ["apply"])

        assert result.exit_code == 0, result.output
        assert "✓" in result.output
        assert "✗" not in result.output


# ---------------------------------------------------------------------------
# --resolve フラグテスト
# ---------------------------------------------------------------------------


class TestApplyResolveFlag:
    """--resolve フラグのプレースホルダテスト"""

    def test_apply_resolve_shows_placeholder_message(self, lock_with_mixed_fonts):
        """--resolve フラグがプレースホルダメッセージを表示すること"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply", "--resolve"])

        assert result.exit_code == 0, result.output
        assert "未実装" in result.output or "resolve" in result.output.lower()

    def test_apply_resolve_still_renders_report(self, lock_with_mixed_fonts):
        """--resolve フラグでもテーブルレポートが表示されること"""
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=_MOCK_FONTS_INSTALLED):
            result = runner.invoke(app, ["apply", "--resolve"])

        assert result.exit_code == 0, result.output
        assert "Font Family" in result.output


# ---------------------------------------------------------------------------
# case-insensitive 判定テスト
# ---------------------------------------------------------------------------


class TestApplyCaseInsensitiveMatching:
    """family 名の case-insensitive マッチのテスト"""

    def test_apply_case_insensitive_match(self, work_dir):
        """lock の family 名と installed フォントが大文字小文字で違っても installed 判定になること"""
        lock = _make_lock([_make_lock_font("inter", "local")])  # 小文字
        save_lock(lock, work_dir / _LOCK_FILE_NAME)

        installed = [
            InstalledFont(
                family="Inter",  # 大文字
                style="Regular",
                path=Path("/Library/Fonts/Inter.ttf"),
                source="local",
            )
        ]
        with patch("src.commands.apply.enumerate_installed_fonts", return_value=installed):
            result = runner.invoke(app, ["apply", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["summary"]["installed"] == 1
