"""指标计算与判断：分级、历史分位、去重、静默时段。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Sequence


@dataclass
class Thresholds:
    warn_high: float
    panic: float
    extreme: float | None = None
    warn_low: float | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Thresholds":
        return cls(
            warn_high=d["warn_high"],
            panic=d["panic"],
            extreme=d.get("extreme"),
            warn_low=d.get("warn_low"),
        )


def classify(value: float, t: Thresholds) -> str | None:
    if t.extreme is not None and value >= t.extreme:
        return "极度恐慌"
    if value >= t.panic:
        return "恐慌"
    if value >= t.warn_high:
        return "警戒"
    if t.warn_low is not None and value < t.warn_low:
        return "过度平静"
    return None


def percentile_rank(value: float, series: Sequence[float]) -> float | None:
    """value 在 series 中的百分位 (0-100)；样本 < 30 返回 None。"""
    samples = [x for x in series if x is not None]
    if len(samples) < 30:
        return None
    below_or_eq = sum(1 for x in samples if x <= value)
    return below_or_eq / len(samples) * 100


def in_quiet_hours(now: datetime, start: str, end: str) -> bool:
    """now 是否落在 [start, end) 内（HH:MM，本地时间）。支持跨午夜。"""
    def _parse(s: str) -> time:
        hh, mm = s.split(":")
        return time(int(hh), int(mm))

    s, e = _parse(start), _parse(end)
    t = now.time()
    if s <= e:
        return s <= t < e
    return t >= s or t < e


@dataclass
class Deduper:
    """每个告警 key 记录上次推送时间，N 小时内不重复。文件持久化。"""

    state_file: Path
    dedup_hours: float
    _state: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.state_file.exists():
            try:
                self._state = json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                self._state = {}

    def should_send(self, key: str, now: datetime) -> bool:
        last_str = self._state.get(key)
        if not last_str:
            return True
        last = datetime.fromisoformat(last_str)
        return now - last >= timedelta(hours=self.dedup_hours)

    def mark_sent(self, key: str, now: datetime) -> None:
        self._state[key] = now.isoformat(timespec="seconds")
        self._persist()

    def is_repeat_quote(self, label: str, quote_ts: str) -> bool:
        """该 label 的上次行情 timestamp 是否与本次相同（行情未刷新）。"""
        return self._state.get(f"__last_ts__{label}") == quote_ts

    def mark_quote_seen(self, label: str, quote_ts: str) -> None:
        """记录已处理过的行情 timestamp，避免下次重复推同一笔报价。"""
        self._state[f"__last_ts__{label}"] = quote_ts
        self._persist()

    def _persist(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
