"""フォント管理コアモジュール

フォントファイルの検出、ハッシュ計算、インストール処理などを行います。
"""

import hashlib
import os
import shutil
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from .cache import FontCache
from .utils import (
    FileLockedError,
    FontValidationError,
    check_disk_space,
    get_safe_filename,
    is_cloud_storage_syncing,
    is_file_locked,
    retry_on_error,
    validate_font_file_advanced,
    wait_for_file_unlock,
)


class FontManager:
    """フォント管理クラス

    Attributes:
        font_extensions (Tuple[str, ...]): 対応するフォントファイルの拡張子
        font_install_dir (Path): フォントのインストール先ディレクトリ
        max_font_size_mb (int): 最大フォントサイズ（MB）
        chunk_size (int): ファイル読み込み時のチャンクサイズ
        use_cache (bool): キャッシュを使用するか
        cache (FontCache): フォントキャッシュ
    """

    def __init__(self, use_cache: bool = True) -> None:
        """FontManagerの初期化

        Args:
            use_cache: キャッシュを使用するか
        """
        self.font_extensions: Tuple[str, ...] = (".otf", ".ttf", ".OTF", ".TTF")
        self.font_install_dir = Path.home() / "Library" / "Fonts"
        self.max_font_size_mb = 200  # 最大200MBまで
        self.chunk_size = 8192  # 8KB
        self.use_cache = use_cache

        # キャッシュの初期化
        if self.use_cache:
            self.cache = FontCache()
        else:
            self.cache = None

    def scan_fonts(self, folder_path: str, yield_batch: bool = False):
        """指定フォルダ内のフォントファイルをスキャン

        Args:
            folder_path (str): スキャンするフォルダのパス
            yield_batch (bool): バッチごとにyieldするか

        Returns/Yields:
            yield_batch=False: List[Path] - フォントファイルのパスリスト
            yield_batch=True: Iterator[List[Path]] - バッチごとのフォントリスト

        Raises:
            FileNotFoundError: フォルダが存在しない場合
            NotADirectoryError: 指定されたパスがディレクトリではない場合
        """
        folder = Path(os.path.expanduser(folder_path))

        if not folder.exists():
            raise FileNotFoundError(f"フォルダが存在しません: {folder}")

        if not folder.is_dir():
            raise NotADirectoryError(f"指定されたパスはディレクトリではありません: {folder}")

        if yield_batch:
            # ジェネレータとして動作
            return self._scan_fonts_generator(folder)
        else:
            # リストとして返す
            return self._scan_fonts_all(folder)

    def _scan_fonts_generator(self, folder: Path):
        """フォントスキャンのジェネレータ版（内部使用）"""
        fonts = []
        batch_size = 100  # 100ファイルごとにバッチ処理

        # サブディレクトリも含めて再帰的に検索
        for ext in self.font_extensions:
            for font_path in folder.rglob(f"*{ext}"):
                # .DS_Storeなどの隠しファイルを除外
                if font_path.name.startswith("."):
                    continue

                # クラウドストレージの同期中ファイルを除外
                if is_cloud_storage_syncing(font_path):
                    continue

                fonts.append(font_path)

                # バッチ処理モードの場合
                if len(fonts) >= batch_size:
                    yield sorted(fonts)
                    fonts = []

        # 残りのフォントをyield
        if fonts:
            yield sorted(fonts)

    def _scan_fonts_all(self, folder: Path):
        """全フォントスキャン（内部使用）"""
        fonts = []

        # サブディレクトリも含めて再帰的に検索
        for ext in self.font_extensions:
            for font_path in folder.rglob(f"*{ext}"):
                # .DS_Storeなどの隠しファイルを除外
                if font_path.name.startswith("."):
                    continue

                # クラウドストレージの同期中ファイルを除外
                if is_cloud_storage_syncing(font_path):
                    continue

                fonts.append(font_path)

        return sorted(fonts)

    @retry_on_error(max_retries=3, delay=0.5)
    def calculate_hash(self, file_path: Path, use_cache: Optional[bool] = None) -> str:
        """ファイルのSHA256ハッシュを計算（リトライ機能付き）

        Args:
            file_path (Path): ハッシュを計算するファイルのパス
            use_cache (Optional[bool]): キャッシュを使用するか（Noneの場合はインスタンスの設定に従う）

        Returns:
            str: SHA256ハッシュ値（16進数文字列）

        Raises:
            FileNotFoundError: ファイルが存在しない場合
            FileLockedError: ファイルがロックされている場合
            IOError: ファイルの読み込みに失敗した場合
        """
        if not file_path.exists():
            raise FileNotFoundError(f"ファイルが存在しません: {file_path}")

        # キャッシュ使用の判定
        use_cache = self.use_cache if use_cache is None else use_cache

        # キャッシュから取得を試みる
        if use_cache and self.cache:
            cached_hash = self.cache.get_hash(file_path)
            if cached_hash:
                return cached_hash

        # ファイルロックチェック
        if is_file_locked(file_path):
            # 少し待機してから再度チェック
            if not wait_for_file_unlock(file_path, timeout=10):
                raise FileLockedError(
                    f"ファイルがロックされています: {file_path}",
                    hint="他のアプリケーションがファイルを使用している可能性があります"
                )

        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                # 大きなファイルにも対応するため、チャンクごとに読み込む
                for chunk in iter(lambda: f.read(self.chunk_size), b""):
                    sha256_hash.update(chunk)
            hash_value = sha256_hash.hexdigest()

            # キャッシュに保存
            if use_cache and self.cache:
                self.cache.set_hash(file_path, hash_value)

            return hash_value
        except IOError as e:
            raise IOError(f"ファイルの読み込みに失敗しました: {e}")

    def copy_font(self, src: Path, dst: Optional[Path] = None, validate: bool = True) -> Path:
        """フォントファイルをコピー（検証機能付き）

        Args:
            src (Path): コピー元のフォントファイルパス
            dst (Optional[Path]): コピー先のパス。Noneの場合はデフォルトのインストール先
            validate (bool): コピー前に詳細な検証を行うか

        Returns:
            Path: コピー先のファイルパス

        Raises:
            FileNotFoundError: コピー元ファイルが存在しない場合
            PermissionError: コピー先への書き込み権限がない場合
            FontValidationError: フォントファイルが無効な場合
        """
        if not src.exists():
            raise FileNotFoundError(f"コピー元ファイルが存在しません: {src}")

        # 詳細な検証
        if validate:
            validation_result = validate_font_file_advanced(src)

            # 警告がある場合は表示（エラーではない）
            if validation_result["warnings"]:
                for warning in validation_result["warnings"]:
                    # ここでは警告をログに記録するだけ
                    pass

            # ファイルがロックされている場合は待機
            if validation_result["is_locked"]:
                if not wait_for_file_unlock(src, timeout=30):
                    raise FileLockedError(
                        f"ファイルがロックされています: {src}",
                        hint="ファイルを使用しているアプリケーションを閉じてください"
                    )

            # 検証モードでのみファイル名の安全性チェック
            safe_filename = get_safe_filename(src.name)
        else:
            # 検証なしの場合は元のファイル名を使用
            safe_filename = src.name

        if dst is None:
            dst = self.font_install_dir / safe_filename

        # ディスク容量チェック
        file_size_mb = src.stat().st_size / (1024 * 1024)
        disk_info = check_disk_space(dst.parent, file_size_mb * 1.1)  # 10%の余裕を持つ

        if not disk_info["has_enough_space"]:
            raise IOError(
                f"ディスク容量が不足しています。必要: {file_size_mb:.1f}MB, 空き: {disk_info['free_mb']:.1f}MB"
            )

        # インストール先ディレクトリが存在しない場合は作成
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            # メタデータも保持してコピー
            shutil.copy2(src, dst)
            return dst
        except PermissionError as e:
            raise PermissionError(
                f"フォントのコピーに失敗しました（権限エラー）: {e}",
                hint="管理者権限で実行するか、インストール先の権限を確認してください"
            )
        except Exception as e:
            raise IOError(f"フォントのコピーに失敗しました: {e}")

    def is_font_installed(self, font_name: str) -> bool:
        """フォントがシステムにインストールされているか確認

        Args:
            font_name (str): フォントファイル名

        Returns:
            bool: インストールされている場合True
        """
        # 安全なファイル名に変換して確認
        safe_name = get_safe_filename(font_name)
        font_path = self.font_install_dir / safe_name

        # 元の名前でも確認（互換性のため）
        original_path = self.font_install_dir / font_name

        return font_path.exists() or original_path.exists()

    def get_installed_font_path(self, font_name: str) -> Optional[Path]:
        """インストール済みフォントのパスを取得

        Args:
            font_name (str): フォントファイル名

        Returns:
            Optional[Path]: フォントのパス。インストールされていない場合はNone
        """
        # 安全なファイル名で確認
        safe_name = get_safe_filename(font_name)
        font_path = self.font_install_dir / safe_name

        if font_path.exists():
            return font_path

        # 元の名前でも確認（互換性のため）
        original_path = self.font_install_dir / font_name
        if original_path.exists():
            return original_path

        return None

    @retry_on_error(max_retries=2, delay=1.0)
    def remove_font(self, font_name: str) -> bool:
        """フォントを削除（リトライ機能付き）

        Args:
            font_name (str): 削除するフォントファイル名

        Returns:
            bool: 削除に成功した場合True
        """
        font_path = self.get_installed_font_path(font_name)

        if not font_path:
            return False

        # ファイルロックチェック
        if is_file_locked(font_path):
            if not wait_for_file_unlock(font_path, timeout=10):
                raise FileLockedError(
                    f"フォントファイルが使用中です: {font_name}",
                    hint="フォントを使用しているアプリケーションを閉じてください"
                )

        try:
            font_path.unlink()
            return True
        except PermissionError:
            raise PermissionError(
                f"フォントの削除に失敗しました（権限エラー）: {font_name}",
                hint="管理者権限で実行するか、ファイルの権限を確認してください"
            )
        except Exception as e:
            raise IOError(f"フォントの削除に失敗しました: {e}")

    def get_font_info(self, font_path: Path) -> Dict[str, any]:
        """フォントファイルの情報を取得（エラーハンドリング強化）

        Args:
            font_path (Path): フォントファイルのパス

        Returns:
            Dict[str, any]: フォントの情報（名前、サイズ、更新日時など）
        """
        if not font_path.exists():
            # エラー情報を含む辞書を返す
            return {
                "name": font_path.name,
                "path": str(font_path),
                "size": 0,
                "size_mb": 0,
                "modified": 0,
                "hash": None,
                "error": f"フォントファイルが存在しません: {font_path}"
            }

        try:
            stat = font_path.stat()

            # 基本情報
            info = {
                "name": font_path.name,
                "path": str(font_path),
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified": stat.st_mtime,
                "hash": None,  # 必要に応じて後で計算
                "is_locked": is_file_locked(font_path),
                "is_syncing": is_cloud_storage_syncing(font_path)
            }

            # サイズ警告
            if info["size_mb"] > self.max_font_size_mb:
                info["warning"] = f"ファイルサイズが大きすぎます ({info['size_mb']}MB)"

            return info

        except Exception as e:
            # 最低限の情報を返す
            return {
                "name": font_path.name,
                "path": str(font_path),
                "size": 0,
                "size_mb": 0,
                "modified": 0,
                "hash": None,
                "error": str(e)
            }

    def validate_font_file(self, font_path: Path) -> bool:
        """フォントファイルの妥当性をチェック（簡易版）

        Args:
            font_path (Path): チェックするフォントファイルのパス

        Returns:
            bool: 妥当な場合True
        """
        try:
            result = validate_font_file_advanced(font_path)
            return result["valid"] and not result.get("error")
        except FontValidationError:
            return False
        except Exception:
            # エラーが発生しても基本的なチェックは行う
            pass

        # 基本的なチェック
        if not font_path.exists():
            return False

        if not font_path.is_file():
            return False

        # 拡張子チェック（大文字小文字を考慮）
        if font_path.suffix.lower() not in [ext.lower() for ext in self.font_extensions]:
            return False

        # ファイルサイズチェック（0バイトでないこと）
        if font_path.stat().st_size == 0:
            return False

        return True

    def get_fonts_batch_info(self, font_paths: List[Path]) -> Iterator[Dict[str, any]]:
        """複数のフォント情報をバッチで取得（大量フォント対応）

        Args:
            font_paths: フォントファイルパスのリスト

        Yields:
            Dict[str, any]: 各フォントの情報
        """
        for font_path in font_paths:
            try:
                yield self.get_font_info(font_path)
            except Exception as e:
                # エラーが発生してもスキップして続行
                yield {
                    "name": font_path.name,
                    "path": str(font_path),
                    "error": str(e)
                }
