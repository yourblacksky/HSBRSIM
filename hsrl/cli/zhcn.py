"""Load zhCN card names and texts from pre-extracted JSON.

Usage:
    from hsrl.cli.zhcn import zhcn
    name = zhcn.name("BG20_100")  # "剃刀沼泽地卜师"
    text = zhcn.text("BG20_100")  # "战吼：获取2张鲜血宝石。"
"""
import json
from pathlib import Path

_JSON_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "card_zhcn.json"


class ZhCN:
    def __init__(self):
        self._data: dict[str, dict[str, str]] = {}
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        if _JSON_PATH.exists():
            with open(_JSON_PATH, encoding="utf-8") as f:
                self._data = json.load(f)
        self._loaded = True

    def name(self, card_id: str) -> str:
        self._ensure_loaded()
        entry = self._data.get(card_id, {})
        return entry.get("n", "")

    def text(self, card_id: str) -> str:
        self._ensure_loaded()
        entry = self._data.get(card_id, {})
        return entry.get("t", "")

    def card(self, card_id: str) -> tuple[str, str]:
        self._ensure_loaded()
        entry = self._data.get(card_id, {})
        return entry.get("n", ""), entry.get("t", "")


zhcn = ZhCN()
