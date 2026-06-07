# VIX & iVIX 恐慌指数预警系统 — 项目规划

> 目标：实时监控美股 VIX 和 A 股 iVIX（50ETF 期权隐含波动率），当出现异常波动时通过**电脑弹窗** + **手机推送**及时提醒。

---

## 一、技术原理与关键认知

在动手前，先理清两个指数的现状，避免走弯路。

### 1.1 VIX（美国恐慌指数）
- 由 CBOE（芝加哥期权交易所）发布，代码 `^VIX`。
- 数据获取容易：Yahoo Finance、Investing.com、新浪财经、东方财富都有。
- 典型阈值参考：
  - `VIX < 20`：市场平静
  - `20 ~ 30`：警戒
  - `> 30`：恐慌
  - `> 40`：极度恐慌（历史罕见）

### 1.2 iVIX（中国波指）⚠️ 重点
- **官方 iVIX 自 2018 年 2 月起已停止发布**，所以你**无法直接抓到一个叫 iVIX 的行情代码**。
- 替代方案（业界通用做法）：
  - 用上证 50ETF 期权 / 沪深 300ETF 期权的**期权链**，按 CBOE 的 VIX 白皮书公式自己计算。
  - 或者使用第三方已计算好的数据接口（如 Tushare Pro 的 `index_daily` 中部分指数、AKShare 的 `index_option_50etf_qvix`）。
- **推荐做法**：先用 AKShare 的现成接口（最省事），后续再考虑自己实现公式。

---

## 二、准备工作清单

### 2.1 软件环境
| 项目 | 推荐版本 / 说明 |
| --- | --- |
| Python | 3.10+（建议用 conda 或 venv 隔离环境） |
| 编辑器 | VS Code + Claude Code 插件 |
| 操作系统 | 已是 Windows 11 ✅ |

### 2.2 数据源账号
1. **AKShare**：开源免费，无需注册，`pip install akshare`。
2. **Tushare Pro**（可选）：[tushare.pro](https://tushare.pro) 注册，部分接口需要积分。
3. **Yahoo Finance**：`pip install yfinance`，无需账号。

### 2.3 推送通道（手机端二选一或全选）
| 通道 | 适合人群 | 注册地址 | 备注 |
| --- | --- | --- | --- |
| **Server 酱（Server Chan）** | 微信用户 | sct.ftqq.com | 推送到微信，免费版每天 5 条 |
| **PushPlus** | 微信用户 | pushplus.plus | 微信推送，免费额度更高 |
| **Bark** | iPhone 用户 | App Store 下载 Bark | 自建服务器或用官方，极简 |
| **Telegram Bot** | 已翻墙用户 | @BotFather | 国内不稳定，不推荐主用 |
| **邮件 SMTP** | 所有人 | QQ 邮箱 / Gmail 开 SMTP | 兜底方案，最稳定 |

> 已选组合：**Bark（主） + 邮件（兜底）**。

### 2.4 桌面弹窗依赖
- Windows 推荐：`plyer` 或 `win10toast-click`
- 也可以用 `tkinter` 自己画一个置顶窗口

---

## 三、系统架构

```
┌─────────────────┐
│  定时调度器     │  (schedule / APScheduler)
│  每 N 分钟触发  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  数据获取模块   │─────▶│  指标计算模块    │
│  - VIX          │      │  - 阈值判断      │
│  - iVIX/QVIX    │      │  - 涨跌幅判断    │
│  - 50ETF期权链  │      │  - 历史分位数    │
└─────────────────┘      └────────┬─────────┘
                                  │ 触发警报
                                  ▼
                         ┌──────────────────┐
                         │  通知分发模块    │
                         │  ├─ 桌面弹窗     │
                         │  ├─ Bark (iOS)   │
                         │  └─ 邮件 (兜底)  │
                         └──────────────────┘
```

---

## 四、实施步骤

### 阶段 1：最小可用版本（MVP） ✅ 已完成
**目标**：跑通"取数 → 判断 → 弹窗"主流程。

**实际选型与原因**：

| 计划 | 实际 | 原因 |
| --- | --- | --- |
| `plyer` 弹窗 | **`winotify`** | `plyer` 在 Windows 上是用老的 WinRT API；`winotify` 是 Win10/11 原生 toast，活跃维护，支持点击回调与告警音。`win10toast-click` 试过，依赖已被移除的 `pkg_resources`，在 Python 3.14 上 import 即报错，弃用。 |
| AKShare 取 VIX | **Sina 实时行情** `hq.sinajs.cn/list=znb_VIX` | AKShare 没有干净的 VIX 接口；Sina 的 `znb_VIX` 返回最新价、涨跌幅、时间，足够 MVP。需带 `Referer: https://finance.sina.com.cn/`。 |
| AKShare 取 QVIX | `index_option_50etf_min_qvix` 优先 + `index_option_50etf_qvix` 兜底 | 分钟接口仅盘中有数据，盘前/盘后回退日线。AKShare 还有 300ETF/500ETF/创业板/科创板等多套 QVIX，后续可扩展。 |

**已落地的代码**：

- `src/data_fetcher.py`：`get_vix()` + `get_qvix_50etf()`，统一返回 `Quote(name, value, change_pct, timestamp)`。
- `src/notifier.py`：`desktop_popup(title, message, urgent=False)`，`urgent=True` 时使用循环警报音。
- `main.py`：`check_once()` 单轮 + `schedule.every(5).minutes` 循环；阈值与异动判断写死在文件顶部（阶段 3 抽到 config）。
- `logs/main.log`：UTF-8 日志，规避 Windows 控制台 GBK 乱码。

**Python 3.14.5 上的坑**：新版 setuptools 移除了 `pkg_resources`，依赖该模块的旧包（如 `win10toast-click`、`pypiwin32`）会直接挂；选包时优先看是否有 cp314 wheel + 最近一年的更新。

**运行方式**：
```bash
# 单次测试
./venv/Scripts/python.exe -m src.data_fetcher      # 取数
./venv/Scripts/python.exe -m src.notifier          # 弹窗
./venv/Scripts/python.exe -c "from main import check_once; check_once()"  # 端到端一轮

# 常驻
./venv/Scripts/python.exe main.py
```

### 阶段 2：加上手机推送（Bark） ✅ 已完成

**实际选型**：仅 Bark（用户已确认 iPhone 用户），邮件兜底**暂不实现**。两通道即可（桌面 + Bark），不单独建 `src/alerts.py`，直接在 `main.py::_maybe_alert` 里循环并发分发，每个通道独立 try/except。后续如加第 3 个通道再抽出。

**为什么用 Bark**：iOS 原生体验最好的开源推送方案，自定义铃声、分组、URL 跳转都支持；服务端可以用官方公共服务器，也可以自建。**没有官方 pip 包**，调用方式就是 HTTP，已装的 `requests` 就够。

#### 2.1 准备工作（已完成）

1. **下载 Bark App**（iOS 限定）：App Store 搜 "Bark - Customed Notifications"。
2. **拿到推送 Key**：打开 App → 默认首页就显示你的设备 URL，形如 `https://api.day.app/XXXXXXXXXXXXXXXX/`，中间那段就是 `BARK_KEY`，**等同于密码，不要外泄**。如不慎泄露，App 内可一键"重新生成密钥"。
3. **手机端测试一次**：浏览器直接打开 `https://api.day.app/{key}/Hello/Bark测试`，App 应立刻收到推送。

#### 2.2 配置文件（已完成）

`.env`（已被 `.gitignore` 屏蔽）：
```bash
BARK_KEY=你的16位key
BARK_SERVER=https://api.day.app          # 自建服务器就改这里
BARK_SOUND=alarm                          # 紧急级别使用的铃声
```

#### 2.3 编码任务（已完成）

- `src/notifier.py` 新增 `bark_push(title, message, urgent=False)`：
  - POST JSON 到 `{BARK_SERVER}/{BARK_KEY}`
  - urgent=True → `level: critical`（强制响铃）+ `sound: alarm`
  - urgent=False → `level: active` + 默认音
  - 统一加 `group: "VIX预警"`，同组消息在锁屏上会折叠
  - 通过 `python-dotenv` 从 `.env` 读凭据，模块首次 import 时加载
- `main.py::_maybe_alert` 改成 `for ch_name, ch_fn in (...)` 循环：单通道异常只记 WARN，其他通道继续。

#### 2.4 验收结果

- ✅ `python -m src.notifier --bark` 手机端立刻收到推送（Bark API 返回 `code: 200`）。
- ✅ `python -c "from main import check_once; check_once()"` 端到端跑通：VIX 21.50 +39.70% 同时触发桌面 toast + Bark 推送，日志无 WARN。
- ✅ `.env` 已写入 `.gitignore`，不会进版本控制。

**单通道故障演练（设计上保证，未额外测）**：若把 `BARK_KEY` 改成错的，`bark_push` 抛异常 → `main.py` 的 try/except 捕获 → 日志记 `WARN: Bark 推送失败`，桌面通道正常工作，下一轮自动重试。

### 阶段 3：完善预警逻辑 ✅ 已完成
1. **多级阈值**：警戒 / 恐慌 / 极度恐慌，对应不同提醒强度，Vix大于20或小于13时都要通知。
2. **变化率监测**：单日涨跌幅 > 20% 也触发。
3. **历史分位数**：当前 VIX 在过去一年中处于多少分位（更有参考价值）。
4. **去重**：同一警报6小时内不重复推送（北京时间00：00~9~00不要推送）。
5. **配置文件**：把阈值抽到 `config.yaml`，把 `BARK_KEY` / SMTP 凭据抽到 `.env`。

**实际选型与原因**：

| 需求 | 实际实现 | 备注 |
| --- | --- | --- |
| VIX 历史 252 日 | **CBOE 官方 CSV** `cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv` | Yahoo/Stooq/Sina 日 K/EastMoney 都试过：Yahoo 国内 403、Stooq PoW 反爬、Sina 美股日 K 返回 null、EastMoney 没收录 VIX 现货指数。CBOE 官方 CSV 1990 年至今完整，469KB，一次拉取常驻内存。 |
| QVIX 历史 252 日 | `ak.index_option_50etf_qvix()` | 直接返回 2700+ 行日线，tail(252) 即可。 |
| 分级（含反向 `warn_low`） | `src/indicators.py::classify` | "过度平静" 作为反向告警等级。 |
| 历史分位 | `src/indicators.py::percentile_rank` | 样本 < 30 行返回 None（告警中显示"数据不足"）。 |
| 去重 | `src/indicators.py::Deduper` | key = `"{label}_{level_or_异动}"`，状态持久化到 `data/dedup.json`（程序重启不丢）。 |
| 静默时段 | `src/indicators.py::in_quiet_hours` | 支持跨午夜（如 22:00–07:00）；按本地时间比较。 |
| 配置 | `config.yaml`（阈值、间隔、去重小时、静默、分位窗口） + `.env`（凭据） | yaml 改后重启 main.py 生效。 |

**新增/改动的文件**：

- 新增 `config.yaml`：所有阈值集中管理。
- 新增 `src/indicators.py`：`Thresholds` / `classify` / `percentile_rank` / `in_quiet_hours` / `Deduper`。
- 改 `src/data_fetcher.py`：新增 `get_vix_history(days=252)` 和 `get_qvix_50etf_history(days=252)`。
- 改 `main.py`：引入 `Context` 类（启动加载 config + 历史 + Deduper），`_send_alert` 整合分级 / 分位 / 静默 / 去重 / 多通道分发；告警标题附 `[N% 分位]`。
- 改 `.gitignore`：新增 `data/`（dedup 状态目录）。

**验收结果**：

- ✅ 单元测：`classify` 含 `warn_low`（VIX<13 → "过度平静"）、`in_quiet_hours` 跨午夜、`percentile_rank` 在实际历史上 21.50 = 86% 分位。
- ✅ 实测推送：`VIX 警戒: 21.50  [86% 分位]` 同时打到桌面 + Bark。
- ✅ 去重：立即重跑 → 日志 `VIX: 'VIX_警戒' 在 6h 去重窗口内，跳过`，无推送。
- ✅ 静默：mock 02:30 北京时间 → 日志 `VIX: 命中静默时段 [00:00-09:00]，跳过`，无推送。

### 阶段 4：长期运行（半天）
1. 让程序后台常驻：
   - 方案 A：Windows 任务计划程序，每 N 分钟启动一次。
   - 方案 B：写成 Windows 服务（用 `nssm` 工具包装）。
   - 方案 C：直接 `pythonw main.py` 后台跑。
2. 加日志（`logging` 模块），方便排查问题。
3. 加异常捕获（网络断了不能让程序挂掉）。

### 阶段 5（可选）：自己算 iVIX
1. 拉取 50ETF 期权链：AKShare 的 `option_finance_board`。
2. 实现 CBOE VIX 白皮书公式（涉及无风险利率、远期价格、期权加权方差）。
3. 与 AKShare 的 QVIX 对比验证，差异 < 1% 即可。

---

## 五、项目目录结构（当前实际）

```
Vix Warning System/
├── main.py                 # 入口、调度、Context、多通道分发（阶段 1+2+3 ✅）
├── config.yaml             # 阈值/间隔/去重/静默/分位窗口（阶段 3 ✅）
├── requirements.txt        # 已固定依赖版本（阶段 1 ✅）
├── .gitignore              # 屏蔽 venv / .env / logs / data（阶段 1+3 ✅）
├── .env                    # BARK_KEY / BARK_SERVER / BARK_SOUND（阶段 2 ✅）
├── PROJECT_PLAN.md         # 本文档
├── venv/                   # 虚拟环境（不进 git）
├── src/
│   ├── __init__.py
│   ├── data_fetcher.py     # get_vix/get_qvix + get_vix_history/get_qvix_50etf_history  ✅
│   ├── notifier.py         # desktop_popup() + bark_push()  ✅
│   └── indicators.py       # Thresholds/classify/percentile_rank/in_quiet_hours/Deduper  ✅
├── data/                   # 运行时状态（不进 git）
│   └── dedup.json          # 去重持久化状态
└── logs/
    └── main.log            # 运行日志（UTF-8）

# 阶段 4 将做：Windows 任务计划 / nssm 后台常驻 / 异常重试退避
# 阶段 5 将做（可选）：自算 iVIX（拉 50ETF 期权链 + CBOE VIX 白皮书公式）
# 阶段 2 计划过 src/alerts.py，实际两通道直接内联，等加第 3 通道时再抽。
```

---

## 六、注意事项与坑

1. **A 股交易时段**：iVIX 只在 9:30–15:00 有效，其他时段不要触发"实时"警报。
2. **VIX 时区**：美东时间 9:30–16:00 才有日内数据，注意时区换算。
3. **数据延迟**：免费接口通常延迟 15 分钟，对预警场景一般够用。
4. **接口限流**：AKShare 与 Sina 行情都有频率限制，调度间隔不要短于 1 分钟。
5. **敏感信息**：Bark key、邮箱密码绝不要硬编码进代码或提交到仓库（`.gitignore` 已屏蔽 `.env`）。
6. **测试推送通道**：先单独跑通每个通道再集成，避免出问题时不知道是哪一环挂了。
7. **Python 3.14 兼容性**：选包时关注是否提供 cp314 wheel，依赖 `pkg_resources` 的老包（如 `win10toast-click`）一律换掉。
8. **Windows 控制台编码**：默认 GBK，直接 `print` 中文会乱码；日志统一写文件并指定 `encoding="utf-8"`。

---

## 七、与 Claude Code 协作建议

- **分模块开发**：每次让 Claude Code 只做一个模块（先 `data_fetcher.py`，再 `notifier.py`），便于检查。
- **先跑通再优化**：MVP 阶段不要追求架构完美，能弹窗就是胜利。
- **真实测试**：每写完一个推送通道，立刻让 Claude Code 帮你写一个 `test_xxx.py` 实测一次。
- **遇到 iVIX 计算时**：把 CBOE 的 VIX 白皮书 PDF 喂给 Claude，让它对照公式实现，比直接让它"凭印象"写更靠谱。

---

## 八、下一步

如果这份规划方向 OK，可以告诉我从哪一步开始，比如：
- "帮我搭好项目骨架和虚拟环境"
- "先实现阶段 1 的 MVP"
- "我已经注册了 Server 酱，帮我接进去"

我会按对应阶段一步步实现。
