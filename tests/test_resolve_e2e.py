"""apply --resolve の E2E テスト

apply --resolve のフルフロー: httpx MockTransport + tmp インストールディレクトリで環境分離。
test_apply.py が resolve_fonts をモックするのに対して、このファイルは実際の resolve_fonts()
を呼び出し、httpx レイヤーのみをモックする。

各テストは以下を組み合わせる:
  - work_dir: monkeypatch.chdir(tmp_path) で fontops.lock の作業ディレクトリを分離
  - mock_install_dir: tmp_path / "Library" / "Fonts" でフォントインストール先を分離
  - patch("src.resolver.httpx.Client"): 実ネットワーク通信を遮断
"""

import hashlib
import json
import zipfile
from io import BytesIO
from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from src.lockfile import FontopsLock, LockFont, save_lock
from src.main import app

runner = CliRunner()

_LOCK_FILE_NAME = "fontops.lock"


# ---------------------------------------------------------------------------
# テストヘルパー
# ---------------------------------------------------------------------------


def create_test_zip(
    font_filename: str = "TestFont-Regular.ttf",
    font_content: bytes = b"dummy ttf content",
) -> bytes:
    """テスト用の Google Fonts-style ZIP を生成"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(font_filename, font_content)
    return buf.getvalue()


def make_mock_http_client(zip_content: bytes) -> httpx.Client:
    """指定した ZIP コンテンツを返す httpx.Client を生成"""

    def handler(request):
        return httpx.Response(200, content=zip_content)

    return httpx.Client(transport=httpx.MockTransport(handler))


def make_error_http_client() -> httpx.Client:
    """常に ConnectError を raise する httpx.Client を生成"""

    def handler(request):
        raise httpx.ConnectError("Connection refused")

    return httpx.Client(transport=httpx.MockTransport(handler))


def make_google_fonts_lock(family: str = "Noto Sans JP", hash_: str | None = None) -> FontopsLock:
    """google-fonts ソースの FontopsLock を生成するヘルパー"""
    return FontopsLock(
        fontops_version="1",
        project_name="test",
        fonts=[LockFont(family=family, source="google-fonts", styles=[], hash=hash_)],
    )


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """作業ディレクトリを tmp_path に変更するフィクスチャ"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def mock_install_dir(tmp_path):
    """フォントインストール先を tmp ディレクトリに置き換えるフィクスチャ"""
    install_dir = tmp_path / "Library" / "Fonts"
    install_dir.mkdir(parents=True)
    return install_dir


# ---------------------------------------------------------------------------
# フルフロー E2E テスト
# ---------------------------------------------------------------------------


class TestApplyResolveFullFlow:
    """apply --resolve の実際のフルフロー（httpx のみモック）"""

    def test_resolve_installs_google_font(self, work_dir, mock_install_dir):
        """Google Fonts フォント → DL → mock_install_dir に .ttf がインストールされること"""
        zip_content = create_test_zip("NotoSansJP-Regular.ttf")
        save_lock(make_google_fonts_lock(), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                with patch(
                    "src.resolver.httpx.Client",
                    return_value=make_mock_http_client(zip_content),
                ):
                    result = runner.invoke(app, ["apply", "--resolve"])

        assert result.exit_code == 0, result.output
        installed_files = list(mock_install_dir.iterdir())
        assert len(installed_files) == 1
        assert installed_files[0].name == "NotoSansJP-Regular.ttf"

    def test_resolve_shows_resolve_report_table(self, work_dir, mock_install_dir):
        """--resolve で解決レポートテーブルが表示されること"""
        zip_content = create_test_zip()
        save_lock(make_google_fonts_lock(), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                with patch(
                    "src.resolver.httpx.Client",
                    return_value=make_mock_http_client(zip_content),
                ):
                    result = runner.invoke(app, ["apply", "--resolve"])

        assert result.exit_code == 0, result.output
        # 解決レポートテーブルのカラムが表示されること
        assert "Font Family" in result.output
        assert "Action" in result.output
        assert "Message" in result.output

    def test_resolve_hash_match_installs(self, work_dir, mock_install_dir):
        """ハッシュ一致 → インストール成功"""
        zip_content = create_test_zip()
        zip_hash = hashlib.sha256(zip_content).hexdigest()
        save_lock(make_google_fonts_lock(hash_=zip_hash), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                with patch(
                    "src.resolver.httpx.Client",
                    return_value=make_mock_http_client(zip_content),
                ):
                    result = runner.invoke(app, ["apply", "--resolve"])

        assert result.exit_code == 0, result.output
        assert any(mock_install_dir.iterdir())  # ファイルがインストールされていること

    def test_resolve_hash_mismatch_aborts_install(self, work_dir, mock_install_dir):
        """ハッシュ不一致 → インストール中止（ファイルなし）"""
        zip_content = create_test_zip()
        save_lock(make_google_fonts_lock(hash_="wronghash000"), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                with patch(
                    "src.resolver.httpx.Client",
                    return_value=make_mock_http_client(zip_content),
                ):
                    result = runner.invoke(app, ["apply", "--resolve"])

        assert result.exit_code == 0, result.output
        assert not list(mock_install_dir.iterdir())  # ファイルがインストールされていない

    def test_resolve_network_error_does_not_abort_command(self, work_dir, mock_install_dir):
        """ネットワークエラー → コマンドは成功終了（エラーは resolve_results に記録）"""
        save_lock(make_google_fonts_lock(), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                with patch(
                    "src.resolver.httpx.Client",
                    return_value=make_error_http_client(),
                ):
                    result = runner.invoke(app, ["apply", "--resolve"])

        assert result.exit_code == 0, result.output
        assert not list(mock_install_dir.iterdir())  # ファイルがインストールされていない


# ---------------------------------------------------------------------------
# --dry-run --resolve テスト
# ---------------------------------------------------------------------------


class TestApplyDryRunResolve:
    """--dry-run --resolve テスト: DL が発生しないことを確認"""

    def test_dry_run_does_not_call_httpx_client(self, work_dir, mock_install_dir):
        """--dry-run --resolve では httpx.Client が呼ばれないこと"""
        save_lock(make_google_fonts_lock(), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                with patch("src.resolver.httpx.Client") as mock_client_cls:
                    result = runner.invoke(app, ["apply", "--dry-run", "--resolve"])

        assert result.exit_code == 0, result.output
        assert "dry-run" in result.output
        mock_client_cls.assert_not_called()  # httpx.Client が呼ばれていないこと
        assert not list(mock_install_dir.iterdir())  # ファイルがインストールされていない

    def test_dry_run_resolve_shows_status_table(self, work_dir, mock_install_dir):
        """--dry-run --resolve でも状態テーブルが表示されること"""
        save_lock(make_google_fonts_lock(), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                result = runner.invoke(app, ["apply", "--dry-run", "--resolve"])

        assert result.exit_code == 0, result.output
        assert "Font Family" in result.output
        assert "Noto Sans JP" in result.output


# ---------------------------------------------------------------------------
# --resolve --json テスト
# ---------------------------------------------------------------------------


class TestApplyResolveJson:
    """--resolve --json の出力構造テスト"""

    def test_resolve_json_contains_resolve_results(self, work_dir, mock_install_dir):
        """--resolve --json → resolve_results フィールドを含む JSON を出力すること"""
        zip_content = create_test_zip()
        save_lock(make_google_fonts_lock(), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                with patch(
                    "src.resolver.httpx.Client",
                    return_value=make_mock_http_client(zip_content),
                ):
                    result = runner.invoke(app, ["apply", "--resolve", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "resolve_results" in data
        assert isinstance(data["resolve_results"], list)
        assert len(data["resolve_results"]) == 1

        rr = data["resolve_results"][0]
        assert "family" in rr
        assert "action" in rr
        assert "message" in rr

    def test_resolve_json_action_downloaded_on_success(self, work_dir, mock_install_dir):
        """DL 成功時の action が 'downloaded' であること"""
        zip_content = create_test_zip()
        save_lock(make_google_fonts_lock(), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                with patch(
                    "src.resolver.httpx.Client",
                    return_value=make_mock_http_client(zip_content),
                ):
                    result = runner.invoke(app, ["apply", "--resolve", "--json"])

        data = json.loads(result.output)
        assert data["resolve_results"][0]["action"] == "downloaded"

    def test_dry_run_resolve_json_has_empty_results_and_dry_run_flag(
        self, work_dir, mock_install_dir
    ):
        """--dry-run --resolve --json → resolve_results は空配列、dry_run=true"""
        save_lock(make_google_fonts_lock(), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                result = runner.invoke(app, ["apply", "--dry-run", "--resolve", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "resolve_results" in data
        assert data["resolve_results"] == []
        assert data.get("dry_run") is True

    def test_resolve_json_error_action_on_failure(self, work_dir, mock_install_dir):
        """ネットワークエラー時の action が 'failed' であること"""
        save_lock(make_google_fonts_lock(), work_dir / _LOCK_FILE_NAME)

        with patch("src.commands.apply.enumerate_installed_fonts", return_value=[]):
            with patch("src.commands.apply._DEFAULT_INSTALL_DIR", mock_install_dir):
                with patch(
                    "src.resolver.httpx.Client",
                    return_value=make_error_http_client(),
                ):
                    result = runner.invoke(app, ["apply", "--resolve", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "resolve_results" in data
        assert data["resolve_results"][0]["action"] == "failed"
        assert data["resolve_results"][0]["error"] is not None
