"""fontops.lock コマンドの E2E テスト

lock init / add / remove コマンドの一連フローを typer.testing.CliRunner で検証。
enumerate_installed_fonts をモックし、tmp_path 上で fontops.lock の生成・変更を確認する。
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.font_inventory import InstalledFont
from src.lockfile import load_lock
from src.main import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# テスト用フィクスチャ・ヘルパー
# ---------------------------------------------------------------------------

_MOCK_FONTS = [
    InstalledFont(family="Inter", style="Regular", path=Path("/Library/Fonts/Inter-Regular.ttf"), source="local"),
    InstalledFont(family="Inter", style="Bold", path=Path("/Library/Fonts/Inter-Bold.ttf"), source="local"),
    InstalledFont(family="Helvetica", style="Regular", path=Path("/Library/Fonts/Helvetica.ttf"), source="local"),
    InstalledFont(family="Adobe Sans", style="Regular", path=Path("/Library/Fonts/AdobeSans.otf"), source="adobe-fonts"),
]


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """作業ディレクトリを tmp_path に変更するフィクスチャ"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def initialized_lock(work_dir):
    """空の fontops.lock が存在する作業ディレクトリを返す"""
    lock_file = work_dir / "fontops.lock"
    lock_data = {
        "fontops_version": "1",
        "project_name": "test-project",
        "fonts": [],
    }
    lock_file.write_text(json.dumps(lock_data, indent=2))
    return work_dir


@pytest.fixture
def lock_with_two_fonts(work_dir):
    """2フォントを持つ fontops.lock が存在する作業ディレクトリを返す"""
    lock_file = work_dir / "fontops.lock"
    lock_data = {
        "fontops_version": "1",
        "project_name": "test-project",
        "fonts": [
            {"family": "Inter", "source": "local", "styles": [], "hash": None},
            {"family": "Helvetica", "source": "system", "styles": [], "hash": None},
        ],
    }
    lock_file.write_text(json.dumps(lock_data, indent=2))
    return work_dir


# ---------------------------------------------------------------------------
# lock init テスト
# ---------------------------------------------------------------------------


class TestLockInitE2E:
    """lock init コマンドの E2E テスト"""

    def test_init_all_creates_lock_file(self, work_dir):
        """lock init --name --all が fontops.lock を生成すること"""
        with patch("src.commands.lock_cmd.enumerate_installed_fonts", return_value=_MOCK_FONTS):
            result = runner.invoke(app, ["lock", "init", "--name", "my-project", "--all"])

        assert result.exit_code == 0, result.output
        lock_file = work_dir / "fontops.lock"
        assert lock_file.exists()

        lock = load_lock(lock_file)
        assert lock.project_name == "my-project"
        assert lock.fontops_version == "1"
        families = {lf.family for lf in lock.fonts}
        assert "Inter" in families
        assert "Helvetica" in families

    def test_init_all_groups_styles_by_family(self, work_dir):
        """lock init --all が同一ファミリーのスタイルをまとめること"""
        with patch("src.commands.lock_cmd.enumerate_installed_fonts", return_value=_MOCK_FONTS):
            result = runner.invoke(app, ["lock", "init", "--name", "proj", "--all"])

        assert result.exit_code == 0, result.output
        lock = load_lock(work_dir / "fontops.lock")
        inter = next(lf for lf in lock.fonts if lf.family == "Inter")
        style_names = {s.name for s in inter.styles}
        assert "Regular" in style_names
        assert "Bold" in style_names

    def test_init_without_all_shows_preview_no_file(self, work_dir):
        """lock init (--all なし) がプレビューを表示してロックを生成しないこと"""
        with patch("src.commands.lock_cmd.enumerate_installed_fonts", return_value=_MOCK_FONTS):
            result = runner.invoke(app, ["lock", "init", "--name", "proj"])

        assert result.exit_code == 0, result.output
        assert not (work_dir / "fontops.lock").exists()
        assert "--all" in result.output

    def test_init_fails_if_lock_exists(self, work_dir):
        """fontops.lock が既に存在する場合 init がエラーになること"""
        (work_dir / "fontops.lock").write_text(
            json.dumps({"fontops_version": "1", "project_name": "old", "fonts": []})
        )
        with patch("src.commands.lock_cmd.enumerate_installed_fonts", return_value=_MOCK_FONTS):
            result = runner.invoke(app, ["lock", "init", "--name", "new", "--all"])

        assert result.exit_code != 0

    def test_init_force_overwrites_existing(self, work_dir):
        """--force オプションで既存の fontops.lock を上書きすること"""
        (work_dir / "fontops.lock").write_text(
            json.dumps({"fontops_version": "1", "project_name": "old", "fonts": []})
        )
        with patch("src.commands.lock_cmd.enumerate_installed_fonts", return_value=_MOCK_FONTS):
            result = runner.invoke(app, ["lock", "init", "--name", "new-project", "--all", "--force"])

        assert result.exit_code == 0, result.output
        lock = load_lock(work_dir / "fontops.lock")
        assert lock.project_name == "new-project"


# ---------------------------------------------------------------------------
# lock add テスト
# ---------------------------------------------------------------------------


class TestLockAddE2E:
    """lock add コマンドの E2E テスト"""

    def test_add_font_default_source(self, initialized_lock):
        """lock add がフォントを local ソースで追加すること"""
        result = runner.invoke(app, ["lock", "add", "Inter"])

        assert result.exit_code == 0, result.output
        lock = load_lock(initialized_lock / "fontops.lock")
        assert len(lock.fonts) == 1
        assert lock.fonts[0].family == "Inter"
        assert lock.fonts[0].source == "local"

    def test_add_font_with_custom_source(self, initialized_lock):
        """lock add --source でソースを指定できること"""
        result = runner.invoke(app, ["lock", "add", "Roboto", "--source", "google-fonts"])

        assert result.exit_code == 0, result.output
        lock = load_lock(initialized_lock / "fontops.lock")
        assert lock.fonts[0].source == "google-fonts"

    def test_add_font_with_styles(self, initialized_lock):
        """lock add --styles でスタイルを追加できること"""
        result = runner.invoke(app, ["lock", "add", "Inter", "--styles", "Regular,Bold"])

        assert result.exit_code == 0, result.output
        lock = load_lock(initialized_lock / "fontops.lock")
        style_names = [s.name for s in lock.fonts[0].styles]
        assert "Regular" in style_names
        assert "Bold" in style_names

    def test_add_font_empty_styles(self, initialized_lock):
        """--styles なしの add が空スタイルリストになること"""
        result = runner.invoke(app, ["lock", "add", "Inter"])

        assert result.exit_code == 0, result.output
        lock = load_lock(initialized_lock / "fontops.lock")
        assert lock.fonts[0].styles == []

    def test_add_duplicate_family_fails(self, initialized_lock):
        """同一 family を重複して add するとエラーになること"""
        runner.invoke(app, ["lock", "add", "Inter"])
        result = runner.invoke(app, ["lock", "add", "Inter"])

        assert result.exit_code != 0

    def test_add_no_lock_file_fails(self, work_dir):
        """fontops.lock がない場合 add がエラーになること"""
        result = runner.invoke(app, ["lock", "add", "Inter"])

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# lock remove テスト
# ---------------------------------------------------------------------------


class TestLockRemoveE2E:
    """lock remove コマンドの E2E テスト"""

    def test_remove_font(self, lock_with_two_fonts):
        """lock remove がフォントを削除すること"""
        result = runner.invoke(app, ["lock", "remove", "Inter"])

        assert result.exit_code == 0, result.output
        lock = load_lock(lock_with_two_fonts / "fontops.lock")
        families = [lf.family for lf in lock.fonts]
        assert "Inter" not in families
        assert "Helvetica" in families

    def test_remove_case_insensitive(self, lock_with_two_fonts):
        """lock remove が大文字小文字を区別しないこと"""
        result = runner.invoke(app, ["lock", "remove", "inter"])

        assert result.exit_code == 0, result.output
        lock = load_lock(lock_with_two_fonts / "fontops.lock")
        assert len(lock.fonts) == 1

    def test_remove_not_found_fails(self, lock_with_two_fonts):
        """存在しない family の remove がエラーになること"""
        result = runner.invoke(app, ["lock", "remove", "NonExistent"])

        assert result.exit_code != 0

    def test_remove_no_lock_file_fails(self, work_dir):
        """fontops.lock がない場合 remove がエラーになること"""
        result = runner.invoke(app, ["lock", "remove", "Inter"])

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# 一連フロー E2E テスト
# ---------------------------------------------------------------------------


class TestLockFullWorkflowE2E:
    """lock init → add → remove の一連フロー E2E テスト"""

    def test_full_workflow(self, work_dir):
        """init → add → remove の一連フローが正常動作すること"""
        single_font = [
            InstalledFont(
                family="Inter",
                style="Regular",
                path=Path("/Library/Fonts/Inter.ttf"),
                source="local",
            )
        ]

        # Step 1: init
        with patch("src.commands.lock_cmd.enumerate_installed_fonts", return_value=single_font):
            result = runner.invoke(app, ["lock", "init", "--name", "design-system", "--all"])
        assert result.exit_code == 0, result.output

        lock = load_lock(work_dir / "fontops.lock")
        assert lock.project_name == "design-system"
        assert len(lock.fonts) == 1
        assert lock.fonts[0].family == "Inter"

        # Step 2: add
        result = runner.invoke(
            app, ["lock", "add", "Roboto", "--source", "google-fonts", "--styles", "Regular,Bold"]
        )
        assert result.exit_code == 0, result.output

        lock = load_lock(work_dir / "fontops.lock")
        assert len(lock.fonts) == 2

        # Step 3: remove
        result = runner.invoke(app, ["lock", "remove", "Inter"])
        assert result.exit_code == 0, result.output

        lock = load_lock(work_dir / "fontops.lock")
        assert len(lock.fonts) == 1
        assert lock.fonts[0].family == "Roboto"
        assert len(lock.fonts[0].styles) == 2


# ---------------------------------------------------------------------------
# エラーケース: 破損 JSON / 不正スキーマ
# ---------------------------------------------------------------------------


class TestLockErrorCasesE2E:
    """破損 JSON・不正スキーマのエラーケース E2E テスト"""

    def test_load_lock_corrupted_json(self, tmp_path):
        """破損 JSON の load_lock が ValueError を raise すること"""
        lock_file = tmp_path / "fontops.lock"
        lock_file.write_text("{ this is not valid json }")

        with pytest.raises(ValueError):
            load_lock(lock_file)

    def test_load_lock_invalid_schema(self, tmp_path):
        """不正スキーマの load_lock が ValueError を raise すること"""
        lock_file = tmp_path / "fontops.lock"
        lock_file.write_text(json.dumps({"unexpected": "structure"}))

        with pytest.raises(ValueError):
            load_lock(lock_file)

    def test_load_lock_valid_empty_fonts(self, tmp_path):
        """空 fonts の lock ファイルが正常に読み込めること"""
        lock_file = tmp_path / "fontops.lock"
        lock_file.write_text(
            json.dumps({"fontops_version": "1", "project_name": "empty", "fonts": []}, indent=2)
        )

        lock = load_lock(lock_file)
        assert lock.fonts == []
