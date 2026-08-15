"""Minimal zero-dependency JSON store with atomic writes (temp + rename)."""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional


class JsonStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {"collections": {}, "events": []}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                self._data = json.load(f)
            self._data.setdefault("collections", {})
            self._data.setdefault("events", [])

    def _save(self) -> None:
        d = self.path + ".tmp"
        with open(d, "w") as f:
            json.dump(self._data, f)
        os.replace(d, self.path)

    def put(self, coll: str, record: dict, event: Optional[str] = None) -> None:
        with self._lock:
            self._data.setdefault("collections", {}).setdefault(coll, {})[record["id"]] = record
            if event:
                self._data["events"].append({"event": event, "id": record.get("id"), "ts": time.time()})
            self._save()

    def get(self, coll: str, id: str) -> Optional[dict]:
        with self._lock:
            return self._data.get("collections", {}).get(coll, {}).get(id)

    def find(self, coll: str, **filters) -> List[dict]:
        with self._lock:
            items = list(self._data.get("collections", {}).get(coll, {}).values())
            for k, v in filters.items():
                items = [i for i in items if i.get(k) == v]
            return items

    def delete(self, coll: str, id: str, event: Optional[str] = None) -> None:
        with self._lock:
            c = self._data.get("collections", {}).get(coll, {})
            if id in c:
                del c[id]
                if event:
                    self._data["events"].append({"event": event, "id": id, "ts": time.time()})
                self._save()
