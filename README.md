# Polymarket Crypto 5-Minute Predictor Trading Bot

Automated trading bot for [Polymarket](https://polymarket.com) 5-minute cryptocurrency prediction markets. Monitors BTC, ETH, SOL, XRP, DOGE, HYPE, and BNB pairs, detects SuperTrend signals, and executes limit orders automatically.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Usage](#usage)
- [File Structure](#file-structure)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Disclaimer](#disclaimer)

## Features

- **Multi-currency support**: BTC, ETH, SOL, XRP, DOGE, HYPE, BNB
- **SuperTrend strategy**: Detects when multiple pairs show strong directional consensus
- **Automatic execution**: Places limit orders (0.99) when signals trigger
- **Timing optimization**: Scans only during last minute before candle close
- **Batch price fetching**: Single API call retrieves all prices
- **Configurable parameters**: Easily adjust thresholds, pair lists, and order sizes

## Architecture

```
                        multi_bot.py
                     (Main Entry Point)
  - Candle cycle management
  - Load token IDs
  - Signal detection loop
  - Order execution
                         |
    +---------------------+---------------------+
    |                     |                     |
    v                     v                     v
+---------+      +---------------+      +----------------+
| config  |      | multi_market  |      | signal_        |
| .py     |      | _scanner      |      | detector       |
|         |      |               |      |                |
| Config  |      | Gamma API     |      | SuperTrend     |
| params  |      | CLOB API      |      | detection      |
+---------+      +---------------+      +-------+--------+
                                                   |
                                                   v
                                          +------------+
                                          | multi_     |
                                          | trader     |
                                          |            |
                                          | CLOB Client|
                                          | Order exec |
                                          +------------+
```

### Data Flow

```
1. Gamma API ──fetch──> token_id (up/down)
                          |
                          v
2. CLOB /prices ──fetch──> Real-time prices (0-100)
                          |
                          v
3. Signal Detector ──detect──> SuperTrend signal
                          |
                          v
4. MultiTrader ──order──> Polymarket CLOB
                          |
                          v
5. Wait for settlement ──profit──> Returns
```

## Requirements

- Python 3.10+
- Polymarket account with funded wallet
- Polygon network funds (for gas)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/GaryZoooo/polymarket-crypto-5min-predictor-trading-bot.git
cd polymarket-crypto-5min-predictor-trading-bot
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp env.example .env
```

Edit `.env` with your credentials:

```env
# Required
PRIVATE_KEY=0xyour_private_key_here
FUNDER_ADDRESS=0xyour_funder_address_here

# Optional (defaults shown)
SIGNATURE_TYPE=1
CHAIN_ID=137
CLOB_HOST=https://clob.polymarket.com

# Optional: Telegram notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 5. Get Your Credentials

**PRIVATE_KEY**: Your Ethereum/Polygon wallet private key (with 0x prefix)

**FUNDER_ADDRESS**: Your Polymarket funding address. Get it from:
1. Go to [polymarket.com](https://polymarket.com)
2. Click your profile → API Keys
3. Copy the "Funder Address"

**SIGNATURE_TYPE**: 
- `1` = EOA (regular private key)
- `3` = PolyProxy

## Configuration

Edit `config.py` to customize the bot behavior:

### Trading Pairs

```python
# All supported pairs
SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "HYPE", "BNB"]

# Only detect signals on these pairs (empty = all pairs)
ENABLED_SYMBOLS = ["BTC", "ETH", "SOL"]

# Never trade these pairs
EXCLUDED_SYMBOLS = ["HYPE"]
```

### Detection Parameters

```python
# Price threshold (0-100) for SuperTrend signal
SUPER_TREND_PRICE = 70

# Minimum pairs needed to trigger signal
MIN_TRIGGER_COUNT = 3

# Candle interval (seconds)
CANDLE_MINUTES = 5
CANDLE_INTERVAL = 300
```

### Timing

```python
# Start detecting N seconds before candle close
DETECT_BEFORE_CLOSE = 298  # 5 minutes - 2 seconds

# Stop scanning N seconds before candle close
DETECT_STOP_BEFORE_CLOSE = 120  # 2 minutes before close

# Scan interval (seconds)
SCAN_INTERVAL = 2
```

### Order Parameters

```python
# Shares per order
BUY_SIZE = 3.0

# Limit order price (0.99 simulates market order)
ORDER_PRICE = 0.99

# Direction mode
ORDER_MODE = "forward"  # "forward" or "reverse"
```

### ORDER_MODE Explanation

| Mode | Trigger | Action |
|------|---------|--------|
| `forward` | UP signal | Buy cheapest UP |
| `forward` | DOWN signal | Buy cheapest DOWN |
| `reverse` | UP signal | Buy cheapest DOWN (contrarian) |
| `reverse` | DOWN signal | Buy cheapest UP (contrarian) |

## How It Works

### 1. Candle Cycle

Polymarket 5-minute prediction markets are structured as 5-minute candles. Each candle has a `start_ts` and `close_ts`.

```
|<------- 300 seconds ------>|
start_ts                    close_ts
    |<----- scan ----->|
    DETECT_BEFORE    DETECT_STOP
    _CLOSE          _BEFORE_CLOSE
```

### 2. SuperTrend Signal

The strategy detects "SuperTrend" when multiple pairs show strong directional consensus:

```
Example: 3+ pairs show UP >= 70
+---------+---------+
|  BTC    |  UP=75 |  yes
|  ETH    |  UP=72 |  yes
|  SOL    |  UP=80 |  yes
|  XRP    |  UP=45 |  
|  DOGE   |  UP=60 |  
+---------+---------+
Signal: SUPERTREND UP (3 pairs triggered)
```

### 3. Order Execution

When signal triggers, the bot:

1. Finds all available pairs for the target direction
2. Selects the cheapest one
3. Places a limit order at 0.99 (almost guaranteed fill)
4. Waits for settlement

```
Signal: SUPERTREND UP detected
Candidates for DOWN:
+---------+---------+
|  BTC    | DOWN=25 |
|  DOGE   | DOWN=22 |  <- Cheapest!
|  SOL    | DOWN=35 |
+---------+---------+
Order: BUY DOGE DOWN @ 0.99
```

## Usage

### Basic Usage

```bash
python multi_bot.py
```

### Expected Output

```
2026-05-19 10:00:00 [INFO] ============================================================
2026-05-19 10:00:00 [INFO] Multi-pair correlation trading bot started
2026-05-19 10:00:00 [INFO] Pairs: BTC/ETH/SOL/XRP/DOGE/HYPE/BNB
2026-05-19 10:00:00 [INFO] Strategy: SuperTrend
2026-05-19 10:00:00 [INFO] ============================================================
2026-05-19 10:04:30 [INFO] Detection window opened  Candle: 10:00:00 ~ 10:05:00 UTC
2026-05-19 10:04:32 [INFO] BTC: UP=52.0 DN=48.0  ETH: UP=55.0 DN=45.0  ...
2026-05-19 10:04:50 [INFO] SuperTrend triggered! Direction=UP  Pairs=['BTC', 'ETH', 'SOL']
2026-05-19 10:04:50 [INFO]   -> Order: DOGE DOWN  Price=22.0
2026-05-19 10:04:50 [INFO] Order success! order_id=xxx  DOGE DOWN @0.22 x3.0
```

### Run with Logs

```bash
# View live logs
python multi_bot.py 2>&1 | tee bot.log

# Or check log files in logs/ directory
```

### Run as Service (Linux)

Using systemd:

```ini
# /etc/systemd/system/polymarket-bot.service
[Unit]
Description=Polymarket Trading Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/bot
ExecStart=/path/to/venv/bin/python multi_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable polymarket-bot
sudo systemctl start polymarket-bot
sudo journalctl -u polymarket-bot -f
```

## File Structure

```
polymarket-bot/
├── multi_bot.py           # Main entry point
├── config.py              # Configuration parameters
├── multi_market_scanner.py # Price fetching & token lookup
├── signal_detector.py     # SuperTrend signal detection
├── multi_trader.py        # Order execution
├── requirements.txt        # Python dependencies
├── env.example            # Environment template
├── .gitignore             # Git ignore patterns
└── README.md              # This file
```

## API Reference

### Config Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `CLOB_HOST` | str | `https://clob.polymarket.com` | CLOB API endpoint |
| `GAMMA_EVENTS_API` | str | `https://gamma-api.polymarket.com/events` | Gamma API endpoint |
| `SYMBOLS` | list | `["BTC", "ETH", ...]` | All supported trading pairs |
| `SUPER_TREND_PRICE` | int | `70` | Price threshold for signal (0-100) |
| `MIN_TRIGGER_COUNT` | int | `1` | Min pairs to trigger |
| `BUY_SIZE` | float | `3.0` | Shares per order |
| `ORDER_MODE` | str | `"forward"` | Direction mode |

### Key Functions

#### `multi_market_scanner.py`

```python
get_candle_timestamps() -> tuple[int, int]
    # Returns (start_ts, close_ts) for current 5-min candle

load_all_token_ids(start_ts: int) -> dict[str, dict]
    # Loads up/down token IDs for all pairs

fetch_realtime_prices(token_ids: dict) -> dict[str, dict]
    # Returns {symbol: {up_price, down_price, up_token_id, down_token_id}}
```

#### `signal_detector.py`

```python
detect_signal(markets: dict, ordered_symbols: set = None) -> list[dict]
    # Returns list of signals when SuperTrend triggers
    # Each signal: {direction, target_symbol, target_price, target_token_id}
```

#### `multi_trader.py`

```python
class MultiTrader:
    def place_order(self, signal: dict) -> dict | None
        # Executes order based on signal
        # Returns order result or None on failure
```

## Troubleshooting

### "Query X market failed"

**Problem**: Gamma API failed to fetch token IDs

**Solution**: 
- Check your internet connection
- Verify the market exists on Polymarket
- Markets may have expired if candle is old

### "Order failed"

**Problem**: Order creation failed

**Solutions**:
- Check if wallet has sufficient funds
- Verify PRIVATE_KEY is correct
- Ensure FUNDER_ADDRESS is valid
- Check gas balance on Polygon

### "No signals triggered"

**Problem**: No signals detected

**Solutions**:
- Check if SUPER_TREND_PRICE is set too high
- Verify ENABLED_SYMBOLS includes active pairs
- Markets may not have reached threshold yet

### "L2 API credentials obtained" but orders still fail

**Problem**: API key issue

**Solution**:
```python
# In .env, try changing SIGNATURE_TYPE
SIGNATURE_TYPE=1  # EOA
# or
SIGNATURE_TYPE=3  # PolyProxy
```

### Rate Limiting

If you see rate limit errors:

```python
# In config.py, increase scan interval
SCAN_INTERVAL = 5  # Increase from 2 to 5 seconds
```

## Disclaimer

WARNING: IMPORTANT - READ CAREFULLY

This bot trades real assets on Polymarket with your funds. Cryptocurrency and prediction market trading involves substantial risk of loss.

- Past performance does not guarantee future results
- The SuperTrend strategy may lose money in sideways or choppy markets
- API changes or market structure modifications may break this bot
- Always monitor your positions and account balance

You are solely responsible for any losses incurred. This software is provided "as is" for educational and informational purposes only. The authors and contributors accept no liability for financial losses or damages arising from the use of this software.

Always test on small amounts first.

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

- Open an issue on GitHub
- Check [Polymarket API docs](https://docs.polymarket.com)
- Review [CLOB Client documentation](https://github.com/polymarket/py-clob-client)
