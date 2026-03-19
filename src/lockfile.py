"""fontops.lock ファイルのデータモデルと I/O"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LockStyle:
    """フォントスタイルの定義"""

    name: str

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LockStyle":
        if "name" not in data:
            raise ValueError("LockStyle requires 'name' field")
        if not isinstance(data["name"], str):
            raise ValueError("LockStyle 'name' must be a string")
        return cls(name=data["name"])


@dataclass
class LockFont:
    """lock ファイル内のフォント定義"""

    family: str
    source: str
    styles: List[LockStyle] = field(default_factory=list)
    hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family": self.family,
            "source": self.source,
            "styles": [s.to_dict() for s in self.styles],
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LockFont":
        if "family" not in data:
            raise ValueError("LockFont requires 'family' field")
        if "source" not in data:
            raise ValueError("LockFont requires 'source' field")
        if "styles" not in data:
            raise ValueError("LockFont requires 'styles' field")
        styles = [LockStyle.from_dict(s) for s in data["styles"]]
        return cls(
            family=data["family"],
            source=data["source"],
            styles=styles,
            hash=data.get("hash"),
        )


@dataclass
class FontopsLock:
    """fontops.lock ファイルのルートモデル"""

    fontops_version: str
    project_name: str
    fonts: List[LockFont] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fontops_version": self.fontops_version,
            "project_name": self.project_name,
            "fonts": [f.to_dict() for f in self.fonts],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FontopsLock":
        if "fontops_version" not in data:
            raise ValueError("FontopsLock requires 'fontops_version' field")
        if "project_name" not in data:
            raise ValueError("FontopsLock requires 'project_name' field")
        if "fonts" not in data:
            raise ValueError("FontopsLock requires 'fonts' field")
        if not isinstance(data["fonts"], list):
            raise ValueError("FontopsLock 'fonts' must be a list")
        fonts = [LockFont.from_dict(f) for f in data["fonts"]]
        return cls(
            fontops_version=data["fontops_version"],
            project_name=data["project_name"],
            fonts=fonts,
        )


def load_lock(path: Path) -> FontopsLock:
    """fontops.lock ファイルを読み込む。

    Args:
        path: lock ファイルのパス

    Returns:
        FontopsLock インスタンス

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: JSON が不正またはスキーマが不正な場合
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"Lock file not found: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in lock file: {e}") from e
    return FontopsLock.from_dict(data)


def save_lock(lock: FontopsLock, path: Path) -> None:
    """fontops.lock ファイルを書き込む。

    Args:
        lock: 保存する FontopsLock インスタンス
        path: 書き込み先のパス
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lock.to_dict(), f, indent=2, ensure_ascii=False)
        f.write("\n")
