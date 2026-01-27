"""キャッシュ機能

フォント情報とハッシュ値のキャッシュを管理します。
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class FontCache:
    """フォント情報のキャッシュを管理するクラス"""

    def __init__(self, cache_dir: Optional[Path] = None, ttl_hours: int = 24):
        """FontCacheの初期化

        Args:
            cache_dir: キャッシュディレクトリ（Noneの場合はデフォルト）
            ttl_hours: キャッシュの有効時間（時間単位）
        """
        if cache_dir is None:
            self.cache_dir = Path.home() / ".fontsync" / "cache"
        else:
            self.cache_dir = cache_dir

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hash_cache_file = self.cache_dir / "hash_cache.json"
        self.info_cache_file = self.cache_dir / "info_cache.json"
        self.ttl_hours = ttl_hours

        # メモリキャッシュ
        self._memory_cache: Dict[str, Any] = {}

    def _get_cache_key(self, file_path: Path) -> str:
        """ファイルパスからキャッシュキーを生成

        Args:
            file_path: ファイルパス

        Returns:
            キャッシュキー
        """
        # パスとファイルサイズ、更新時刻を組み合わせてキーを作成
        try:
            stat = file_path.stat()
            key_data = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
            return hashlib.md5(key_data.encode()).hexdigest()
        except Exception:
            # ファイルが存在しない場合などはパスのみでキーを作成
            return hashlib.md5(str(file_path).encode()).hexdigest()

    def _is_cache_valid(self, timestamp: float) -> bool:
        """キャッシュが有効期限内かチェック

        Args:
            timestamp: キャッシュのタイムスタンプ

        Returns:
            有効な場合True
        """
        if self.ttl_hours <= 0:
            return True  # TTLが0以下の場合は常に有効

        cache_time = datetime.fromtimestamp(timestamp)
        expiry_time = cache_time + timedelta(hours=self.ttl_hours)
        return datetime.now() < expiry_time

    def _load_cache_file(self, cache_file: Path) -> Dict[str, Any]:
        """キャッシュファイルを読み込む

        Args:
            cache_file: キャッシュファイルパス

        Returns:
            キャッシュデータ
        """
        if not cache_file.exists():
            return {}

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            # 読み込みエラーの場合は空のキャッシュを返す
            return {}

    def _save_cache_file(self, cache_file: Path, data: Dict[str, Any]) -> None:
        """キャッシュファイルに保存

        Args:
            cache_file: キャッシュファイルパス
            data: 保存するデータ
        """
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            # 保存エラーは無視（キャッシュなので）
            pass

    def get_hash(self, file_path: Path) -> Optional[str]:
        """キャッシュからハッシュ値を取得

        Args:
            file_path: ファイルパス

        Returns:
            ハッシュ値（キャッシュにない場合はNone）
        """
        cache_key = self._get_cache_key(file_path)

        # メモリキャッシュを確認
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if self._is_cache_valid(entry['timestamp']):
                return entry.get('hash')

        # ファイルキャッシュを確認
        hash_cache = self._load_cache_file(self.hash_cache_file)
        if cache_key in hash_cache:
            entry = hash_cache[cache_key]
            if self._is_cache_valid(entry['timestamp']):
                # メモリキャッシュに追加
                self._memory_cache[cache_key] = entry
                return entry.get('hash')

        return None

    def set_hash(self, file_path: Path, hash_value: str) -> None:
        """ハッシュ値をキャッシュに保存

        Args:
            file_path: ファイルパス
            hash_value: ハッシュ値
        """
        cache_key = self._get_cache_key(file_path)
        entry = {
            'hash': hash_value,
            'timestamp': time.time(),
            'path': str(file_path)
        }

        # メモリキャッシュに保存
        self._memory_cache[cache_key] = entry

        # ファイルキャッシュに保存
        hash_cache = self._load_cache_file(self.hash_cache_file)
        hash_cache[cache_key] = entry
        self._save_cache_file(self.hash_cache_file, hash_cache)

    def get_info(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """キャッシュからフォント情報を取得

        Args:
            file_path: ファイルパス

        Returns:
            フォント情報（キャッシュにない場合はNone）
        """
        cache_key = self._get_cache_key(file_path)

        # ファイルキャッシュを確認
        info_cache = self._load_cache_file(self.info_cache_file)
        if cache_key in info_cache:
            entry = info_cache[cache_key]
            if self._is_cache_valid(entry['timestamp']):
                return entry.get('info')

        return None

    def set_info(self, file_path: Path, info: Dict[str, Any]) -> None:
        """フォント情報をキャッシュに保存

        Args:
            file_path: ファイルパス
            info: フォント情報
        """
        cache_key = self._get_cache_key(file_path)
        entry = {
            'info': info,
            'timestamp': time.time(),
            'path': str(file_path)
        }

        # ファイルキャッシュに保存
        info_cache = self._load_cache_file(self.info_cache_file)
        info_cache[cache_key] = entry
        self._save_cache_file(self.info_cache_file, info_cache)

    def clear(self) -> None:
        """すべてのキャッシュをクリア"""
        self._memory_cache.clear()

        if self.hash_cache_file.exists():
            self.hash_cache_file.unlink()

        if self.info_cache_file.exists():
            self.info_cache_file.unlink()

    def cleanup_expired(self) -> Tuple[int, int]:
        """期限切れのキャッシュエントリを削除

        Returns:
            (削除されたハッシュエントリ数, 削除された情報エントリ数)
        """
        hash_removed = 0
        info_removed = 0

        # ハッシュキャッシュのクリーンアップ
        hash_cache = self._load_cache_file(self.hash_cache_file)
        valid_hash_cache = {}
        for key, entry in hash_cache.items():
            if self._is_cache_valid(entry.get('timestamp', 0)):
                valid_hash_cache[key] = entry
            else:
                hash_removed += 1

        if hash_removed > 0:
            self._save_cache_file(self.hash_cache_file, valid_hash_cache)

        # 情報キャッシュのクリーンアップ
        info_cache = self._load_cache_file(self.info_cache_file)
        valid_info_cache = {}
        for key, entry in info_cache.items():
            if self._is_cache_valid(entry.get('timestamp', 0)):
                valid_info_cache[key] = entry
            else:
                info_removed += 1

        if info_removed > 0:
            self._save_cache_file(self.info_cache_file, valid_info_cache)

        # メモリキャッシュもクリーンアップ
        valid_memory_cache = {}
        for key, entry in self._memory_cache.items():
            if self._is_cache_valid(entry.get('timestamp', 0)):
                valid_memory_cache[key] = entry
        self._memory_cache = valid_memory_cache

        return hash_removed, info_removed

    def get_stats(self) -> Dict[str, Any]:
        """キャッシュの統計情報を取得

        Returns:
            統計情報の辞書
        """
        hash_cache = self._load_cache_file(self.hash_cache_file)
        info_cache = self._load_cache_file(self.info_cache_file)

        return {
            'hash_entries': len(hash_cache),
            'info_entries': len(info_cache),
            'memory_entries': len(self._memory_cache),
            'cache_dir': str(self.cache_dir),
            'ttl_hours': self.ttl_hours,
            'hash_cache_size': self.hash_cache_file.stat().st_size if self.hash_cache_file.exists() else 0,
            'info_cache_size': self.info_cache_file.stat().st_size if self.info_cache_file.exists() else 0
        }
