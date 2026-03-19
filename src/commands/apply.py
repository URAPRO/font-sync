"""fontops.lock の状態確認コマンド"""

import json
from collections import Counter
from pathlib import Path
from typing import List

import typer
from rich.console import Console
from rich.table import Table

from ..font_inventory import enumerate_installed_fonts
from ..font_status import FontStatus, JudgmentResult, judge_all
from ..lockfile import FontopsLock, load_lock
from ..main import handle_errors

console = Console()

_LOCK_FILE = Path("fontops.lock")


# ---------------------------------------------------------------------------
# 内部実装（@handle_errors 適用）
# ---------------------------------------------------------------------------


@handle_errors
def apply_command(resolve: bool, dry_run: bool, json_output: bool) -> None:  # noqa: ARG001
    """apply コマンドの実装。

    fontops.lock を読み込み、インストール済みフォントと照合して状態を表示する。
    --dry-run は --resolve と組み合わせて意味を持つ（現時点では通常と同じ動作）。
    """
    if not _LOCK_FILE.exists():
        console.print(
            "[red]エラー: fontops.lock が見つかりません。"
            "font-sync lock init で作成してください。[/red]"
        )
        raise typer.Exit(1)

    lock = load_lock(_LOCK_FILE)

    if not lock.fonts:
        console.print("[yellow]フォントが定義されていません[/yellow]")
        return

    installed_fonts = enumerate_installed_fonts()
    results = judge_all(lock, installed_fonts)

    if json_output:
        _output_json(lock, results)
        return

    if resolve:
        console.print("[yellow]resolve 機能は未実装です（m5-f3 で実装予定）[/yellow]")

    _render_report(results)


# ---------------------------------------------------------------------------
# 出力ヘルパー
# ---------------------------------------------------------------------------


def _render_report(results: List[JudgmentResult]) -> None:
    """Rich Table でフォント状態レポートを表示。"""
    table = Table(title="fontops.lock フォント状態")
    table.add_column("Font Family", style="cyan")
    table.add_column("Source", style="magenta")
    table.add_column("Status")
    table.add_column("Action")

    for result in results:
        status_text = (
            f"[{result.status.color}]"
            f"{result.status.icon} {result.status.label}"
            f"[/{result.status.color}]"
        )
        table.add_row(
            result.font.family,
            result.font.source,
            status_text,
            result.action_message,
        )

    console.print(table)

    # サマリー行
    counts = Counter(r.status for r in results)
    summary_parts = []
    for status in FontStatus:
        count = counts.get(status, 0)
        if count > 0:
            summary_parts.append(
                f"[{status.color}]{status.label}: {count}[/{status.color}]"
            )
    console.print("  ".join(summary_parts))


def _output_json(lock: FontopsLock, results: List[JudgmentResult]) -> None:
    """JSON 形式でレポートを出力。"""
    counts = Counter(r.status for r in results)
    output = {
        "fontops_version": lock.fontops_version,
        "results": [
            {
                "family": r.font.family,
                "source": r.font.source,
                "status": r.status.value,
                "action": r.action_message,
                "styles": [s.name for s in r.font.styles],
            }
            for r in results
        ],
        "summary": {
            status.value: counts.get(status, 0)
            for status in FontStatus
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
