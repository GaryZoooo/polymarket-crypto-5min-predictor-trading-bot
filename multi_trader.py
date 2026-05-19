"""
多币种下单执行器
基于信号检测结果，向目标币种的up/down市场下单
"""

import logging
from py_clob_client_v2 import (
    ClobClient, OrderArgs, OrderType, Side,
    PartialCreateOrderOptions,
)
from config import BUY_SIZE, TICK_SIZE

logger = logging.getLogger(__name__)


class MultiTrader:
    def __init__(self, client: ClobClient):
        self.client = client

    def place_order(self, signal: dict) -> dict | None:
        """
        根据信号下单

        参数:
            signal: 包含 target_token_id, direction, target_price, target_symbol

        返回:
            {"order_id": "...", "symbol": "DOGE", "direction": "up", "price": 0.99, "size": 5.0}
            或 None（下单失败时）
        """
        token_id = signal["target_token_id"]
        direction = signal["direction"]
        price = signal["target_price"]
        symbol = signal["target_symbol"]

        # 价格转为 0-1 范围（Polymarket 价格单位）
        price_decimal = round(price / 100, 2)

        # 固定数量，金额随价格浮动
        size = BUY_SIZE

        logger.info(
            "准备下单: %s %s  限价=%.2f  数量=%.1f shares",
            symbol, direction.upper(), price_decimal, size
        )

        try:
            resp = self.client.create_and_post_order(
                order_args=OrderArgs(
                    token_id=token_id,
                    price=price_decimal,
                    side=Side.BUY,
                    size=size,
                ),
                options=PartialCreateOrderOptions(tick_size=TICK_SIZE),
                order_type=OrderType.GTC,
            )
            order_id = resp.get("orderID") if isinstance(resp, dict) else None

            if order_id:
                logger.info(
                    "下单成功! order_id=%s  %s %s @%.2f x%.2f",
                    order_id, symbol, direction.upper(), price_decimal, size
                )
                return {
                    "order_id": order_id,
                    "symbol": symbol,
                    "direction": direction,
                    "price": price_decimal,
                    "size": size,
                    "token_id": token_id,
                }
            else:
                logger.warning("下单响应无 order_id: %s", resp)
                return None

        except Exception as e:
            logger.error("下单失败: %s %s  err=%s", symbol, direction.upper(), e)
            return None
