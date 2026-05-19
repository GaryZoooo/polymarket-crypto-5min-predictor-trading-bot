# Polymarket Crypto 5-Minute Predictor Trading Bot

Automated trading bot for Polymarket 5-minute prediction markets. Monitors multiple crypto pairs (BTC, ETH, SOL, XRP, DOGE, HYPE, BNB) and executes trades based on a **SuperTrend** strategy.

## Strategy

- **SuperTrend Signal**: When ≥N crypto pairs have the same direction (UP or DOWN) priced at ≥70, a signal triggers
- **Execution**: Buy the cheapest UP or DOWN option from all pairs using a limit order (price=0.99)
- **Timing**: Scans during the last 1 minute before each 5-minute candle closes

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your PRIVATE_KEY and FUNDER_ADDRESS
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `PRIVATE_KEY` | Your wallet private key |
| `FUNDER_ADDRESS` | Your Polymarket funder address |
| `SIGNATURE_TYPE` | Signature type (default: 1) |
| `CHAIN_ID` | Chain ID (default: 137 for Polygon) |

## Configuration

Edit `config.py` to customize:

```python
SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "HYPE", "BNB"]  # Trading pairs
SUPER_TREND_PRICE = 70       # Price threshold (0-100)
MIN_TRIGGER_COUNT = 1        # Minimum pairs to trigger signal
BUY_SIZE = 3.0               # Order size in shares
ORDER_MODE = "forward"        # "forward" or "reverse"
```

## Usage

```bash
python multi_bot.py
```

## Disclaimer

⚠️ **HIGH RISK**: This bot trades real assets on Polymarket. Cryptocurrency trading involves substantial risk of loss. This software is for educational purposes only. Use at your own risk.

## License

MIT
