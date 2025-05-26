"""並列処理モジュールのテスト"""

import pytest
from pathlib import Path
import time
import tempfile
from unittest.mock import Mock, patch

from src.parallel import ParallelProcessor, ParallelConfig, measure_performance


class TestParallelConfig:
    """ParallelConfigのテスト"""
    
    def test_default_config(self):
        """デフォルト設定のテスト"""
        config = ParallelConfig()
        
        assert config.chunk_size == 50
        assert config.timeout is None
        assert config.max_workers is not None
        assert 2 <= config.max_workers <= 8
    
    def test_custom_config(self):
        """カスタム設定のテスト"""
        config = ParallelConfig(max_workers=4, chunk_size=100, timeout=30.0)
        
        assert config.max_workers == 4
        assert config.chunk_size == 100
        assert config.timeout == 30.0


class TestParallelProcessor:
    """ParallelProcessorのテスト"""
    
    def test_process_batch_success(self):
        """バッチ処理の成功テスト"""
        processor = ParallelProcessor()
        
        # テスト用の処理関数
        def process_item(item):
            return item * 2
        
        items = list(range(10))
        results = processor.process_batch(items, process_item)
        
        assert len(results) == 10
        # 並列処理のため順序は保証されないが、すべて成功している
        success_count = sum(1 for success, _ in results if success)
        assert success_count == 10
        
        # 結果の値を確認
        result_values = sorted([result for success, result in results if success])
        expected_values = [i * 2 for i in range(10)]
        assert result_values == expected_values
    
    def test_process_batch_with_errors(self):
        """エラーを含むバッチ処理のテスト"""
        processor = ParallelProcessor()
        
        # エラーを発生させる処理関数
        def process_item(item):
            if item == 5:
                raise ValueError("Test error")
            return item * 2
        
        items = list(range(10))
        results = processor.process_batch(items, process_item)
        
        assert len(results) == 10
        success_count = sum(1 for success, _ in results if success)
        error_count = sum(1 for success, _ in results if not success)
        
        assert success_count == 9
        assert error_count == 1
    
    def test_process_batch_with_progress(self):
        """進捗コールバック付きバッチ処理のテスト"""
        processor = ParallelProcessor(ParallelConfig(max_workers=2))
        
        progress_calls = []
        
        def progress_callback(completed, total):
            progress_calls.append((completed, total))
        
        def process_item(item):
            time.sleep(0.01)  # 少し時間のかかる処理をシミュレート
            return item
        
        items = list(range(5))
        processor.process_batch(items, process_item, progress_callback)
        
        # 進捗が報告されていることを確認
        assert len(progress_calls) == 5
        assert progress_calls[-1] == (5, 5)
    
    def test_calculate_hashes_parallel(self, temp_dir: Path):
        """並列ハッシュ計算のテスト"""
        processor = ParallelProcessor()
        
        # テスト用ファイルを作成
        font_paths = []
        for i in range(5):
            font_path = temp_dir / f"font{i}.otf"
            font_path.write_bytes(b"OTTO" + bytes([i]) * 100)
            font_paths.append(font_path)
        
        # 簡易ハッシュ関数（テスト用）
        def mock_hash_func(path: Path) -> str:
            return f"hash_{path.name}"
        
        hash_results = processor.calculate_hashes_parallel(font_paths, mock_hash_func)
        
        assert len(hash_results) == 5
        for font_path in font_paths:
            assert font_path in hash_results
            assert hash_results[font_path] == f"hash_{font_path.name}"
    
    def test_calculate_hashes_with_error(self, temp_dir: Path):
        """エラーを含むハッシュ計算のテスト"""
        processor = ParallelProcessor()
        
        # 存在しないファイルを含む
        font_paths = [
            temp_dir / "exists.otf",
            temp_dir / "not_exists.otf"
        ]
        font_paths[0].write_bytes(b"OTTO")
        
        def hash_func(path: Path) -> str:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            return "hash"
        
        hash_results = processor.calculate_hashes_parallel(font_paths, hash_func)
        
        assert len(hash_results) == 2
        assert hash_results[font_paths[0]] == "hash"
        assert hash_results[font_paths[1]] is None
    
    def test_copy_fonts_parallel(self, temp_dir: Path):
        """並列フォントコピーのテスト"""
        processor = ParallelProcessor()
        
        src_dir = temp_dir / "src"
        dst_dir = temp_dir / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        
        # コピータスクを作成
        copy_tasks = []
        for i in range(5):
            src = src_dir / f"font{i}.otf"
            dst = dst_dir / f"font{i}.otf"
            src.write_bytes(b"font data")
            copy_tasks.append((src, dst))
        
        # 簡易コピー関数
        def copy_func(src: Path, dst: Path) -> Path:
            dst.write_bytes(src.read_bytes())
            return dst
        
        results = processor.copy_fonts_parallel(copy_tasks, copy_func)
        
        assert len(results) == 5
        success_count = sum(1 for success, _ in results if success)
        assert success_count == 5
        
        # コピーされたファイルを確認
        for i in range(5):
            assert (dst_dir / f"font{i}.otf").exists()


class TestPerformanceMeasurement:
    """パフォーマンス測定のテスト"""
    
    def test_measure_performance(self):
        """実行時間計測のテスト"""
        def test_func():
            time.sleep(0.1)
            return "result"
        
        result, elapsed = measure_performance(test_func)
        
        assert result == "result"
        assert 0.09 < elapsed < 0.2  # 少し余裕を持たせる
    
    def test_parallel_vs_sequential_performance(self, temp_dir: Path):
        """並列処理と逐次処理のパフォーマンス比較"""
        # テスト用のファイルを作成
        files = []
        for i in range(20):
            file_path = temp_dir / f"file{i}.txt"
            file_path.write_bytes(b"x" * 1000)
            files.append(file_path)
        
        # 処理関数（少し重い処理）
        def process_file(path: Path) -> int:
            data = path.read_bytes()
            # 簡単な処理をシミュレート
            return sum(data)
        
        # 逐次処理
        def sequential_process():
            results = []
            for file in files:
                results.append(process_file(file))
            return results
        
        # 並列処理
        def parallel_process():
            processor = ParallelProcessor(ParallelConfig(max_workers=4))
            results = processor.process_batch(files, process_file)
            return [r for _, r in results]
        
        seq_result, seq_time = measure_performance(sequential_process)
        par_result, par_time = measure_performance(parallel_process)
        
        # 結果が同じことを確認（順序は異なる可能性がある）
        assert sorted(seq_result) == sorted(par_result)
        
        # 並列処理の方が速いことを期待（ただし、小さなタスクでは必ずしもそうならない）
        # このテストではパフォーマンス向上を厳密には要求しない
        print(f"Sequential: {seq_time:.3f}s, Parallel: {par_time:.3f}s") 