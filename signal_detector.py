"""
信号检测器 — 超级趋势策略
检测 ENABLED_SYMBOLS（或全部 SYMBOLS）中 >= MIN_TRIGGER_COUNT 个币种
同方向价格达到 SUPER_TREND_PRICE 时，按 ORDER_MODE 决定下单方向。

ORDER_MODE = "reverse"（默认）:
    触发UP → 买最低DOWN，触发DOWN → 买最低UP（赌反转）
ORDER_MODE = "forward":
    触发UP → 买最低UP，  触发DOWN → 买最低DOWN（顺势）
"""

import logging
from config import SUPER_TREND_PRICE, MIN_TRIGGER_COUNT, EXCLUDED_SYMBOLS, ENABLED_SYMBOLS, ORDER_MODE

logger = logging.getLogger(__name__)


def detect_signal(markets: dict[str, dict], ordered_symbols: set[str] = None) -> list[dict]:
    """
    检测超级趋势信号，触发后从全部币种中下单

    参数:
        markets: fetch_realtime_prices() 返回的字典 {symbol: market_info}（全部币种）
        ordered_symbols: 已下单的 (symbol, direction) 集合，跳过这些

    返回:
        触发时返回 list（1个信号字典），否则返回 []
    """
    if ordered_symbols is None:
        ordered_symbols = set()

    # ── 步骤1：只用白名单币种检测趋势（若 ENABLED_SYMBOLS 非空）──────────
    detection_markets = {s: info for s, info in markets.items()
                         if not ENABLED_SYMBOLS or s in ENABLED_SYMBOLS}

    if len(detection_markets) < MIN_TRIGGER_COUNT:
        logger.debug("检测币种数 %d < 最低要求 %d，跳过", len(detection_markets), MIN_TRIGGER_COUNT)
        return []

    # 统计达到阈值的币种（仅检测集）
    up_super = []
    down_super = []

    for symbol, info in detection_markets.items():
        up_price = info["up_price"]
        down_price = info["down_price"]
        if up_price >= SUPER_TREND_PRICE:
            up_super.append((symbol, up_price, info["up_token_id"]))
        if down_price >= SUPER_TREND_PRICE:
            down_super.append((symbol, down_price, info["down_token_id"]))

    # 检查是否触发
    triggered_direction = None
    triggered = None
    for direction, items in [("up", up_super), ("down", down_super)]:
        if len(items) >= MIN_TRIGGER_COUNT:
            triggered_direction = direction
            triggered = items
            break

    if not triggered_direction:
        logger.debug(
            "未触发  检测集 up>=%d: %d个  down>=%d: %d个  (需要>= %d)",
            SUPER_TREND_PRICE, len(up_super),
            SUPER_TREND_PRICE, len(down_super),
            MIN_TRIGGER_COUNT,
        )
        return []

    triggered_names = [t[0] for t in triggered]

    # ── 步骤2：根据 ORDER_MODE 决定下单方向 ───────────────────────────────
    if ORDER_MODE == "forward":
        order_direction = triggered_direction  # 顺势
    else:
        order_direction = "down" if triggered_direction == "up" else "up"  # 反向（默认）

    candidates = []
    for symbol, info in markets.items():
        if symbol in EXCLUDED_SYMBOLS:
            continue
        if (symbol, order_direction) in ordered_symbols:
            continue
        order_price = info[f"{order_direction}_price"]
        order_token_id = info[f"{order_direction}_token_id"]
        candidates.append((symbol, order_price, order_token_id))

    if not candidates:
        logger.warning("下单方向=%s 无可用币种", order_direction.upper())
        return []

    candidates.sort(key=lambda x: x[1])
    target_symbol, target_price, target_token_id = candidates[0]

    mode_label = "顺势" if ORDER_MODE == "forward" else "反向"
    signal = {
        "direction": order_direction,
        "target_symbol": target_symbol,
        "target_price": target_price,
        "target_token_id": target_token_id,
        "triggered_direction": triggered_direction,
        "triggered_symbols": triggered_names,
        "triggered_count": len(triggered),
    }

    logger.info(
        "超级趋势触发! 趋势方向=%s  触发币种(%d)=%s",
        triggered_direction.upper(), len(triggered), triggered_names,
    )
    logger.info(
        "  → 下单: %s %s  价格=%.1f  (%s，候选=%s)",
        target_symbol, order_direction.upper(), target_price,
        mode_label, [c[0] for c in candidates],
    )

    return [signal]
