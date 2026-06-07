# VIX & 沪金预警系统 — 项目规划

> 目标：实时监控美股 VIX 恐慌指数和上海期货交易所黄金主力合约（AU0），当出现异常波动时通过**电脑弹窗** + **手机推送**及时提醒。

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

### 1.2 沪金（SHFE 黄金主力合约 AU0）
- 上海期货交易所黄金期货主力连续合约，代码 `AU0`。
- 数据获取：AKShare `futures_zh_realtime(symbol='黄金')` 返回所有 AU 合约实时报价。
- `changepercent` 字段是相对**前结算价**（不是前收盘价）的**小数**（如 `-0.029` = -2.9%），需乘 100 转百分数。
- 阈值：`|涨跌幅| ≥ 2%` 触发"异动"告警。不分级、不算历史分位（金价长期趋势使分位意义不大）。
- 交易时段：09:00-11:30、13:30-15:00、21:00-02:30 次日（夜盘）。

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
│  - VIX (Sina)   │      │  - 阈值判断      │
│  - 沪金 AU0     │      │  - 涨跌幅判断    │
│  - VIX 历史     │      │  - 历史分位数    │
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
| AKShare 取 QVIX（已弃用） | ~~`index_option_50etf_min_qvix` + 日线兜底~~ | 阶段 5 用户改需求，去掉 iVIX/QVIX 通道，换成沪金。 |

**已落地的代码**：

- `src/data_fetcher.py`：`get_vix()` + `get_shfe_gold()`（阶段 5 加入），统一返回 `Quote(name, value, change_pct, timestamp)`。
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
| QVIX 历史 252 日（已弃用） | ~~`ak.index_option_50etf_qvix()`~~ | 阶段 5 弃用整个 QVIX 通道。 |
| 分级（含反向 `warn_low`） | `src/indicators.py::classify` | "过度平静" 作为反向告警等级。 |
| 历史分位 | `src/indicators.py::percentile_rank` | 样本 < 30 行返回 None（告警中显示"数据不足"）。 |
| 去重 | `src/indicators.py::Deduper` | 两层去重：(1) `should_send/mark_sent` 同警报 key 在 N 小时窗口内不重复（key = `"{label}_{level_or_异动}"`）；(2) `is_repeat_quote/mark_quote_seen` 同 label 的同一笔行情 timestamp 只推一次。**非交易时段 Sina 持续返回上一收盘价 → 第二层会拦下重复推送**。状态持久化到 `data/dedup.json`，程序重启不丢。 |
| 静默时段 | `src/indicators.py::in_quiet_hours` | 支持跨午夜（如 22:00–07:00）；按本地时间比较。 |
| 配置 | `config.yaml`（阈值、间隔、去重小时、静默、分位窗口） + `.env`（凭据） | yaml 改后重启 main.py 生效。 |

**新增/改动的文件**：

- 新增 `config.yaml`：所有阈值集中管理。
- 新增 `src/indicators.py`：`Thresholds` / `classify` / `percentile_rank` / `in_quiet_hours` / `Deduper`。
- 改 `src/data_fetcher.py`：新增 `get_vix_history(days=252)`。（QVIX 历史函数后续阶段 5 移除。）
- 改 `main.py`：引入 `Context` 类（启动加载 config + 历史 + Deduper），`_send_alert` 整合分级 / 分位 / 静默 / 去重 / 多通道分发；告警标题附 `[N% 分位]`。
- 改 `.gitignore`：新增 `data/`（dedup 状态目录）。

**验收结果**：

- ✅ 单元测：`classify` 含 `warn_low`（VIX<13 → "过度平静"）、`in_quiet_hours` 跨午夜、`percentile_rank` 在实际历史上 21.50 = 86% 分位。
- ✅ 实测推送：`VIX 警戒: 21.50  [86% 分位]` 同时打到桌面 + Bark。
- ✅ 去重：立即重跑 → 日志 `VIX: 'VIX_警戒' 在 6h 去重窗口内，跳过`，无推送。
- ✅ 行情 timestamp 去重：Sina 在非交易时段返回相同的 timestamp（如美股已收盘，timestamp 一直是 04:15:01），第二轮检查直接日志 `VIX: 报价 timestamp ... 未刷新，跳过`，不进入告警管道。**对应"每个收盘只推一次总结"语义**。
- ✅ 静默：mock 02:30 北京时间 → 日志 `VIX: 命中静默时段 [00:00-09:00]，跳过`，无推送。

### 阶段 4：常驻运行 — GitHub Actions 云端调度 ✅ 已完成

**决策**：弃用本地常驻方案，**完全用 GitHub Actions 取代**。优点是电脑关机也有提醒；缺点是没有桌面 toast、调度有 5-15 分钟延迟。

**Actions 的硬限制（已规避）**：

| 限制 | 应对 |
| --- | --- |
| 容器无桌面 | `notifier.py` 把 `winotify` 改成条件导入；`main.py` 检测 `sys.platform != "win32"` 自动从通道列表里剔除桌面 |
| 容器每次销毁，`data/dedup.json` 不持久 | 用 `actions/cache@v5` 把整个 `data/` 目录跨 run 复用（key 唯一 + restore-keys 前缀匹配） |
| `.env` 不能进仓库 | `BARK_KEY` 等通过 **GitHub Secrets** 注入到环境变量 |
| 容器是 UTC 时间 | workflow 顶层 `env: TZ: Asia/Shanghai`，`datetime.now()` 自动返回北京时间 |
| 仓库 60 天无活动 → GitHub 自动停 cron；本仓库 / 账户的 schedule 触发器**整体静默失效**（重命名 workflow、最小 canary 测试都拿不到 schedule 触发，仅 dispatch 能跑） | **彻底放弃 `on.schedule`**，改用 [cron-job.org](https://cron-job.org/) 每 30 分钟 POST GitHub `dispatches` API 触发 `vix-monitor.yml`，外部触发的 API 调用本身也算 user activity，顺带不再需要 60 天保活机制 |
| Python 3.14 在 Linux 上 wheel 不全 | Actions 用 **Python 3.12**（本地仍用 3.14；代码只使用 3.10+ 共有语法） |
| pandas/numpy 等编译耗时 | `actions/setup-python` 的 `cache: pip` 复用 pip wheel 缓存，二次起接近秒级 |

**代码改动**：

- `main.py`：加 `--once` 模式（单次执行后退出，云端用）；`DESKTOP_AVAILABLE = sys.platform == "win32"` 自动决定是否进入桌面通道。
- `src/notifier.py`：`winotify` 改成 `try/except ImportError`；`desktop_popup` 在非 Windows 抛 `RuntimeError`，被 `main.py` 的 try/except 捕获记 WARN。env 读取容空（`BARK_SERVER`/`BARK_SOUND` 未配置时回落到代码默认）。
- `requirements.txt`：精简为直接依赖，`winotify` 加 `sys_platform == "win32"` 平台标记。Linux Actions 自动跳过 winotify 安装。

**workflow 文件**：

`.github/workflows/vix-monitor.yml` — 核心检查

- 触发：仅 `workflow_dispatch`。**不再用 `on.schedule`**（在本仓库 / 账户上整体失效，详见限制表第 5 行）。由 cron-job.org 外部 POST `dispatches` API 调起。
- 并发：`concurrency: group: vix-check, cancel-in-progress: false`，避免上一次未跑完下一次覆盖 dedup。
- 步骤：checkout → setup-python 3.12 → install deps → 恢复 dedup cache → `python main.py --once` → 上传 `logs/` artifact（7 天保留）。
- 超时：`timeout-minutes: 5`。

**外部触发（cron-job.org）**：

- 频率：北京时间 09:00–23:59 内每小时 `:07` 和 `:37`（每 30 分钟一次，错开 `:00` 高峰）。
- 请求：`POST https://api.github.com/repos/<owner>/<repo>/actions/workflows/vix-monitor.yml/dispatches`，body `{"ref":"main"}`。
- Headers：`Authorization: Bearer <fine-grained PAT>`、`Accept: application/vnd.github+json`、`X-GitHub-Api-Version: 2022-11-28`。
- PAT 权限最小化：仅 `Actions: Read and write`，仅授权本仓库。

**用户手动操作（一次性）**：

1. **强烈建议先在 Bark App 重新生成密钥**（旧 key 已出现在对话历史里）。
2. GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret：
   - `BARK_KEY` = 新的 16 位 key（必填）
   - `BARK_SERVER` = `https://api.day.app`（可选，留空走默认）
   - `BARK_SOUND` = `alarm`（可选）
3. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens 创建 PAT：仅 `Actions: Read and write`，仅授权本仓库。复制 token。
4. 注册 [cron-job.org](https://cron-job.org/) → 新建 cron job：见上 "外部触发（cron-job.org）" 段填写 URL / Headers / body / 时间。
5. 进 Actions 页面 → 选 "VIX Warning (cloud)" workflow → 点 "Run workflow" 手动跑一次验证。
6. 验证通过后无需操作，每 30 分钟（北京 09:00-23:59）自动跑。

### 阶段 5：换标的 — iVIX/QVIX 替换为沪金 ✅ 已完成

**起因**：iVIX 替代用的 QVIX 实际意义有限（用户更关心黄金避险标的）。改成监控 SHFE 黄金主力合约 AU0，触发条件简化为 `|涨跌幅| ≥ 2%`。

**改动**：

- `src/data_fetcher.py`：删 `get_qvix_50etf()` / `get_qvix_50etf_history()`；新增 `get_shfe_gold()`，调用 `ak.futures_zh_realtime(symbol='黄金')` 取 AU0 主力行。注意 `changepercent` 是小数，乘 100。
- `config.yaml`：删 `qvix` 块；`vix` 块下新增 `change_alert_pct: 20.0`（VIX 自己的异动阈值）；新增 `gold` 块 `change_alert_pct: 2.0`。删全局 `intraday_change_alert_pct`。
- `main.py`：
  - `Context` 删 `qvix_t` / `qvix_history` / `surge_pct`；新增 `vix_surge_pct` / `gold_surge_pct`。
  - `_send_alert()` 增 `surge_pct` 参数；`history` 为空时不显示分位（避免出现"[分位:数据不足]"这种不必要的提示）。
  - `check_once` 沪金分支：`level=None, history=[], surge_pct=ctx.gold_surge_pct`，仅靠涨跌幅触发。
- 行情时间戳去重对沪金同样生效（夜盘收盘后 Sina 持续返回同一收盘价 → 自动跳过）。

**验收（本地）**：

- ✅ `--once` 测试：VIX 21.50 +39.7% 推"警戒 [86% 分位]"；沪金 949.40 -2.93% 推"异动"，无分位字段。
- ✅ `dedup.json` 含 4 个 key：`VIX_警戒`、`__last_ts__VIX`、`沪金_异动`、`__last_ts__沪金`。

---

## 五、项目目录结构（当前实际）

```
Vix Warning System/
├── main.py                 # 入口（支持 --once）、调度、Context、多通道分发（阶段 1+2+3+4 ✅）
├── config.yaml             # 阈值/间隔/去重/静默/分位窗口（阶段 3 ✅）
├── requirements.txt        # 直接依赖 + 平台标记 winotify (Windows-only)（阶段 4 ✅）
├── .gitignore              # 屏蔽 venv / .env / logs / data / .claude（阶段 1+3+4 ✅）
├── .gitattributes          # 强制 *.yml/*.yaml 用 LF 行尾，规避 Windows CRLF 隐患
├── .env                    # 本地用：BARK_KEY 等（云端走 GitHub Secrets）
├── PROJECT_PLAN.md         # 本文档
├── .github/workflows/
│   └── vix-monitor.yml     # 核心检查：跑 main.py --once；由 cron-job.org 外部触发（阶段 4 ✅）
├── venv/                   # 虚拟环境（不进 git）
├── src/
│   ├── __init__.py
│   ├── data_fetcher.py     # get_vix + get_vix_history + get_shfe_gold（阶段 5 ✅）
│   ├── notifier.py         # desktop_popup（跨平台守护）+ bark_push()  ✅
│   └── indicators.py       # Thresholds/classify/percentile_rank/in_quiet_hours/Deduper  ✅
├── data/                   # 运行时状态（云端走 actions/cache，本地走文件）
│   └── dedup.json          # 去重持久化状态
└── logs/
    └── main.log            # 运行日志（UTF-8；云端会作为 artifact 上传）
```

---

## 六、注意事项与坑

1. **A 股交易时段 / 沪金交易时段**：沪金主力交易时段是 09:00-11:30、13:30-15:00、21:00-02:30 次日。非交易时段 Sina 返回上一收盘价，由"行情 timestamp 去重"保证不重复推送。
2. **VIX 时区**：美东时间 9:30–16:00 才有日内数据（DST 时 = 北京 21:30–04:00；标准时 = 22:30–05:00）。非交易时段 Sina 持续返回上一收盘价 → 由 `Deduper` 的"行情 timestamp 去重"保证每个收盘只触发一次告警（先到达本逻辑的那次推送）。
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
- **遇到要扩新标的时**：参考阶段 5 给沪金加通道的做法 — `data_fetcher.py` 加一个 `get_xxx()` 函数返回 `Quote`，`config.yaml` 加阈值块，`main.py::check_once` 加一个 `_send_alert(...)` 调用即可。

---

## 八、下一步

如果这份规划方向 OK，可以告诉我从哪一步开始，比如：
- "帮我搭好项目骨架和虚拟环境"
- "先实现阶段 1 的 MVP"
- "我已经注册了 Server 酱，帮我接进去"

我会按对应阶段一步步实现。
