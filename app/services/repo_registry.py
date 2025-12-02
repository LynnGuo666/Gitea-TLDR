"""简单的仓库配置和密钥存储"""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Dict, Optional


class RepoRegistry:
    """用于存储每个仓库的Webhook密钥和基础信息."""

    def __init__(self, work_dir: str, filename: str = "repo_registry.json"):
        self.base_path = Path(work_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.base_path / filename
        self._lock = Lock()
        self._data: Dict[str, Dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if not self.registry_file.exists():
            self.registry_file.write_text("{}", encoding="utf-8")
        try:
            self._data = json.loads(self.registry_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # 如果文件损坏，重置为空以避免运行时失败
            self._data = {}
            self.registry_file.write_text("{}", encoding="utf-8")

    def _save(self) -> None:
        self.registry_file.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _key(self, owner: str, repo: str) -> str:
        return f"{owner}/{repo}"

    def get_secret(self, owner: str, repo: str) -> Optional[str]:
        key = self._key(owner, repo)
        with self._lock:
            repo_info = self._data.get(key, {})
            return repo_info.get("webhook_secret")

    def set_secret(self, owner: str, repo: str, secret: str) -> None:
        key = self._key(owner, repo)
        with self._lock:
            repo_info = self._data.get(key, {})
            repo_info["webhook_secret"] = secret
            self._data[key] = repo_info
            self._save()

    def get_repo_info(self, owner: str, repo: str) -> Dict[str, str]:
        key = self._key(owner, repo)
        with self._lock:
            return self._data.get(key, {})

    def list_all(self) -> Dict[str, Dict[str, str]]:
        with self._lock:
            return dict(self._data)

