# Telegram to MT5 Bridge 🚀

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![MetaTrader 5](https://img.shields.io/badge/MetaTrader-5-green.svg)](https://www.metatrader5.com/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-2CA5E0.svg?logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A lightweight, modular, and reliable bridge that automatically captures trading signals from Telegram (private chat, trading groups, or VIP channels) and executes them directly on **MetaTrader 5 (MT5)**.

Designed for seamless testing and production scalability, featuring smart broker symbol resolution, intelligent filling-mode handling, configurable risk controls, and interactive bot management commands.

---

## 📌 Key Features

- ⚡ **Instant Order Execution**: Market orders (`BUY`, `SELL`) executed with minimal latency.
- 🎯 **Pending Orders Supported**: Supports `BUY LIMIT`, `SELL LIMIT`, `BUY STOP`, and `SELL STOP`.
- 🔍 **Intelligent Broker Symbol Resolver**: Automatically detects broker suffix conventions (e.g., converts `EURUSD` to `EURUSDm` or `EURUSD.pro` seamlessly).
- 🏷️ **Asset & Commodity Aliases**: Automatically maps `GOLD` ➔ `XAUUSD`, `SILVER` ➔ `XAGUSD`, `US30` ➔ `DJ30`/`US30`, and cryptos like `BTC` ➔ `BTCUSD`.
- ⚙️ **Dynamic Filling Mode Detection**: Automatically handles `IOC`, `FOK`, and `RETURN` modes according to broker symbol specification to eliminate rejection error `10030`.
- 🛡️ **User Whitelisting & Security**: Restrict signal execution to authorized Telegram user IDs or channel IDs.
- 🧪 **Dry-Run / Simulation Mode**: Test signal parsing and bridge logic safely without risking real capital.
- 🤖 **Interactive Telegram Commands**: Check real-time balance, view open positions, close positions, and trigger emergency close-all commands directly from Telegram.

---

## 🏗️ Architecture Flow

```text
┌──────────────────────────┐
│   Telegram Signal Source │
│ (Private Chat / Channel) │
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│    Telegram Bot Listener │
│  (python-telegram-bot)   │
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│   Signal Parser Engine   │ ◄─── Extracts Action, Symbol, Lot, Entry, SL, TPs
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│  Broker Symbol Resolver  │ ◄─── Maps Aliases & Suffixes (e.g. EURUSD -> EURUSDm)
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│        MT5 Engine        │ ◄─── Sets Filling Mode, Lot Size, Deviation & Magic No.
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│  MetaTrader 5 Terminal   │ ───► Executes Order on Broker Server
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│ Execution Feedback Reply │ ───► Sends Ticket #, Price, SL/TP Confirmation to Telegram
└──────────────────────────┘
```

---

## 📋 Supported Signal Formats

The built-in parser supports diverse real-world signal formats, with or without emojis:

### 1. Standard Structured Signals
```text
BUY EURUSD
SL: 1.0820
TP: 1.0920
```

### 2. Gold & Commodities with Price
```text
SELL GOLD @ 2650.00
SL: 2665.00
TP: 2620.00
```

### 3. Custom Lot Size & Multiple Take Profits
```text
🚀 BUY GBPUSD 0.05
SL: 1.2950
TP1: 1.3050
TP2: 1.3100
TP3: 1.3150
```

### 4. Pending Limit & Stop Orders
```text
BUY LIMIT EURUSD 1.0800 SL 1.0750 TP 1.0900
SELL STOP XAUUSD 2630 SL 2645 TP 2600
```

### 5. Position Management Commands
```text
CLOSE EURUSD
CLOSE ALL
```

---

## 💻 System Requirements

- **Operating System**: Windows 10 / 11 / Windows Server
- **Python**: Version 3.10 or higher
- **MetaTrader 5**: Desktop terminal installed and running

---

## 🚀 Quick Start Guide

### 1. Clone the Repository
```bash
git clone https://github.com/Shifrozy/Telegram-to-mt5-bridge.git
cd Telegram-to-mt5-bridge
```

### 2. Create Virtual Environment & Install Dependencies
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create a Telegram Bot
1. Open Telegram and search for [@BotFather](https://t.me/botfather).
2. Send `/newbot` and follow instructions to get your **Bot API Token**.
3. (Optional) Message [@userinfobot](https://t.me/userinfobot) to get your numerical Telegram User ID for whitelisting.

### 4. Configure Environment Variables
Copy the `.env.example` file to `.env`:
```bash
copy .env.example .env
```
Edit `.env` with your preferred text editor:
```ini
# Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRstuVWXyz

# Your Telegram User ID (Leave blank to allow any sender during testing)
TELEGRAM_ALLOWED_USERS=123456789

# Default lot size when not specified in signal
DEFAULT_LOT_SIZE=0.01

# Auto-detect broker suffixes (e.g. 'm' on Exness)
AUTO_DETECT_SUFFIX=True

# Set to True for safe simulation mode
DRY_RUN=False
```

### 5. Enable Algo Trading in MetaTrader 5
In your MetaTrader 5 terminal:
1. Go to **Tools** ➔ **Options** (or press `Ctrl+O`).
2. Select the **Expert Advisors** tab.
3. Check **"Allow Algo Trading"**.
4. Check **"Allow DLL imports"**.
5. Click **OK**.
6. Ensure the **Algo Trading** button on the top toolbar is green.

### 6. Verify MT5 Connection
Before launching the Telegram bot, run the status diagnostic tool:
```bash
python main.py --status
```
You should see:
```text
=======================================================
       TELEGRAM TO MT5 BRIDGE - STATUS CHECK
=======================================================
✅ MT5 Status: Connected successfully!
   Account:          472380743
   Server:           Exness-MT5Trial16
   Balance:          241.75 USD
   Trade Allowed:    True
=======================================================
```

### 7. Run the Bridge
```bash
python main.py
```

Send `/start` to your Telegram bot to test the connection!

---

## 🤖 Telegram Bot Commands

| Command | Description |
| :--- | :--- |
| `/start` | Initializes chat and displays user ID and bridge status |
| `/status` | Fetches live MT5 account balance, equity, margin & server details |
| `/positions` | Lists all currently open trades with ticket #, SL, TP, and floating P&L |
| `/closeall` | Emergency command: Closes all open positions across all symbols |
| `/test` | Executes a safe simulated test signal in dry-run mode |
| `/help` | Displays signal formatting documentation and examples |

---

## 🧪 Testing & Verification

Run the automated test suite with pytest:
```bash
pytest -v
```

Test signal parsing interactively from your terminal:
```bash
python main.py --test-parser
```

Run the bridge in safe simulation mode (no real trades placed):
```bash
python main.py --dry-run
```

---

## 📁 Project Structure

```text
Telegram-to-mt5-bridge/
├── .env.example              # Template configuration file
├── .gitignore                # Git ignore rules
├── LICENSE                   # MIT License
├── README.md                 # Project documentation
├── requirements.txt          # Python dependencies
├── main.py                   # Main entry point & diagnostic CLI
├── src/
│   ├── __init__.py
│   ├── config.py             # Configuration loader & validation
│   ├── models.py             # Data classes (TradeSignal, ExecutionResult, etc.)
│   ├── parser.py             # Signal parsing engine with regex & heuristics
│   ├── mt5_engine.py         # MT5 terminal connection & order execution manager
│   └── telegram_listener.py  # Telegram bot handlers & command routers
└── tests/
    ├── __init__.py
    ├── test_parser.py        # Signal parsing unit tests
    └── test_mt5_engine.py    # MT5 execution & simulation unit tests
```

---

## ⚠️ Risk Disclaimer

Trading foreign exchange, commodities, cryptocurrencies, and CFDs on margin carries a high level of risk and may not be suitable for all investors. Test this bridge thoroughly on a **Demo / Paper trading account** before using real funds. The authors and contributors assume no liability for financial losses incurred through the use of this software.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.