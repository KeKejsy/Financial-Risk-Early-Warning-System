"""数据获取：CBOE VIX（Sina 实时 + CBOE 官方历史）+ 沪金 AU 主力（AKShare）。"""
from dataclasses import dataclass

import akshare as ak
import requests

SINA_VIX_URL = "https://hq.sinajs.cn/list=znb_VIX"
SINA_HEADERS = {"Referer": "https://finance.sina.com.cn/"}
CBOE_VIX_HISTORY_URL = (
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
)


@dataclass
class Quote:
    name: str
    value: float
    change_pct: float
    timestamp: str


def get_vix(timeout: float = 10) -> Quote:
    r = requests.get(SINA_VIX_URL, headers=SINA_HEADERS, timeout=timeout)
    r.encoding = "gbk"
    body = r.text
    payload = body.split('"', 2)[1] if '"' in body else ""
    if not payload:
        raise RuntimeError(f"Sina VIX 响应为空: {body!r}")
    parts = payload.split(",")
    # 字段顺序: 名称, 最新价, 涨跌额, 涨跌幅%, _, _, 日期, 时间, 开盘, 前收, 最高, 最低, _
    return Quote(
        name=parts[0],
        value=float(parts[1]),
        change_pct=float(parts[3]),
        timestamp=f"{parts[6]} {parts[7]}",
    )


def get_vix_history(days: int = 252, timeout: float = 30) -> list[float]:
    """从 CBOE 官方拉 VIX 日线收盘价，返回最近 N 个交易日（按日期升序）。"""
    r = requests.get(
        CBOE_VIX_HISTORY_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout
    )
    r.raise_for_status()
    closes: list[float] = []
    for line in r.text.strip().splitlines()[1:]:  # CSV header: DATE,OPEN,HIGH,LOW,CLOSE
        parts = line.split(",")
        try:
            closes.append(float(parts[-1]))
        except (ValueError, IndexError):
            continue
    return closes[-days:] if days else closes


def get_shfe_gold() -> Quote:
    """SHFE 黄金期货主力合约（AU0）实时报价。
    changepercent 是相对前结算价的小数（如 -0.029 = -2.9%）。
    """
    df = ak.futures_zh_realtime(symbol="黄金")
    row = df[df["symbol"] == "AU0"].iloc[0]
    return Quote(
        name="沪金主力 AU0",
        value=float(row["trade"]),
        change_pct=float(row["changepercent"]) * 100,
        timestamp=f"{row['tradedate']} {row['ticktime']}",
    )


if __name__ == "__main__":
    print("VIX :", get_vix())
    print("GOLD:", get_shfe_gold())
    vh = get_vix_history()
    print(f"VIX  历史: {len(vh)} 行, 范围 [{min(vh):.2f}, {max(vh):.2f}]")
