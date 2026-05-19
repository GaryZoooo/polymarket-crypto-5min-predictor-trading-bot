"""
多币种市场扫描器
两步走：
  1. Gamma API 获取 token_id（每个新K线周期只需查一次）
  2. CLOB POST /prices 批量获取实时价格（每次扫描，一次POST搞定14个价格）
"""

import json
import time
import httpx
import logging
from config import GAMMA_EVENTS_API, SYMBOLS, ENABLED_SYMBOLS, CANDLE_INTERVAL

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

CLOB_HOST = "https://clob.polymarket.com"


def _parse_json_field(value, default=None):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def get_candle_timestamps() -> tuple[int, int]:
    """
    返回当前正在交易的5分钟K线周期的 (start_ts, close_ts)
    """
    now = int(time.time())
    start_ts = (now // CANDLE_INTERVAL) * CANDLE_INTERVAL
    close_ts = start_ts + CANDLE_INTERVAL
    return start_ts, close_ts


def fetch_token_ids(symbol: str, start_ts: int) -> dict | None:
    """
    通过 Gamma API 获取单个币种的 token_id
    """
    slug = f"{symbol.lower()}-updown-5m-{start_ts}"

    try:
        resp = httpx.get(
            GAMMA_EVENTS_API,
            params={"slug": slug},
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("查询 %s 市场失败: %s", symbol, e)
        return None

    if not data:
        return None

    event = data[0]
    if not event.get("active") or event.get("closed"):
        return None

    markets = event.get("markets", [])
    if not markets:
        return None

    market = markets[0]
    outcomes = _parse_json_field(market.get("outcomes", "[]"))
    clob_token_ids = _parse_json_field(market.get("clobTokenIds", "[]"))

    if len(clob_token_ids) < 2 or len(outcomes) < 2:
        return None

    up_idx = down_idx = -1
    for i, name in enumerate(outcomes):
        if name.lower() == "up":
            up_idx = i
        elif name.lower() == "down":
            down_idx = i
    if up_idx == -1 or down_idx == -1:
        up_idx, down_idx = 0, 1

    return {
        "symbol": symbol,
        "slug": slug,
        "up_token_id": clob_token_ids[up_idx],
        "down_token_id": clob_token_ids[down_idx],
    }


def load_all_token_ids(start_ts: int) -> dict[str, dict]:
    """
    并发查询所有 SYMBOLS 币种的 token_id（每个K线周期只需调用一次）
    ENABLED_SYMBOLS 仅用于趋势检测参考，不影响 token_id 加载范围
    """
    import concurrent.futures

    logger.info("加载全部币种 token_id: %s", SYMBOLS)

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SYMBOLS)) as executor:
        futures = {
            executor.submit(fetch_token_ids, symbol, start_ts): symbol
            for symbol in SYMBOLS
        }
        for future in concurrent.futures.as_completed(futures):
            symbol = futures[future]
            try:
                data = future.result()
                if data:
                    results[symbol] = data
            except Exception as e:
                logger.warning("获取 %s token_id 异常: %s", symbol, e)

    logger.info("Token ID 加载完成: %d/%d 个币种", len(results), len(SYMBOLS))
    return results


def fetch_realtime_prices(token_ids: dict[str, dict]) -> dict[str, dict]:
    """
    通过 CLOB POST /prices 批量获取所有币种的实时价格
    一次 POST 请求搞定所有 token，无需认证

    参数:
        token_ids: load_all_token_ids() 返回的字典

    返回:
        {symbol: {"up_price": float(0-100), "down_price": float(0-100),
                 "up_token_id": str, "down_token_id": str}}
    """
    # 构造批量请求体
    price_requests = []
    token_map = {}  # token_id -> (symbol, direction)

    for symbol, info in token_ids.items():
        for direction in ["up", "down"]:
            tid = info[f"{direction}_token_id"]
            price_requests.append({"token_id": tid, "side": "BUY"})
            token_map[tid] = (symbol, direction)

    if not price_requests:
        return {}

    # 一次 POST 获取所有价格
    try:
        resp = httpx.post(
            f"{CLOB_HOST}/prices",
            json=price_requests,
            timeout=15,
        )
        resp.raise_for_status()
        prices_data = resp.json()
    except Exception as e:
        logger.error("CLOB /prices 请求失败: %s", e)
        return {}

    # 解析结果
    raw_prices = {}  # (symbol, direction) -> float
    for tid, sides in prices_data.items():
        if tid in token_map:
            symbol, direction = token_map[tid]
            buy_price = float(sides.get("BUY", 0.5))
            raw_prices[(symbol, direction)] = buy_price

    # 组装返回结果
    results = {}
    for symbol, info in token_ids.items():
        up_raw = raw_prices.get((symbol, "up"), 0.5)
        down_raw = raw_prices.get((symbol, "down"), 0.5)
        results[symbol] = {
            "symbol": symbol,
            "up_price": round(up_raw * 100, 1),     # 0-1 → 0-100
            "down_price": round(down_raw * 100, 1),  # 0-1 → 0-100
            "up_token_id": info["up_token_id"],
            "down_token_id": info["down_token_id"],
        }

    return results
