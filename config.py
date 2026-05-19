"""
多币种相关性交易机器人 — 配置文件
策略: K线收盘前1分钟，检测超级趋势（≥N个币种同方向价格=100），
      买入该方向价格最低的币种
"""

# ── CLOB 端点 ──────────────────────────────────────────
CLOB_HOST = "https://clob.polymarket.com"

# ── Gamma API ───────────────────────────────────────────
GAMMA_EVENTS_API = "https://gamma-api.polymarket.com/events"

# ── 交易币种 ────────────────────────────────────────────
SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "HYPE", "BNB"]

# ── 检测币种（白名单）─────────────────────────────────────
# 空列表 = 检测全部 SYMBOLS；填入币种名 = 只检测这些
# 例: ENABLED_SYMBOLS = ["BTC", "ETH", "SOL"]  → 只检测BTC/ETH/SOL
ENABLED_SYMBOLS = ["HYPE"]

# ── 下单排除的币种（黑名单）────────────────────────────────
EXCLUDED_SYMBOLS = ["HYPE"]

# ── K线参数 ─────────────────────────────────────────────
CANDLE_MINUTES = 5
CANDLE_INTERVAL = CANDLE_MINUTES * 60  # 300 秒

# ── 检测窗口 ────────────────────────────────────────────
DETECT_BEFORE_CLOSE = 298    # K线结束前多少秒开始检测（1分钟）
DETECT_STOP_BEFORE_CLOSE = 120   # K线结束前多少秒停止扫描下单
SCAN_INTERVAL = 2           # 每次扫描间隔（秒）

# ── 超级趋势信号 ────────────────────────────────────────
SUPER_TREND_PRICE = 70     # 价格阈值（0-100），达到此值视为"确定"
MIN_TRIGGER_COUNT = 1       # 至少N个币种同方向达到阈值才触发

# ── 下单方向模式 ────────────────────────────────────────
# "reverse" = 反向（触发UP买最低DOWN，触发DOWN买最低UP，赌反转）
# "forward" = 正向（触发UP买最低UP，触发DOWN买最低DOWN，顺势）
ORDER_MODE = "forward"

# ── 下单参数 ────────────────────────────────────────────
BUY_SIZE = 3.0              # 每单数量（shares）
TICK_SIZE = "0.01"          # 价格精度

# ── 链与签名 ────────────────────────────────────────────
CHAIN_ID = 137
SIGNATURE_TYPE = 1
