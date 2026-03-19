"""フォント状態判定モジュール

fontops.lock のフォントとインストール済みフォントを照合し、
5 状態（INSTALLED / RESOLVABLE / ACTIVATABLE / PURCHASABLE / UNAVAILABLE）を判定する。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Set

from .font_inventory import InstalledFont
from .lockfile import FontopsLock, LockFont


class FontStatus(Enum):
    """フォントの状態を表す 5 値の列挙型。

    各値は (value, label, icon, color) のタプルで定義する。
    color は Rich マークアップで使用する色名。
    """

    INSTALLED = ("installed", "インストール済み", "✓", "green")
    RESOLVABLE = ("resolvable", "取得可能", "↓", "blue")
    ACTIVATABLE = ("activatable", "有効化可能", "◎", "yellow")
    PURCHASABLE = ("purchasable", "購入可能", "$", "cyan")
    UNAVAILABLE = ("unavailable", "入手不可", "✗", "red")

    def __new__(cls, value: str, label: str, icon: str, color: str) -> "FontStatus":
        obj = object.__new__(cls)
        obj._value_ = value
        obj._label = label
        obj._icon = icon
        obj._color = color
        return obj

    @property
    def label(self) -> str:
        """日本語ラベル"""
        return self._label  # type: ignore[attr-defined]

    @property
    def icon(self) -> str:
        """Rich テーブル用アイコン文字"""
        return self._icon  # type: ignore[attr-defined]

    @property
    def color(self) -> str:
        """Rich マークアップ用色名"""
        return self._color  # type: ignore[attr-defined]


@dataclass
class JudgmentResult:
    """フォント状態の判定結果。"""

    font: LockFont
    status: FontStatus
    action_message: str
    installed_styles: List[str] = field(default_factory=list)
    missing_styles: List[str] = field(default_factory=list)


def judge_font_status(
    lock_font: LockFont,
    installed_families: Set[str],
) -> JudgmentResult:
    """フォントの状態を判定する純粋関数。

    installed_families との case-insensitive マッチでインストール済みを判定し、
    未インストールの場合は source に基づいてアクションを提示する。

    Args:
        lock_font: 判定対象の LockFont
        installed_families: インストール済みファミリー名の小文字 set

    Returns:
        JudgmentResult
    """
    family_lower = lock_font.family.lower()

    # インストール済みかどうかを最優先で確認（source に関わらず）
    if family_lower in {f.lower() for f in installed_families}:
        return JudgmentResult(
            font=lock_font,
            status=FontStatus.INSTALLED,
            action_message="インストール済み",
        )

    source = lock_font.source

    if source == "google-fonts":
        return JudgmentResult(
            font=lock_font,
            status=FontStatus.RESOLVABLE,
            action_message="Google Fonts から取得可能",
        )
    elif source == "adobe-fonts":
        return JudgmentResult(
            font=lock_font,
            status=FontStatus.ACTIVATABLE,
            action_message="Creative Cloud で有効化",
        )
    elif source == "commercial":
        return JudgmentResult(
            font=lock_font,
            status=FontStatus.PURCHASABLE,
            action_message="購入が必要",
        )
    else:
        # source == "local" / "system" / その他
        return JudgmentResult(
            font=lock_font,
            status=FontStatus.UNAVAILABLE,
            action_message="入手方法不明",
        )


def judge_all(
    lock: FontopsLock,
    installed_fonts: List[InstalledFont],
) -> List[JudgmentResult]:
    """lock 全体のフォント状態を判定するオーケストレータ。

    installed_fonts から family 名の小文字 set を構築し、
    lock の各 LockFont に対して judge_font_status() を呼び出す。

    Args:
        lock: FontopsLock インスタンス
        installed_fonts: インストール済みフォントのリスト

    Returns:
        各フォントの JudgmentResult リスト（lock.fonts と同じ順序）
    """
    installed_families = {f.family.lower() for f in installed_fonts}
    return [judge_font_status(lf, installed_families) for lf in lock.fonts]
