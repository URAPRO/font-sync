"""fontops.lock の状態確認コマンド"""

import json
from collections import Counter
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from ..font_inventory import enumerate_installed_fonts
from ..font_status import FontStatus, JudgmentResult, judge_all
from ..lockfile import FontopsLock, load_lock
from ..main import handle_errors
from ..resolver import ResolveResult, resolve_fonts

console = Console()

_LOCK_FILE = Path("fontops.lock")
_DEFAULT_INSTALL_DIR = Path.home() / "Library" / "Fonts"


# ---------------------------------------------------------------------------
# 内部実装（@handle_errors 適用）
# ---------------------------------------------------------------------------


@handle_errors
def apply_command(resolve: bool, dry_run: bool, json_output: bool) -> None:
    """apply コマンドの実装。

    fontops.lock を読み込み、インストール済みフォントと照合して状態を表示する。
    --resolve 時は未インストールフォントの自動解決を試みる。
    --dry-run は --resolve と組み合わせて、DL を行わず判定のみ表示する。
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

    # resolve=True かつ dry_run=False の場合のみ実際に resolve_fonts() を呼び出す
    resolve_results: Optional[List[ResolveResult]] = None
    if resolve:
        if dry_run:
            resolve_results = []  # dry-run: 空リスト（DL は行わない）
        else:
            resolve_results = resolve_fonts(results, _DEFAULT_INSTALL_DIR)

    if json_output:
        _output_json(lock, results, resolve_results=resolve_results, is_dry_run=resolve and dry_run)
        return

    _render_report(results)

    if resolve:
        if dry_run:
            console.print("[dim]dry-run: 実際のダウンロードは行いません[/dim]")
        else:
            assert resolve_results is not None
            _render_resolve_report(resolve_results)


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


def _render_resolve_report(results: List[ResolveResult]) -> None:
    """Rich Table でフォント解決レポートを表示。

    success=True → green、success=False かつ error あり → red、それ以外 → yellow
    """
    table = Table(title="フォント解決結果")
    table.add_column("Font Family", style="cyan")
    table.add_column("Action")
    table.add_column("Message")

    for r in results:
        if r.success:
            action = "[green]downloaded[/green]"
        elif r.error:
            action = "[red]failed[/red]"
        else:
            action = "[yellow]message[/yellow]"
        table.add_row(r.font_family, action, r.message)

    console.print(table)


def _output_json(
    lock: FontopsLock,
    results: List[JudgmentResult],
    resolve_results: Optional[List[ResolveResult]] = None,
    is_dry_run: bool = False,
) -> None:
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

    if resolve_results is not None:
        output["resolve_results"] = [
            {
                "family": r.font_family,
                "action": "downloaded" if r.success else ("failed" if r.error else "message"),
                "message": r.message,
                "error": r.error,
            }
            for r in resolve_results
        ]
        if is_dry_run:
            output["dry_run"] = True

    print(json.dumps(output, ensure_ascii=False, indent=2))
