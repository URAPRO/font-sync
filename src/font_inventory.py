"""インストール済みフォントの列挙モジュール"""

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# サポートする拡張子
_FONT_EXTENSIONS = frozenset((".ttf", ".otf", ".ttc", ".otc"))

# Adobe CoreSync パスマーカー
_ADOBE_CORYSYNC_MARKERS = ("Adobe/CoreSync", "Adobe CoreSync")

# セッション内キャッシュ
_cache: Optional[List["InstalledFont"]] = None


def _default_scan_dirs() -> List[Path]:
    """デフォルトのスキャン対象ディレクトリを返す。

    /System/Library/Fonts/ は意図的に除外している。
    """
    return [
        Path.home() / "Library" / "Fonts",
        Path("/Library/Fonts"),
    ]


@dataclass
class InstalledFont:
    """インストール済みフォントの情報"""

    family: str
    style: str
    path: Path
    source: str  # 'local' | 'adobe-fonts'


def _classify_source(path: Path) -> str:
    """フォントのソースを分類する。

    realpath に 'Adobe/CoreSync' または 'Adobe CoreSync' を含む → 'adobe-fonts'
    それ以外 → 'local'
    """
    try:
        real = os.path.realpath(path)
    except Exception:
        return "local"

    for marker in _ADOBE_CORYSYNC_MARKERS:
        if marker in real:
            return "adobe-fonts"

    return "local"


def _get_best_name(name_table, name_id: int) -> Optional[str]:
    """name テーブルから最良のレコードを取得する。

    優先順位: Windows Unicode BMP (3, 1) → Mac Roman (1, 0) → 任意
    """
    # Windows BMP + English US を優先
    record = name_table.getName(name_id, 3, 1, 0x0409)
    if record is not None:
        try:
            return record.toUnicode()
        except Exception:
            pass

    # 言語非依存で Windows BMP から探す
    for rec in name_table.names:
        if rec.nameID == name_id and rec.platformID == 3 and rec.platEncID == 1:
            try:
                return rec.toUnicode()
            except Exception:
                pass

    # Mac Roman フォールバック
    record = name_table.getName(name_id, 1, 0, 0)
    if record is not None:
        try:
            return record.toUnicode()
        except Exception:
            pass

    # どの platform でも探す
    for rec in name_table.names:
        if rec.nameID == name_id:
            try:
                return rec.toUnicode()
            except Exception:
                pass

    return None


def _read_name_from_font(font, fallback_stem: str) -> Tuple[str, str]:
    """TTFont オブジェクトから (family, style) を読み取る。"""
    name_table = font.get("name")
    if name_table is None:
        return (fallback_stem, "Regular")

    family = _get_best_name(name_table, 1)
    style = _get_best_name(name_table, 2)
    return (family or fallback_stem, style or "Regular")


def _extract_font_names(path: Path) -> List[Tuple[str, str]]:
    """fontTools で family/style 名を抽出する。

    .ttc/.otc は TTCollection で複数フォントを展開。
    読めないファイルは警告ログを出して空リストを返す（例外を raise しない）。

    Returns:
        List of (family, style) tuples
    """
    from fontTools.ttLib import TTFont  # noqa: PLC0415

    results: List[Tuple[str, str]] = []
    suffix = path.suffix.lower()
    stem = path.stem

    if suffix in (".ttc", ".otc"):
        try:
            from fontTools.ttLib import TTCollection  # noqa: PLC0415

            collection = TTCollection(str(path))
            for i in range(len(collection)):
                try:
                    font = collection[i]
                    family, style = _read_name_from_font(font, stem)
                    results.append((family, style))
                except Exception as e:
                    logger.warning(
                        "TTC インデックス %d 読み込みエラー（スキップ）: %s - %s", i, path, e
                    )
        except Exception as e:
            logger.warning("フォントコレクション読み込みエラー（スキップ）: %s - %s", path, e)
    else:
        try:
            font = TTFont(str(path))
            family, style = _read_name_from_font(font, stem)
            results.append((family, style))
        except Exception as e:
            logger.warning("フォント読み込みエラー（スキップ）: %s - %s", path, e)

    return results


def calculate_font_hash(path: Path) -> str:
    """フォントファイルの SHA-256 ハッシュを計算する。

    Args:
        path: フォントファイルのパス

    Returns:
        SHA-256 hex digest 文字列
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def enumerate_installed_fonts(
    dirs: Optional[List[Path]] = None,
    use_cache: bool = True,
) -> List[InstalledFont]:
    """インストール済みフォントを列挙する。

    デフォルトでは ~/Library/Fonts/ と /Library/Fonts/ をスキャン。
    /System/Library/Fonts/ は除外（デフォルトスキャン対象外）。

    Args:
        dirs: スキャン対象ディレクトリのリスト。None の場合はデフォルト。
        use_cache: True かつ dirs=None の場合、セッション内キャッシュを使用。

    Returns:
        InstalledFont のリスト。
    """
    global _cache

    # キャッシュは dirs=None の場合のみ有効
    if use_cache and dirs is None and _cache is not None:
        return _cache

    scan_dirs = dirs if dirs is not None else _default_scan_dirs()
    results: List[InstalledFont] = []

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue

        for font_path in sorted(scan_dir.rglob("*")):
            if not font_path.is_file():
                continue
            if font_path.suffix.lower() not in _FONT_EXTENSIONS:
                continue
            if font_path.name.startswith("."):
                continue

            # 0 バイトファイルはスキップ
            try:
                if font_path.stat().st_size == 0:
                    logger.warning("空のフォントファイル（スキップ）: %s", font_path)
                    continue
            except Exception:
                continue

            source = _classify_source(font_path)
            names = _extract_font_names(font_path)

            for family, style in names:
                results.append(
                    InstalledFont(family=family, style=style, path=font_path, source=source)
                )

    if use_cache and dirs is None:
        _cache = results

    return results


def clear_cache() -> None:
    """セッション内キャッシュをリセットする。"""
    global _cache
    _cache = None
