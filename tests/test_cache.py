"""キャッシュ機能のテスト"""

import json
import time
from pathlib import Path

import pytest

from src.cache import FontCache


class TestFontCache:
    """FontCacheクラスのテスト"""

    @pytest.fixture
    def cache(self, temp_dir: Path):
        """テスト用のキャッシュインスタンスを作成"""
        cache_dir = temp_dir / "cache"
        return FontCache(cache_dir=cache_dir, ttl_hours=1)

    def test_init(self, temp_dir: Path):
        """初期化のテスト"""
        cache_dir = temp_dir / "test_cache"
        cache = FontCache(cache_dir=cache_dir, ttl_hours=24)

        assert cache.cache_dir == cache_dir
        assert cache.ttl_hours == 24
        assert cache_dir.exists()
        assert cache.hash_cache_file == cache_dir / "hash_cache.json"
        assert cache.info_cache_file == cache_dir / "info_cache.json"

    def test_default_cache_dir(self):
        """デフォルトキャッシュディレクトリのテスト"""
        cache = FontCache()
        expected_dir = Path.home() / ".fontsync" / "cache"
        assert cache.cache_dir == expected_dir

    def test_cache_key_generation(self, cache: FontCache, temp_dir: Path):
        """キャッシュキー生成のテスト"""
        # 存在するファイル
        test_file = temp_dir / "test.otf"
        test_file.write_bytes(b"test data")

        key1 = cache._get_cache_key(test_file)
        assert isinstance(key1, str)
        assert len(key1) == 32  # MD5ハッシュの長さ

        # 同じファイルは同じキー
        key2 = cache._get_cache_key(test_file)
        assert key1 == key2

        # ファイルを変更するとキーが変わる
        test_file.write_bytes(b"modified data")
        key3 = cache._get_cache_key(test_file)
        assert key1 != key3

        # 存在しないファイル
        non_existent = temp_dir / "non_existent.otf"
        key4 = cache._get_cache_key(non_existent)
        assert isinstance(key4, str)

    def test_hash_cache(self, cache: FontCache, temp_dir: Path):
        """ハッシュキャッシュのテスト"""
        test_file = temp_dir / "font.otf"
        test_file.write_bytes(b"font data")

        # キャッシュが空の状態
        assert cache.get_hash(test_file) is None

        # ハッシュを設定
        test_hash = "abcdef1234567890"
        cache.set_hash(test_file, test_hash)

        # キャッシュから取得
        assert cache.get_hash(test_file) == test_hash

        # メモリキャッシュとファイルキャッシュの両方を確認
        cache_key = cache._get_cache_key(test_file)
        assert cache_key in cache._memory_cache

        # ファイルキャッシュも確認
        with open(cache.hash_cache_file, 'r') as f:
            file_cache = json.load(f)
            assert cache_key in file_cache

    def test_info_cache(self, cache: FontCache, temp_dir: Path):
        """情報キャッシュのテスト"""
        test_file = temp_dir / "font.otf"
        test_file.write_bytes(b"font data")

        # キャッシュが空の状態
        assert cache.get_info(test_file) is None

        # 情報を設定
        test_info = {
            "name": "TestFont.otf",
            "size_mb": 1.5,
            "modified": time.time()
        }
        cache.set_info(test_file, test_info)

        # キャッシュから取得
        cached_info = cache.get_info(test_file)
        assert cached_info == test_info

    def test_cache_expiry(self, temp_dir: Path):
        """キャッシュの有効期限テスト"""
        # TTLを0.001時間（3.6秒）に設定
        cache = FontCache(cache_dir=temp_dir / "cache", ttl_hours=0.001)

        test_file = temp_dir / "font.otf"
        test_file.write_bytes(b"font data")

        # ハッシュを設定
        cache.set_hash(test_file, "test_hash")
        assert cache.get_hash(test_file) == "test_hash"

        # 4秒待機
        time.sleep(4)

        # キャッシュが期限切れ
        assert cache.get_hash(test_file) is None

    def test_cache_clear(self, cache: FontCache, temp_dir: Path):
        """キャッシュクリアのテスト"""
        test_file = temp_dir / "font.otf"
        test_file.write_bytes(b"font data")

        # データを設定
        cache.set_hash(test_file, "test_hash")
        cache.set_info(test_file, {"name": "test"})

        # クリア前の確認
        assert cache.get_hash(test_file) == "test_hash"
        assert cache.get_info(test_file) == {"name": "test"}
        assert len(cache._memory_cache) > 0

        # クリア
        cache.clear()

        # クリア後の確認
        assert cache.get_hash(test_file) is None
        assert cache.get_info(test_file) is None
        assert len(cache._memory_cache) == 0
        assert not cache.hash_cache_file.exists()
        assert not cache.info_cache_file.exists()

    def test_cleanup_expired(self, temp_dir: Path):
        """期限切れエントリのクリーンアップテスト"""
        cache = FontCache(cache_dir=temp_dir / "cache", ttl_hours=24)

        # 複数のファイルを作成
        files = []
        for i in range(5):
            file = temp_dir / f"font{i}.otf"
            file.write_bytes(b"data")
            files.append(file)
            cache.set_hash(file, f"hash{i}")

        # 一部のエントリを期限切れにする（直接タイムスタンプを変更）
        hash_cache = cache._load_cache_file(cache.hash_cache_file)
        expired_keys = []
        for i, (key, entry) in enumerate(list(hash_cache.items())):
            if i < 2:  # 最初の2つを期限切れに
                entry['timestamp'] = time.time() - (25 * 3600)  # 25時間前
                expired_keys.append(key)
        cache._save_cache_file(cache.hash_cache_file, hash_cache)

        # メモリキャッシュもクリア（再読み込みを強制）
        cache._memory_cache.clear()

        # クリーンアップ実行
        hash_removed, info_removed = cache.cleanup_expired()

        assert hash_removed == 2
        assert info_removed == 0

        # 残りのエントリを確認
        for i in range(2, 5):
            assert cache.get_hash(files[i]) == f"hash{i}"
        for i in range(0, 2):
            assert cache.get_hash(files[i]) is None

    def test_cache_stats(self, cache: FontCache, temp_dir: Path):
        """キャッシュ統計情報のテスト"""
        # 初期状態
        stats = cache.get_stats()
        assert stats['hash_entries'] == 0
        assert stats['info_entries'] == 0
        assert stats['memory_entries'] == 0
        assert stats['ttl_hours'] == 1

        # データを追加
        for i in range(3):
            file = temp_dir / f"font{i}.otf"
            file.write_bytes(b"data")
            cache.set_hash(file, f"hash{i}")
            if i < 2:
                cache.set_info(file, {"index": i})

        # 統計情報を更新
        stats = cache.get_stats()
        assert stats['hash_entries'] == 3
        assert stats['info_entries'] == 2
        assert stats['memory_entries'] == 3  # ハッシュのみメモリキャッシュに
        assert stats['hash_cache_size'] > 0
        assert stats['info_cache_size'] > 0

    def test_invalid_cache_file(self, cache: FontCache):
        """無効なキャッシュファイルの処理テスト"""
        # 無効なJSONを書き込む
        cache.hash_cache_file.write_text("invalid json{")

        # エラーが発生せず、空のキャッシュが返される
        result = cache._load_cache_file(cache.hash_cache_file)
        assert result == {}

    def test_concurrent_access(self, cache: FontCache, temp_dir: Path):
        """並行アクセスのテスト（簡易版）"""
        test_file = temp_dir / "font.otf"
        test_file.write_bytes(b"font data")

        # 複数回の読み書きを行う
        for i in range(10):
            cache.set_hash(test_file, f"hash_{i}")
            assert cache.get_hash(test_file) == f"hash_{i}"

        # 最終的な値を確認
        assert cache.get_hash(test_file) == "hash_9"
