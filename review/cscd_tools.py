"""CSCD 客户端工厂。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from cscd_client import CscdClient


def load_config(path: str = "config.yaml") -> dict:
    config_path = Path(__file__).parent / path
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def get_cscd_client() -> CscdClient:
    config = load_config().get("cscd", {})
    return CscdClient(config)


def ensure_cscd_api_code() -> None:
    """运行前获取新的 ApiCode。"""
    get_cscd_client().refresh_api_code()
