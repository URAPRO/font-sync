"""font_status モジュールのテスト"""

from pathlib import Path

import pytest

from src.font_inventory import InstalledFont
from src.font_status import (
    FontStatus,
    JudgmentResult,
    judge_all,
    judge_font_status,
)
from src.lockfile import FontopsLock, LockFont


class TestFontStatusEnum:
    """FontStatus enum のテスト"""

    def test_font_status_has_five_values(self):
        """FontStatus が 5 つの値を持つこと"""
        assert len(FontStatus) == 5

    def test_font_status_expected_values_exist(self):
        """FontStatus が期待する 5 値を持つこと"""
        assert FontStatus.INSTALLED
        assert FontStatus.RESOLVABLE
        assert FontStatus.ACTIVATABLE
        assert FontStatus.PURCHASABLE
        assert FontStatus.UNAVAILABLE

    def test_font_status_all_have_label(self):
        """FontStatus の全値に非空の label があること"""
        for status in FontStatus:
            assert isinstance(status.label, str), f"{status} の label が str でない"
            assert len(status.label) > 0, f"{status} の label が空"

    def test_font_status_all_have_icon(self):
        """FontStatus の全値に非空の icon があること"""
        for status in FontStatus:
            assert isinstance(status.icon, str), f"{status} の icon が str でない"
            assert len(status.icon) > 0, f"{status} の icon が空"

    def test_font_status_all_have_color(self):
        """FontStatus の全値に非空の color があること"""
        for status in FontStatus:
            assert isinstance(status.color, str), f"{status} の color が str でない"
            assert len(status.color) > 0, f"{status} の color が空"

    def test_font_status_installed_color_is_green(self):
        """INSTALLED の color が green であること"""
        assert FontStatus.INSTALLED.color == "green"

    def test_font_status_resolvable_color_is_blue(self):
        """RESOLVABLE の color が blue であること"""
        assert FontStatus.RESOLVABLE.color == "blue"

    def test_font_status_activatable_color_is_yellow(self):
        """ACTIVATABLE の color が yellow であること"""
        assert FontStatus.ACTIVATABLE.color == "yellow"

    def test_font_status_purchasable_color_is_cyan(self):
        """PURCHASABLE の color が cyan であること"""
        assert FontStatus.PURCHASABLE.color == "cyan"

    def test_font_status_unavailable_color_is_red(self):
        """UNAVAILABLE の color が red であること"""
        assert FontStatus.UNAVAILABLE.color == "red"


class TestJudgeFontStatus:
    """judge_font_status 関数のテスト"""

    @pytest.mark.parametrize(
        "source,installed,expected_status",
        [
            ("google-fonts", True, FontStatus.INSTALLED),
            ("google-fonts", False, FontStatus.RESOLVABLE),
            ("adobe-fonts", True, FontStatus.INSTALLED),
            ("adobe-fonts", False, FontStatus.ACTIVATABLE),
            ("commercial", True, FontStatus.INSTALLED),
            ("commercial", False, FontStatus.PURCHASABLE),
            ("local", True, FontStatus.INSTALLED),
            ("local", False, FontStatus.UNAVAILABLE),
            ("system", True, FontStatus.INSTALLED),
            ("system", False, FontStatus.UNAVAILABLE),
        ],
    )
    def test_judge_font_status_parametrized(self, source, installed, expected_status):
        """source × installed の全 10 パターンを正しく判定すること"""
        lock_font = LockFont(family="TestFont", source=source, styles=[])
        installed_families = {"testfont"} if installed else set()
        result = judge_font_status(lock_font, installed_families)
        assert result.status == expected_status

    def test_judge_font_status_returns_judgment_result(self):
        """judge_font_status が JudgmentResult を返すこと"""
        lock_font = LockFont(family="Roboto", source="google-fonts", styles=[])
        result = judge_font_status(lock_font, {"roboto"})
        assert isinstance(result, JudgmentResult)

    def test_judge_font_status_result_contains_lock_font(self):
        """JudgmentResult.font が入力の lock_font と同じであること"""
        lock_font = LockFont(family="Roboto", source="google-fonts", styles=[])
        result = judge_font_status(lock_font, {"roboto"})
        assert result.font is lock_font

    def test_judge_font_status_case_insensitive_match(self):
        """family 名の大文字小文字を区別せず判定すること"""
        lock_font = LockFont(family="Helvetica Neue", source="local", styles=[])
        # installed_families は大文字で登録されている場合
        installed_families = {"HELVETICA NEUE"}
        result = judge_font_status(lock_font, installed_families)
        assert result.status == FontStatus.INSTALLED

    def test_judge_font_status_case_insensitive_mixed_case(self):
        """混合ケースの family 名でも正しく判定すること"""
        lock_font = LockFont(family="SF Pro", source="system", styles=[])
        installed_families = {"sf pro"}
        result = judge_font_status(lock_font, installed_families)
        assert result.status == FontStatus.INSTALLED

    def test_judge_font_status_resolvable_action_message(self):
        """RESOLVABLE の action_message が 'Google Fonts' を含むこと"""
        lock_font = LockFont(family="Roboto", source="google-fonts", styles=[])
        result = judge_font_status(lock_font, set())
        assert "Google Fonts" in result.action_message

    def test_judge_font_status_activatable_action_message(self):
        """ACTIVATABLE の action_message が 'Creative Cloud' を含むこと"""
        lock_font = LockFont(family="Myriad Pro", source="adobe-fonts", styles=[])
        result = judge_font_status(lock_font, set())
        assert "Creative Cloud" in result.action_message

    def test_judge_font_status_purchasable_action_message(self):
        """PURCHASABLE の action_message が '購入' を含むこと"""
        lock_font = LockFont(family="Proxima Nova", source="commercial", styles=[])
        result = judge_font_status(lock_font, set())
        assert "購入" in result.action_message

    def test_judge_font_status_unavailable_action_message_is_nonempty(self):
        """UNAVAILABLE の action_message が空でないこと"""
        lock_font = LockFont(family="SomeFont", source="local", styles=[])
        result = judge_font_status(lock_font, set())
        assert isinstance(result.action_message, str)
        assert len(result.action_message) > 0

    def test_judge_font_status_installed_styles_are_list(self):
        """JudgmentResult.installed_styles がリストであること"""
        lock_font = LockFont(family="Inter", source="google-fonts", styles=[])
        result = judge_font_status(lock_font, {"inter"})
        assert isinstance(result.installed_styles, list)

    def test_judge_font_status_missing_styles_are_list(self):
        """JudgmentResult.missing_styles がリストであること"""
        lock_font = LockFont(family="Inter", source="google-fonts", styles=[])
        result = judge_font_status(lock_font, set())
        assert isinstance(result.missing_styles, list)

    def test_judge_font_status_unknown_source_is_unavailable(self):
        """不明なソース（'unknown' 等）は UNAVAILABLE になること"""
        lock_font = LockFont(family="SomeFont", source="unknown", styles=[])
        result = judge_font_status(lock_font, set())
        assert result.status == FontStatus.UNAVAILABLE


class TestJudgeAll:
    """judge_all 関数のテスト"""

    def test_judge_all_empty_lock_returns_empty_list(self):
        """空 lock の場合、空リストを返すこと"""
        lock = FontopsLock(fontops_version="1", project_name="test", fonts=[])
        result = judge_all(lock, [])
        assert result == []

    def test_judge_all_empty_installed_fonts_returns_non_installed(self):
        """installed_fonts が空の場合、INSTALLED 以外の判定が返ること"""
        lock = FontopsLock(
            fontops_version="1",
            project_name="test",
            fonts=[LockFont(family="Roboto", source="google-fonts", styles=[])],
        )
        results = judge_all(lock, [])
        assert len(results) == 1
        assert results[0].status == FontStatus.RESOLVABLE

    def test_judge_all_multiple_fonts_correct_statuses(self):
        """複数フォントを正しく判定すること（1つだけインストール済み）"""
        lock = FontopsLock(
            fontops_version="1",
            project_name="test",
            fonts=[
                LockFont(family="Roboto", source="google-fonts", styles=[]),
                LockFont(family="Myriad Pro", source="adobe-fonts", styles=[]),
                LockFont(family="Helvetica", source="local", styles=[]),
            ],
        )
        installed_fonts = [
            InstalledFont(
                family="Roboto",
                style="Regular",
                path=Path("/Library/Fonts/Roboto.ttf"),
                source="local",
            ),
        ]
        results = judge_all(lock, installed_fonts)
        assert len(results) == 3
        statuses = {r.font.family: r.status for r in results}
        assert statuses["Roboto"] == FontStatus.INSTALLED
        assert statuses["Myriad Pro"] == FontStatus.ACTIVATABLE
        assert statuses["Helvetica"] == FontStatus.UNAVAILABLE

    def test_judge_all_returns_list_of_judgment_results(self):
        """judge_all が JudgmentResult のリストを返すこと"""
        lock = FontopsLock(
            fontops_version="1",
            project_name="test",
            fonts=[LockFont(family="Inter", source="google-fonts", styles=[])],
        )
        results = judge_all(lock, [])
        assert all(isinstance(r, JudgmentResult) for r in results)

    def test_judge_all_installed_fonts_family_case_insensitive(self):
        """installed_fonts の family 名を case-insensitive で照合すること"""
        lock = FontopsLock(
            fontops_version="1",
            project_name="test",
            fonts=[LockFont(family="Inter", source="google-fonts", styles=[])],
        )
        # installed_fonts が大文字の family 名を持つ
        installed_fonts = [
            InstalledFont(
                family="INTER",
                style="Regular",
                path=Path("/Library/Fonts/Inter.ttf"),
                source="local",
            ),
        ]
        results = judge_all(lock, installed_fonts)
        assert results[0].status == FontStatus.INSTALLED

    def test_judge_all_all_installed(self):
        """全フォントがインストール済みの場合、全て INSTALLED になること"""
        lock = FontopsLock(
            fontops_version="1",
            project_name="test",
            fonts=[
                LockFont(family="Roboto", source="google-fonts", styles=[]),
                LockFont(family="Inter", source="commercial", styles=[]),
            ],
        )
        installed_fonts = [
            InstalledFont(family="Roboto", style="Regular", path=Path("/f/Roboto.ttf"), source="local"),
            InstalledFont(family="Inter", style="Regular", path=Path("/f/Inter.ttf"), source="local"),
        ]
        results = judge_all(lock, installed_fonts)
        assert all(r.status == FontStatus.INSTALLED for r in results)

    def test_judge_all_preserves_lock_font_order(self):
        """judge_all が lock の fonts 順序を保持すること"""
        lock = FontopsLock(
            fontops_version="1",
            project_name="test",
            fonts=[
                LockFont(family="FontA", source="google-fonts", styles=[]),
                LockFont(family="FontB", source="adobe-fonts", styles=[]),
                LockFont(family="FontC", source="commercial", styles=[]),
            ],
        )
        results = judge_all(lock, [])
        assert results[0].font.family == "FontA"
        assert results[1].font.family == "FontB"
        assert results[2].font.family == "FontC"
