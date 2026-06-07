"""VIX 预警系统主程序：取数 → 分级 + 分位 → 去重/静默 → 多通道分发 → 循环。"""
from __future__ import annotations

import logging
import sys
import time as _time
from datetime import datetime
from pathlib import Path

import schedule
import yaml

from src.data_fetcher import (
    Quote,
    get_qvix_50etf,
    get_qvix_50etf_history,
    get_vix,
    get_vix_history,
)
from src.indicators import Deduper, Thresholds, classify, in_quiet_hours, percentile_rank
from src.notifier import bark_push, desktop_popup

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.yaml"
STATE_FILE = ROOT / "data" / "dedup.json"

# 非 Windows 平台（如 GitHub Actions Linux 容器）自动跳过桌面 toast
DESKTOP_AVAILABLE = sys.platform == "win32"

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "main.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("vix-warning")


class Context:
    """启动时构建一次的运行上下文：配置、阈值、历史、去重器。"""

    def __init__(self) -> None:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.vix_t = Thresholds.from_dict(self.cfg["vix"])
        self.qvix_t = Thresholds.from_dict(self.cfg["qvix"])
        self.dedup = Deduper(STATE_FILE, self.cfg["dedup_hours"])
        self.quiet_start = self.cfg["quiet_hours"]["start"]
        self.quiet_end = self.cfg["quiet_hours"]["end"]
        self.surge_pct = self.cfg["intraday_change_alert_pct"]
        self.window = self.cfg["percentile_window_days"]
        self.vix_history: list[float] = []
        self.qvix_history: list[float] = []
        self._history_loaded_at: datetime | None = None

    def refresh_history(self, force: bool = False) -> None:
        now = datetime.now()
        stale = (
            self._history_loaded_at is None
            or (now - self._history_loaded_at).total_seconds() > 24 * 3600
        )
        if not (force or stale):
            return
        try:
            self.vix_history = get_vix_history(self.window)
            log.info(f"VIX 历史已加载: {len(self.vix_history)} 行")
        except Exception as e:
            log.warning(f"VIX 历史加载失败: {e}")
        try:
            self.qvix_history = get_qvix_50etf_history(self.window)
            log.info(f"QVIX 历史已加载: {len(self.qvix_history)} 行")
        except Exception as e:
            log.warning(f"QVIX 历史加载失败: {e}")
        self._history_loaded_at = now


def _send_alert(ctx: Context, label: str, q: Quote, level: str | None, history: list[float]) -> None:
    """组装消息 → 去重 → 多通道分发；通过则 mark_sent。"""
    surged = abs(q.change_pct) >= ctx.surge_pct
    if not level and not surged:
        return

    now = datetime.now()
    if in_quiet_hours(now, ctx.quiet_start, ctx.quiet_end):
        log.info(f"{label}: 命中静默时段 [{ctx.quiet_start}-{ctx.quiet_end}]，跳过")
        return

    title_tag = level or "异动"
    key = f"{label}_{title_tag}"
    if not ctx.dedup.should_send(key, now):
        log.info(f"{label}: '{key}' 在 {ctx.cfg['dedup_hours']}h 去重窗口内，跳过")
        return

    pct = percentile_rank(q.value, history)
    pct_str = f"  [{pct:.0f}% 分位]" if pct is not None else "  [分位:数据不足]"
    title = f"{label} {title_tag}: {q.value:.2f}{pct_str}"
    message = f"涨跌幅 {q.change_pct:+.2f}%  @ {q.timestamp}"
    urgent = level in ("恐慌", "极度恐慌")

    any_ok = False
    channels: list[tuple[str, callable]] = []
    if DESKTOP_AVAILABLE:
        channels.append(("桌面", desktop_popup))
    channels.append(("Bark", bark_push))
    for ch_name, ch_fn in channels:
        try:
            ch_fn(title, message, urgent=urgent)
            any_ok = True
        except Exception as e:
            log.warning(f"{ch_name} 推送失败: {e}")

    if any_ok:
        ctx.dedup.mark_sent(key, now)
        log.info(f"已推送: {title} | {message}")


def check_once(ctx: Context) -> None:
    log.info("---- 检查开始 ----")
    ctx.refresh_history()
    try:
        v = get_vix()
        log.info(f"VIX  = {v.value:6.2f}  ({v.change_pct:+.2f}%)   @ {v.timestamp}")
        _send_alert(ctx, "VIX", v, classify(v.value, ctx.vix_t), ctx.vix_history)
    except Exception as e:
        log.exception(f"取 VIX 失败: {e}")

    try:
        q = get_qvix_50etf()
        log.info(f"QVIX = {q.value:6.2f}  ({q.change_pct:+.2f}%)   @ {q.timestamp}  [{q.name}]")
        _send_alert(ctx, "QVIX", q, classify(q.value, ctx.qvix_t), ctx.qvix_history)
    except Exception as e:
        log.exception(f"取 QVIX 失败: {e}")


def main() -> None:
    ctx = Context()
    once = "--once" in sys.argv
    log.info(
        f"启动：mode={'once' if once else 'loop'}, "
        f"desktop={'on' if DESKTOP_AVAILABLE else 'off (非 Windows)'}, "
        f"interval={ctx.cfg['interval_min']}min, dedup={ctx.cfg['dedup_hours']}h, "
        f"quiet={ctx.quiet_start}-{ctx.quiet_end}, window={ctx.window}d"
    )
    check_once(ctx)
    if once:
        return
    schedule.every(ctx.cfg["interval_min"]).minutes.do(check_once, ctx)
    while True:
        schedule.run_pending()
        _time.sleep(1)


if __name__ == "__main__":
    main()
