"""設定管理モジュール

font-syncの設定をJSON形式で管理します。
設定ファイルは ~/.fontsync/config.json に保存されます。
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """設定管理クラス

    Attributes:
        config_dir (Path): 設定ディレクトリのパス
        config_file (Path): 設定ファイルのパス
        config (Dict[str, Any]): 現在の設定
    """

    def __init__(self) -> None:
        """ConfigManagerの初期化"""
        self.config_dir = Path.home() / ".fontsync"
        self.config_file = self.config_dir / "config.json"
        self.config: Dict[str, Any] = {}

    def load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込む

        Returns:
            Dict[str, Any]: 設定の辞書

        Raises:
            FileNotFoundError: 設定ファイルが存在しない場合
        """
        if not self.config_file.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_file}")

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"設定ファイルの形式が不正です: {e}")

        return self.config

    def save_config(self) -> None:
        """現在の設定をファイルに保存する

        Raises:
            IOError: ファイルの書き込みに失敗した場合
        """
        # 設定ディレクトリが存在しない場合は作成
        self.config_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise IOError(f"設定ファイルの保存に失敗しました: {e}")

    def get_sync_folder(self) -> Optional[str]:
        """同期元フォルダのパスを取得

        Returns:
            Optional[str]: 同期元フォルダのパス、未設定の場合はNone
        """
        return self.config.get("sync_folder")

    def set_sync_folder(self, folder_path: str) -> None:
        """同期元フォルダのパスを設定

        Args:
            folder_path (str): 同期元フォルダのパス
        """
        # パスを展開（~/を実際のホームディレクトリに変換）
        expanded_path = os.path.expanduser(folder_path)
        self.config["sync_folder"] = expanded_path

    def get_installed_fonts(self) -> Dict[str, Dict[str, Any]]:
        """インストール済みフォントの情報を取得

        Returns:
            Dict[str, Dict[str, Any]]: フォント名をキーとした情報の辞書
        """
        return self.config.get("installed_fonts", {})

    def add_installed_font(self, font_name: str, font_hash: str) -> None:
        """インストール済みフォントを記録

        Args:
            font_name (str): フォントファイル名
            font_hash (str): フォントファイルのハッシュ値
        """
        if "installed_fonts" not in self.config:
            self.config["installed_fonts"] = {}

        self.config["installed_fonts"][font_name] = {
            "hash": font_hash,
            "installed_at": datetime.now().isoformat()
        }

    def remove_installed_font(self, font_name: str) -> None:
        """インストール済みフォントの記録を削除

        Args:
            font_name (str): フォントファイル名
        """
        if "installed_fonts" in self.config and font_name in self.config["installed_fonts"]:
            del self.config["installed_fonts"][font_name]

    def is_font_installed(self, font_name: str) -> bool:
        """フォントがインストール済みか確認

        Args:
            font_name (str): フォントファイル名

        Returns:
            bool: インストール済みの場合True
        """
        return font_name in self.get_installed_fonts()

    def get_font_hash(self, font_name: str) -> Optional[str]:
        """インストール済みフォントのハッシュ値を取得

        Args:
            font_name (str): フォントファイル名

        Returns:
            Optional[str]: ハッシュ値、未インストールの場合はNone
        """
        fonts = self.get_installed_fonts()
        if font_name in fonts:
            return fonts[font_name].get("hash")
        return None

    def initialize_config(self, sync_folder: str) -> None:
        """設定を初期化

        Args:
            sync_folder (str): 同期元フォルダのパス
        """
        self.config = {
            "sync_folder": os.path.expanduser(sync_folder),
            "installed_fonts": {},
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        }
        self.save_config()

    def config_exists(self) -> bool:
        """設定ファイルが存在するか確認

        Returns:
            bool: 存在する場合True
        """
        return self.config_file.exists()
