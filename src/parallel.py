"""並列処理ユーティリティ

フォント処理の並列化をサポートする関数を提供します。
"""

import concurrent.futures
import multiprocessing
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ParallelConfig:
    """並列処理の設定"""
    max_workers: Optional[int] = None
    chunk_size: int = 50
    timeout: Optional[float] = None

    def __post_init__(self):
        """初期化後の処理"""
        if self.max_workers is None:
            # CPUコア数の半分を使用（最小2、最大8）
            cpu_count = multiprocessing.cpu_count()
            self.max_workers = min(max(cpu_count // 2, 2), 8)


class ParallelProcessor:
    """並列処理を管理するクラス"""

    def __init__(self, config: Optional[ParallelConfig] = None):
        """ParallelProcessorの初期化

        Args:
            config: 並列処理の設定
        """
        self.config = config or ParallelConfig()

    def process_batch(
        self,
        items: List[Any],
        process_func: Callable[[Any], Any],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        error_handler: Optional[Callable[[Any, Exception], Any]] = None
    ) -> List[Tuple[bool, Any]]:
        """アイテムをバッチで並列処理

        Args:
            items: 処理対象のアイテムリスト
            process_func: 各アイテムを処理する関数
            progress_callback: 進捗コールバック (completed, total)
            error_handler: エラーハンドラー (item, exception) -> result

        Returns:
            List[Tuple[bool, Any]]: (成功フラグ, 結果)のリスト
        """
        results = []
        completed = 0
        total = len(items)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.max_workers
        ) as executor:
            # バッチごとに処理
            for i in range(0, total, self.config.chunk_size):
                batch = items[i:i + self.config.chunk_size]

                # 並列でタスクを送信
                future_to_item = {
                    executor.submit(process_func, item): item
                    for item in batch
                }

                # 結果を収集
                for future in concurrent.futures.as_completed(
                    future_to_item,
                    timeout=self.config.timeout
                ):
                    item = future_to_item[future]
                    try:
                        result = future.result()
                        results.append((True, result))
                    except Exception as e:
                        if error_handler:
                            fallback_result = error_handler(item, e)
                            results.append((False, fallback_result))
                        else:
                            results.append((False, {"error": str(e), "item": item}))

                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)

        return results

    def calculate_hashes_parallel(
        self,
        font_paths: List[Path],
        hash_func: Callable[[Path], str],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[Path, Optional[str]]:
        """複数ファイルのハッシュを並列計算

        Args:
            font_paths: フォントファイルパスのリスト
            hash_func: ハッシュ計算関数
            progress_callback: 進捗コールバック

        Returns:
            Dict[Path, Optional[str]]: パスとハッシュ値の辞書
        """
        def error_handler(path: Path, e: Exception) -> Dict[str, Any]:
            return {"path": path, "hash": None, "error": str(e)}

        results = self.process_batch(
            font_paths,
            lambda path: {"path": path, "hash": hash_func(path)},
            progress_callback,
            error_handler
        )

        # 結果を辞書に変換
        hash_dict = {}
        for success, result in results:
            if isinstance(result, dict) and "path" in result:
                hash_dict[result["path"]] = result.get("hash")

        return hash_dict

    def copy_fonts_parallel(
        self,
        copy_tasks: List[Tuple[Path, Path]],
        copy_func: Callable[[Path, Path], Path],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Tuple[bool, Dict[str, Any]]]:
        """複数のフォントを並列でコピー

        Args:
            copy_tasks: (src, dst)のタプルリスト
            copy_func: コピー関数
            progress_callback: 進捗コールバック

        Returns:
            List[Tuple[bool, Dict]]: 各タスクの結果
        """
        def process_copy(task: Tuple[Path, Path]) -> Dict[str, Any]:
            src, dst = task
            result_path = copy_func(src, dst)
            return {
                "src": src,
                "dst": result_path,
                "success": True
            }

        def error_handler(task: Tuple[Path, Path], e: Exception) -> Dict[str, Any]:
            src, dst = task
            return {
                "src": src,
                "dst": dst,
                "success": False,
                "error": str(e)
            }

        results = self.process_batch(
            copy_tasks,
            process_copy,
            progress_callback,
            error_handler
        )

        return results


def measure_performance(func: Callable[[], Any]) -> Tuple[Any, float]:
    """関数の実行時間を計測

    Args:
        func: 計測対象の関数

    Returns:
        Tuple[Any, float]: (結果, 実行時間)
    """
    start_time = time.time()
    result = func()
    elapsed_time = time.time() - start_time
    return result, elapsed_time
