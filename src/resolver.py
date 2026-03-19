"""フォント自動解決モジュール

fontops.lock で定義されたフォントのうち未インストールのものを自動解決する。

- Google Fonts: API 経由で DL + ZIP 展開 + SHA-256 hash 検証 + インストール
- Adobe Fonts: Creative Cloud での有効化を案内
- Commercial: 購入を案内
- Unavailable: 入手方法不明を報告
"""

import hashlib
import logging
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import httpx

from .font_status import FontStatus, JudgmentResult
from .lockfile import LockFont

logger = logging.getLogger(__name__)

_GOOGLE_FONTS_DOWNLOAD_URL = "https://fonts.google.com/download?family={family}"
_FONT_EXTENSIONS = frozenset([".ttf", ".otf"])


@dataclass
class ResolveResult:
    """フォント解決結果"""

    success: bool
    font_family: str
    installed_files: List[Path] = field(default_factory=list)
    message: str = ""
    error: Optional[str] = None


class GoogleFontsResolver:
    """Google Fonts からフォントをダウンロード・インストールするリゾルバー"""

    def __init__(
        self,
        install_dir: Path,
        client: Optional[httpx.Client] = None,
        rate_limit_sec: float = 1.0,
    ) -> None:
        self._install_dir = install_dir
        self._client = client
        self._rate_limit_sec = rate_limit_sec

    def can_resolve(self, lock_font: LockFont) -> bool:
        return lock_font.source == "google-fonts"

    def resolve(self, lock_font: LockFont) -> ResolveResult:
        client = self._client or httpx.Client()
        family_encoded = lock_font.family.replace(" ", "+")
        url = _GOOGLE_FONTS_DOWNLOAD_URL.format(family=family_encoded)

        # ダウンロード
        try:
            response = client.get(url)
            response.raise_for_status()
        except Exception as e:
            return ResolveResult(
                success=False,
                font_family=lock_font.family,
                message="ダウンロードに失敗しました",
                error=str(e),
            )

        zip_content = response.content

        # SHA-256 hash 検証（ZIP ファイル全体のハッシュ）
        if lock_font.hash:
            actual_hash = hashlib.sha256(zip_content).hexdigest()
            if actual_hash != lock_font.hash:
                return ResolveResult(
                    success=False,
                    font_family=lock_font.family,
                    message="ハッシュ検証に失敗しました（インストールを中止します）",
                    error=f"期待: {lock_font.hash}, 実際: {actual_hash}",
                )
        else:
            logger.warning(
                "hash が未定義です。%s のダウンロード検証をスキップします。",
                lock_font.family,
            )

        # ZIP 展開 + インストール
        try:
            installed_files = self._extract_and_install(zip_content)
        except (zipfile.BadZipFile, ValueError) as e:
            return ResolveResult(
                success=False,
                font_family=lock_font.family,
                message="ZIP の展開に失敗しました",
                error=str(e),
            )

        # レート制限
        if self._rate_limit_sec > 0:
            time.sleep(self._rate_limit_sec)

        return ResolveResult(
            success=True,
            font_family=lock_font.family,
            installed_files=installed_files,
            message=f"{lock_font.family} をインストールしました",
        )

    def _extract_and_install(self, zip_content: bytes) -> List[Path]:
        """ZIP を展開し、フォントファイルをインストールディレクトリにコピーする。

        セキュリティ:
        - extractall は使用しない（path traversal 対策）
        - .ttf/.otf のみを抽出
        - 同名ファイルが存在する場合はスキップ（上書きしない）
        """
        installed_files: List[Path] = []
        self._install_dir.mkdir(parents=True, exist_ok=True)

        try:
            zf = zipfile.ZipFile(BytesIO(zip_content))
        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid ZIP: {e}") from e

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with zf:
                for name in zf.namelist():
                    # パストラバーサル対策: ファイル名のみ使用（ディレクトリ成分を除去）
                    safe_name = Path(name).name
                    if not safe_name:
                        continue

                    # 拡張子フィルタ: .ttf/.otf のみ
                    if Path(safe_name).suffix.lower() not in _FONT_EXTENSIONS:
                        continue

                    # 一時ディレクトリに展開
                    data = zf.read(name)
                    tmp_file = tmp_path / safe_name
                    tmp_file.write_bytes(data)

                    # インストール（既存ファイルはスキップ）
                    dest = self._install_dir / safe_name
                    if not dest.exists():
                        shutil.copy2(tmp_file, dest)

                    installed_files.append(dest)

        return installed_files


class AdobeFontsHandler:
    """Adobe Fonts フォントの案内ハンドラー"""

    def can_resolve(self, lock_font: LockFont) -> bool:
        return lock_font.source == "adobe-fonts"

    def resolve(self, lock_font: LockFont) -> ResolveResult:
        return ResolveResult(
            success=False,
            font_family=lock_font.family,
            message=f"Creative Cloud アプリで {lock_font.family} を有効化してください",
        )


class CommercialHandler:
    """商用フォントの案内ハンドラー"""

    def can_resolve(self, lock_font: LockFont) -> bool:
        return lock_font.source == "commercial"

    def resolve(self, lock_font: LockFont) -> ResolveResult:
        return ResolveResult(
            success=False,
            font_family=lock_font.family,
            message=f"{lock_font.family} の購入が必要です",
        )


class UnavailableHandler:
    """解決不可能なフォントのフォールバックハンドラー"""

    def can_resolve(self, lock_font: LockFont) -> bool:
        return True  # フォールバック: 常に True

    def resolve(self, lock_font: LockFont) -> ResolveResult:
        return ResolveResult(
            success=False,
            font_family=lock_font.family,
            message=f"{lock_font.family} の入手方法が不明です",
        )


def resolve_fonts(
    results: List[JudgmentResult],
    install_dir: Path,
    client: Optional[httpx.Client] = None,
    rate_limit_sec: float = 1.0,
) -> List[ResolveResult]:
    """フォント判定結果のリストを受け取り、適切なハンドラーで解決する。

    INSTALLED フォントはスキップする。
    各フォントの source に応じてハンドラーを選択する。

    Args:
        results: judge_all() の返却値
        install_dir: フォントのインストール先ディレクトリ
        client: httpx.Client（テスト用 DI）
        rate_limit_sec: Google Fonts DL 後のウェイト秒数

    Returns:
        List[ResolveResult]: INSTALLED 以外のフォントの解決結果
    """
    google_resolver = GoogleFontsResolver(
        install_dir=install_dir,
        client=client,
        rate_limit_sec=rate_limit_sec,
    )
    adobe_handler = AdobeFontsHandler()
    commercial_handler = CommercialHandler()
    unavailable_handler = UnavailableHandler()

    # 優先順位順に並べる（UnavailableHandler は最後のフォールバック）
    handlers = [google_resolver, adobe_handler, commercial_handler, unavailable_handler]

    resolve_results: List[ResolveResult] = []

    for judgment in results:
        # INSTALLED はスキップ
        if judgment.status == FontStatus.INSTALLED:
            continue

        lock_font = judgment.font
        handler = next(
            (h for h in handlers if h.can_resolve(lock_font)),
            unavailable_handler,
        )
        result = handler.resolve(lock_font)
        resolve_results.append(result)

    return resolve_results
