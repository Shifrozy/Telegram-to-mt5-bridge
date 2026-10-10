import sys
import io
import logging
import argparse

# Fix Windows console UTF-8 encoding for emojis
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

from src.config import BridgeConfig
from src.mt5_engine import MT5Engine
from src.telegram_listener import TelegramBridgeBot
from src.parser import SignalParser


def setup_logging(level_name: str = "INFO"):
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=level,
    )


def run_status_check(config: BridgeConfig):
    print("=" * 55)
    print("       TELEGRAM TO MT5 BRIDGE - STATUS CHECK")
    print("=" * 55)
    print(f"Dry Run Mode:        {'ENABLED (Simulation)' if config.dry_run else 'DISABLED (Live)'}")
    print(f"Default Lot Size:    {config.default_lot_size}")
    print(f"Magic Number:        {config.magic_number}")
    print(f"Allowed User IDs:    {config.allowed_users if config.allowed_users else 'Any (No restriction)'}")
    print("-" * 55)

    engine = MT5Engine(config)
    if not engine.initialize():
        print("❌ MT5 Status: Failed to connect to MetaTrader 5 terminal.")
        print("   Make sure MT5 is open or verify your MT5_* settings in .env.")
        return

    summary = engine.get_account_summary()
    print("✅ MT5 Status: Connected successfully!")
    print(f"   Account:          {summary.get('login')}")
    print(f"   Server:           {summary.get('server')}")
    print(f"   Balance:          {summary.get('balance'):.2f} {summary.get('currency')}")
    print(f"   Equity:           {summary.get('equity'):.2f} {summary.get('currency')}")
    print(f"   Free Margin:      {summary.get('margin_free'):.2f} {summary.get('currency')}")
    print(f"   Trade Allowed:    {summary.get('trade_allowed')}")
    print("=" * 55)
    engine.shutdown()


def test_parser_interactive():
    parser = SignalParser(default_volume=0.01)
    print("=" * 55)
    print("       SIGNAL PARSER TEST CONSOLE")
    print("       (Type 'exit' to quit)")
    print("=" * 55)
    examples = [
        "BUY EURUSD\nSL: 1.0820\nTP: 1.0920",
        "SELL GOLD @ 2650.00 SL 2665.00 TP 2620.00",
        "BUY GBPUSD 0.05 SL: 1.2950 TP1: 1.3050 TP2: 1.3100",
        "CLOSE ALL",
    ]
    print("\nRunning sample tests:")
    for ex in examples:
        sig = parser.parse(ex)
        print(f"\nInput:\n{ex}\nParsed: {sig}")

    print("\nEnter custom signals to test:")
    while True:
        try:
            line = input("\nSignal > ")
            if line.strip().lower() in ("exit", "quit"):
                break
            sig = parser.parse(line)
            if sig:
                print(f"✅ Parsed: {sig}")
            else:
                print("❌ Not recognized as a trade signal.")
        except (KeyboardInterrupt, EOFError):
            break


def main():
    parser = argparse.ArgumentParser(description="Telegram to MT5 Automated Trading Bridge")
    parser.add_argument("--status", action="store_true", help="Check MT5 connection and account info")
    parser.add_argument("--test-parser", action="store_true", help="Run interactive signal parser test")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run simulation mode")

    args = parser.parse_args()

    config = BridgeConfig.from_env()
    if args.dry_run:
        config.dry_run = True

    setup_logging(config.log_level)
    logger = logging.getLogger("BridgeMain")

    if args.status:
        run_status_check(config)
        return

    if args.test_parser:
        test_parser_interactive()
        return

    # Check Telegram token
    if not config.telegram_bot_token or config.telegram_bot_token == "your_telegram_bot_token_here":
        logger.error(
            "\n" + "!" * 65 + "\n"
            "TELEGRAM_BOT_TOKEN is missing or not configured!\n"
            "1. Copy .env.example to .env\n"
            "2. Create a bot with @BotFather on Telegram and get the bot token\n"
            "3. Paste the token into .env: TELEGRAM_BOT_TOKEN=123456:ABC-DEF...\n"
            "4. Run: python main.py\n\n"
            "To test MT5 connection only: python main.py --status\n"
            "To test signal parser:       python main.py --test-parser\n"
            + "!" * 65
        )
        sys.exit(1)

    engine = MT5Engine(config)
    if not config.dry_run:
        if not engine.initialize():
            logger.warning("MT5 could not be initialized at startup. Will retry on orders.")
        else:
            logger.info("MT5 Engine ready.")

    bridge = TelegramBridgeBot(config, engine)
    app = bridge.build_application()

    logger.info("Starting Telegram Bot listener... (Press Ctrl+C to stop)")
    try:
        app.run_polling()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down bridge...")
    finally:
        engine.shutdown()


if __name__ == "__main__":
    main()
