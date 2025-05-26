"""pytest設定と共通フィクスチャ"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator
import json


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """一時ディレクトリを作成するフィクスチャ
    
    Yields:
        Path: 一時ディレクトリのパス
    """
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_config_dir(temp_dir: Path) -> Path:
    """モックの設定ディレクトリを作成
    
    Args:
        temp_dir: 一時ディレクトリ
        
    Returns:
        Path: 設定ディレクトリのパス
    """
    config_dir = temp_dir / ".fontsync"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def mock_sync_folder(temp_dir: Path) -> Path:
    """モックの同期元フォルダを作成
    
    Args:
        temp_dir: 一時ディレクトリ
        
    Returns:
        Path: 同期元フォルダのパス
    """
    sync_folder = temp_dir / "shared-fonts"
    sync_folder.mkdir()
    return sync_folder


@pytest.fixture
def mock_font_install_dir(temp_dir: Path) -> Path:
    """モックのフォントインストールディレクトリを作成
    
    Args:
        temp_dir: 一時ディレクトリ
        
    Returns:
        Path: フォントインストールディレクトリのパス
    """
    font_dir = temp_dir / "Library" / "Fonts"
    font_dir.mkdir(parents=True)
    return font_dir


@pytest.fixture
def sample_font_file(mock_sync_folder: Path) -> Path:
    """サンプルのフォントファイルを作成
    
    Args:
        mock_sync_folder: 同期元フォルダ
        
    Returns:
        Path: サンプルフォントファイルのパス
    """
    font_file = mock_sync_folder / "SampleFont.otf"
    # 実際のフォントファイルの代わりにダミーデータを作成
    font_file.write_bytes(b"dummy font data")
    return font_file


@pytest.fixture
def sample_config(mock_config_dir: Path, mock_sync_folder: Path) -> Path:
    """サンプルの設定ファイルを作成
    
    Args:
        mock_config_dir: 設定ディレクトリ
        mock_sync_folder: 同期元フォルダ
        
    Returns:
        Path: 設定ファイルのパス
    """
    config_file = mock_config_dir / "config.json"
    config_data = {
        "sync_folder": str(mock_sync_folder),
        "installed_fonts": {},
        "version": "1.0"
    }
    with open(config_file, "w") as f:
        json.dump(config_data, f)
    return config_file


@pytest.fixture
def mock_home_dir(monkeypatch, temp_dir: Path) -> Path:
    """ホームディレクトリをモック
    
    Args:
        monkeypatch: pytestのmonkeypatch
        temp_dir: 一時ディレクトリ
        
    Returns:
        Path: モックのホームディレクトリ
    """
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    return temp_dir 