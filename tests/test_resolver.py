"""resolver モジュールのテスト

ResolverProtocol, ResolveResult, GoogleFontsResolver（httpx MockTransport 使用）,
AdobeFontsHandler, CommercialHandler, UnavailableHandler, resolve_fonts() の全コンポーネントをテスト。
"""

import hashlib
import zipfile
from io import BytesIO

import httpx

from src.font_status import FontStatus, JudgmentResult
from src.lockfile import LockFont
from src.resolver import (
    AdobeFontsHandler,
    CommercialHandler,
    GoogleFontsResolver,
    ResolveResult,
    UnavailableHandler,
    resolve_fonts,
)

# ---------------------------------------------------------------------------
# テストヘルパー
# ---------------------------------------------------------------------------


def create_test_zip(
    font_filename: str = "TestFont-Regular.ttf",
    font_content: bytes = b"dummy ttf content",
    extra_files: dict | None = None,
) -> bytes:
    """テスト用の Google Fonts-style ZIP を生成"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(font_filename, font_content)
        if extra_files:
            for name, content in extra_files.items():
                zf.writestr(name, content)
    return buf.getvalue()


def make_lock_font(
    family: str = "Noto Sans JP",
    source: str = "google-fonts",
    hash_: str | None = None,
) -> LockFont:
    return LockFont(family=family, source=source, styles=[], hash=hash_)


def make_judgment_result(
    lock_font: LockFont,
    status: FontStatus,
    action_message: str = "",
) -> JudgmentResult:
    return JudgmentResult(
        font=lock_font,
        status=status,
        action_message=action_message,
    )


# ---------------------------------------------------------------------------
# ResolveResult テスト
# ---------------------------------------------------------------------------


class TestResolveResult:
    def test_resolve_result_success_defaults(self):
        """ResolveResult の成功デフォルト値"""
        result = ResolveResult(success=True, font_family="TestFont")
        assert result.success is True
        assert result.font_family == "TestFont"
        assert result.installed_files == []
        assert result.message == ""
        assert result.error is None

    def test_resolve_result_failure(self):
        """ResolveResult の失敗フィールド"""
        result = ResolveResult(
            success=False,
            font_family="TestFont",
            message="失敗しました",
            error="404 Not Found",
        )
        assert result.success is False
        assert result.error == "404 Not Found"
        assert result.message == "失敗しました"


# ---------------------------------------------------------------------------
# can_resolve テスト
# ---------------------------------------------------------------------------


class TestCanResolve:
    def test_google_resolver_can_resolve_google_fonts(self, tmp_path):
        resolver = GoogleFontsResolver(install_dir=tmp_path)
        assert resolver.can_resolve(make_lock_font(source="google-fonts")) is True

    def test_google_resolver_cannot_resolve_adobe(self, tmp_path):
        resolver = GoogleFontsResolver(install_dir=tmp_path)
        assert resolver.can_resolve(make_lock_font(source="adobe-fonts")) is False

    def test_google_resolver_cannot_resolve_commercial(self, tmp_path):
        resolver = GoogleFontsResolver(install_dir=tmp_path)
        assert resolver.can_resolve(make_lock_font(source="commercial")) is False

    def test_google_resolver_cannot_resolve_local(self, tmp_path):
        resolver = GoogleFontsResolver(install_dir=tmp_path)
        assert resolver.can_resolve(make_lock_font(source="local")) is False

    def test_adobe_handler_can_resolve_adobe(self):
        handler = AdobeFontsHandler()
        assert handler.can_resolve(make_lock_font(source="adobe-fonts")) is True

    def test_adobe_handler_cannot_resolve_local(self):
        handler = AdobeFontsHandler()
        assert handler.can_resolve(make_lock_font(source="local")) is False

    def test_commercial_handler_can_resolve_commercial(self):
        handler = CommercialHandler()
        assert handler.can_resolve(make_lock_font(source="commercial")) is True

    def test_commercial_handler_cannot_resolve_local(self):
        handler = CommercialHandler()
        assert handler.can_resolve(make_lock_font(source="local")) is False

    def test_unavailable_handler_can_resolve_any_source(self):
        """UnavailableHandler はどの source でも True を返す（フォールバック）"""
        handler = UnavailableHandler()
        for source in ["local", "system", "unknown", "anything"]:
            assert handler.can_resolve(make_lock_font(source=source)) is True


# ---------------------------------------------------------------------------
# GoogleFontsResolver.resolve() テスト
# ---------------------------------------------------------------------------


class TestGoogleFontsResolverDownload:
    def test_resolve_success_installs_ttf(self, tmp_path):
        """DL 成功 → .ttf がインストールされること"""
        zip_content = create_test_zip("NotoSansJP-Regular.ttf", b"ttf data")

        def handler(request):
            return httpx.Response(200, content=zip_content)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver = GoogleFontsResolver(install_dir=tmp_path, client=client, rate_limit_sec=0)
        font = make_lock_font(family="Noto Sans JP", source="google-fonts")
        result = resolver.resolve(font)

        assert result.success is True
        assert (tmp_path / "NotoSansJP-Regular.ttf").exists()
        assert len(result.installed_files) == 1

    def test_resolve_success_with_otf(self, tmp_path):
        """DL 成功 → .otf がインストールされること"""
        zip_content = create_test_zip("TestFont-Regular.otf", b"otf data")

        def handler(request):
            return httpx.Response(200, content=zip_content)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver = GoogleFontsResolver(install_dir=tmp_path, client=client, rate_limit_sec=0)
        result = resolver.resolve(make_lock_font())

        assert result.success is True
        assert (tmp_path / "TestFont-Regular.otf").exists()

    def test_resolve_failure_404(self, tmp_path):
        """404 エラー → success=False, error あり"""

        def handler(request):
            return httpx.Response(404)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver = GoogleFontsResolver(install_dir=tmp_path, client=client, rate_limit_sec=0)
        result = resolver.resolve(make_lock_font())

        assert result.success is False
        assert result.error is not None

    def test_resolve_failure_connect_error(self, tmp_path):
        """ネットワークエラー → success=False"""

        def handler(request):
            raise httpx.ConnectError("Connection refused")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver = GoogleFontsResolver(install_dir=tmp_path, client=client, rate_limit_sec=0)
        result = resolver.resolve(make_lock_font())

        assert result.success is False
        assert result.error is not None

    def test_resolve_hash_match_installs(self, tmp_path):
        """ハッシュ一致 → インストール成功"""
        zip_content = create_test_zip()
        zip_hash = hashlib.sha256(zip_content).hexdigest()

        def handler(request):
            return httpx.Response(200, content=zip_content)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver = GoogleFontsResolver(install_dir=tmp_path, client=client, rate_limit_sec=0)
        font = make_lock_font(hash_=zip_hash)
        result = resolver.resolve(font)

        assert result.success is True

    def test_resolve_hash_mismatch_aborts(self, tmp_path):
        """ハッシュ不一致 → インストール中止"""
        zip_content = create_test_zip()

        def handler(request):
            return httpx.Response(200, content=zip_content)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver = GoogleFontsResolver(install_dir=tmp_path, client=client, rate_limit_sec=0)
        font = make_lock_font(hash_="wronghash123")
        result = resolver.resolve(font)

        assert result.success is False
        assert result.error is not None
        assert not any(tmp_path.iterdir())  # ファイルがインストールされていないこと

    def test_resolve_no_hash_installs_with_warning(self, tmp_path, caplog):
        """ハッシュ未記録 → 警告ログを出してインストール続行"""
        import logging

        zip_content = create_test_zip()

        def handler(request):
            return httpx.Response(200, content=zip_content)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver = GoogleFontsResolver(install_dir=tmp_path, client=client, rate_limit_sec=0)
        font = make_lock_font(hash_=None)

        with caplog.at_level(logging.WARNING):
            result = resolver.resolve(font)

        assert result.success is True
        assert len(result.installed_files) > 0

    def test_resolve_skips_existing_file(self, tmp_path):
        """既存ファイルはスキップされること（上書きしない）"""
        existing = tmp_path / "TestFont-Regular.ttf"
        existing.write_bytes(b"original content")

        zip_content = create_test_zip("TestFont-Regular.ttf", b"new content")

        def handler(request):
            return httpx.Response(200, content=zip_content)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver = GoogleFontsResolver(install_dir=tmp_path, client=client, rate_limit_sec=0)
        resolver.resolve(make_lock_font())

        # 既存ファイルが上書きされていないこと
        assert existing.read_bytes() == b"original content"


# ---------------------------------------------------------------------------
# ZIP セキュリティテスト
# ---------------------------------------------------------------------------


class TestZipSecurity:
    def test_non_font_files_excluded(self, tmp_path):
        """.exe ファイルは除外されること"""
        zip_content = create_test_zip(
            font_filename="TestFont-Regular.ttf",
            font_content=b"ttf data",
            extra_files={"malware.exe": b"evil executable"},
        )

        def handler(request):
            return httpx.Response(200, content=zip_content)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver = GoogleFontsResolver(install_dir=tmp_path, client=client, rate_limit_sec=0)
        result = resolver.resolve(make_lock_font())

        assert result.success is True
        assert (tmp_path / "TestFont-Regular.ttf").exists()
        assert not (tmp_path / "malware.exe").exists()

    def test_path_traversal_prevented(self, tmp_path):
        """ZIP 内のパストラバーサル攻撃が防がれること"""
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../evil.ttf", b"evil ttf")
            zf.writestr("GoodFont.ttf", b"good ttf")
        zip_content = buf.getvalue()

        def handler(request):
            return httpx.Response(200, content=zip_content)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver = GoogleFontsResolver(install_dir=tmp_path, client=client, rate_limit_sec=0)
        resolver.resolve(make_lock_font())

        # tmp_path 外に evil.ttf が書き込まれていないこと
        assert not (tmp_path.parent.parent / "evil.ttf").exists()
        # GoodFont.ttf はインストールされること
        assert (tmp_path / "GoodFont.ttf").exists()


# ---------------------------------------------------------------------------
# AdobeFontsHandler テスト
# ---------------------------------------------------------------------------


class TestAdobeFontsHandler:
    def test_resolve_returns_creative_cloud_message(self):
        handler = AdobeFontsHandler()
        font = make_lock_font(family="Adobe Font", source="adobe-fonts")
        result = handler.resolve(font)

        assert result.success is False
        assert "Creative Cloud" in result.message or "有効化" in result.message
        assert result.font_family == "Adobe Font"

    def test_resolve_no_error_field(self):
        handler = AdobeFontsHandler()
        result = handler.resolve(make_lock_font(source="adobe-fonts"))
        assert result.error is None


# ---------------------------------------------------------------------------
# CommercialHandler テスト
# ---------------------------------------------------------------------------


class TestCommercialHandler:
    def test_resolve_returns_purchase_message(self):
        handler = CommercialHandler()
        font = make_lock_font(family="Commercial Font", source="commercial")
        result = handler.resolve(font)

        assert result.success is False
        assert "購入" in result.message
        assert result.font_family == "Commercial Font"

    def test_resolve_no_error_field(self):
        handler = CommercialHandler()
        result = handler.resolve(make_lock_font(source="commercial"))
        assert result.error is None


# ---------------------------------------------------------------------------
# UnavailableHandler テスト
# ---------------------------------------------------------------------------


class TestUnavailableHandler:
    def test_resolve_returns_unavailable_message(self):
        handler = UnavailableHandler()
        font = make_lock_font(family="Local Font", source="local")
        result = handler.resolve(font)

        assert result.success is False
        assert result.font_family == "Local Font"
        assert "不明" in result.message or "入手" in result.message

    def test_resolve_no_error_field(self):
        handler = UnavailableHandler()
        result = handler.resolve(make_lock_font(source="local"))
        assert result.error is None


# ---------------------------------------------------------------------------
# resolve_fonts オーケストレータテスト
# ---------------------------------------------------------------------------


class TestResolveFonts:
    def test_skips_installed_fonts(self, tmp_path):
        """INSTALLED フォントはスキップされ結果に含まれないこと"""
        font = make_lock_font(source="google-fonts")
        results = [make_judgment_result(font, FontStatus.INSTALLED)]

        resolve_results = resolve_fonts(results, install_dir=tmp_path)

        assert resolve_results == []

    def test_handles_resolvable_with_google_fonts(self, tmp_path):
        """RESOLVABLE → GoogleFontsResolver で処理されること"""
        zip_content = create_test_zip()

        def handler(request):
            return httpx.Response(200, content=zip_content)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        font = make_lock_font(source="google-fonts")
        results = [make_judgment_result(font, FontStatus.RESOLVABLE)]

        resolve_results = resolve_fonts(results, install_dir=tmp_path, client=client, rate_limit_sec=0)

        assert len(resolve_results) == 1
        assert resolve_results[0].font_family == "Noto Sans JP"

    def test_handles_activatable_with_adobe(self, tmp_path):
        """ACTIVATABLE → AdobeFontsHandler で処理されること"""
        font = make_lock_font(source="adobe-fonts")
        results = [make_judgment_result(font, FontStatus.ACTIVATABLE)]

        resolve_results = resolve_fonts(results, install_dir=tmp_path)

        assert len(resolve_results) == 1
        assert resolve_results[0].success is False
        assert "Creative Cloud" in resolve_results[0].message or "有効化" in resolve_results[0].message

    def test_handles_purchasable_with_commercial(self, tmp_path):
        """PURCHASABLE → CommercialHandler で処理されること"""
        font = make_lock_font(source="commercial")
        results = [make_judgment_result(font, FontStatus.PURCHASABLE)]

        resolve_results = resolve_fonts(results, install_dir=tmp_path)

        assert len(resolve_results) == 1
        assert resolve_results[0].success is False
        assert "購入" in resolve_results[0].message

    def test_handles_unavailable(self, tmp_path):
        """UNAVAILABLE → UnavailableHandler で処理されること"""
        font = make_lock_font(source="local")
        results = [make_judgment_result(font, FontStatus.UNAVAILABLE)]

        resolve_results = resolve_fonts(results, install_dir=tmp_path)

        assert len(resolve_results) == 1
        assert resolve_results[0].success is False

    def test_empty_results(self, tmp_path):
        """空の results → 空のリストを返すこと"""
        assert resolve_fonts([], install_dir=tmp_path) == []

    def test_mixed_results(self, tmp_path):
        """混在ケース: installed はスキップ、それ以外は処理されること"""
        zip_content = create_test_zip()

        def handler(request):
            return httpx.Response(200, content=zip_content)

        client = httpx.Client(transport=httpx.MockTransport(handler))

        results = [
            make_judgment_result(make_lock_font(source="google-fonts"), FontStatus.INSTALLED),
            make_judgment_result(make_lock_font(source="google-fonts"), FontStatus.RESOLVABLE),
            make_judgment_result(make_lock_font(source="adobe-fonts"), FontStatus.ACTIVATABLE),
        ]

        resolve_results = resolve_fonts(results, install_dir=tmp_path, client=client, rate_limit_sec=0)

        # INSTALLED は除外 → 2件
        assert len(resolve_results) == 2
