import asyncio
import logging
from typing import Optional
from telegram import Update
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from src.config import BridgeConfig
from src.parser import SignalParser
from src.mt5_engine import MT5Engine
from src.models import ExecutionResult, TradeSignal

logger = logging.getLogger(__name__)


class TelegramBridgeBot:
    """Manages Telegram Bot interactions and connects messages to the MT5 Engine."""

    def __init__(self, config: BridgeConfig, engine: MT5Engine):
        self.config = config
        self.engine = engine
        self.parser = SignalParser(default_volume=config.default_lot_size)
        self.app: Optional[Application] = None

    async def _safe_reply(self, message, text: str, **kwargs):
        """Replies to a message with automatic retry on timeout/network error."""
        if not message:
            return None
        for attempt in range(1, 4):
            try:
                return await message.reply_text(text, **kwargs)
            except Exception as e:
                logger.warning(f"Telegram reply error (attempt {attempt}/3): {e}")
                if attempt < 3:
                    await asyncio.sleep(2)
                else:
                    logger.error(f"Failed to send Telegram message after 3 attempts.")
                    return None

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Log errors caused by updates and network timeouts gracefully."""
        logger.error(f"Telegram handler error: {context.error}")

    def build_application(self) -> Application:
        """Configures and builds the telegram Application with resilient timeouts and proxy support."""
        if not self.config.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment or .env file.")

        request_kwargs = {
            "connection_pool_size": 8,
            "connect_timeout": 60.0,
            "read_timeout": 60.0,
            "write_timeout": 60.0,
            "pool_timeout": 60.0,
        }
        if self.config.telegram_proxy:
            request_kwargs["proxy"] = self.config.telegram_proxy
            logger.info(f"Using Telegram proxy: {self.config.telegram_proxy}")

        request = HTTPXRequest(**request_kwargs)
        get_updates_request = HTTPXRequest(**request_kwargs)

        app = (
            ApplicationBuilder()
            .token(self.config.telegram_bot_token)
            .request(request)
            .get_updates_request(get_updates_request)
            .build()
        )

        app.add_error_handler(self._error_handler)

        # Command handlers
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(CommandHandler("positions", self._cmd_positions))
        app.add_handler(CommandHandler("closeall", self._cmd_closeall))
        app.add_handler(CommandHandler("test", self._cmd_test))

        # Message handlers: regular messages and channel posts
        signal_filter = filters.TEXT & (~filters.COMMAND)
        app.add_handler(MessageHandler(signal_filter, self._handle_message))

        self.app = app
        return app

    def _is_authorized(self, update: Update) -> bool:
        """Verifies if the sender is authorized."""
        user = update.effective_user
        if not user:
            # Channel posts may not have effective_user
            chat = update.effective_chat
            if chat and chat.id:
                return self.config.is_user_allowed(chat.id)
            return True
        return self.config.is_user_allowed(user.id)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start command."""
        user = update.effective_user
        user_id = user.id if user else update.effective_chat.id
        status_text = "🟢 Dry-Run Mode (Simulation)" if self.config.dry_run else "⚡ Live Execution Mode"

        welcome_msg = (
            f"👋 *Welcome to Telegram-to-MT5 Bridge!*\n\n"
            f"Your Telegram ID: `{user_id}`\n"
            f"Bridge Status: {status_text}\n\n"
            f"*Available Commands:*\n"
            f"• `/status` - Check MT5 connection & account balance\n"
            f"• `/positions` - View current open positions\n"
            f"• `/closeall` - Emergency close all open positions\n"
            f"• `/test` - Simulate a test signal\n"
            f"• `/help` - Signal formatting guide\n\n"
            f"Simply send or forward trading signals to this chat or add this bot to your signal channel."
        )
        await self._safe_reply(update.effective_message, welcome_msg, parse_mode="Markdown")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /help command."""
        help_msg = (
            "📖 *Supported Signal Formats:*\n\n"
            "*1. Standard Multi-line:*\n"
            "```\nBUY EURUSD\nSL: 1.0820\nTP: 1.0920\n```\n\n"
            "*2. One-Liner with Entry:*\n"
            "```\nSELL GOLD @ 2650.00 SL 2665.00 TP 2620.00\n```\n\n"
            "*3. Custom Lot Size:*\n"
            "```\nBUY GBPUSD 0.05\nSL: 1.2950\nTP: 1.3050\n```\n\n"
            "*4. Pending Orders:*\n"
            "```\nBUY LIMIT EURUSD 1.0800 SL 1.0750 TP 1.0900\nSELL STOP XAUUSD 2630 SL 2645 TP 2600\n```\n\n"
            "*5. Close Commands:*\n"
            "```\nCLOSE EURUSD\nCLOSE ALL\n```\n\n"
            "Aliases like `GOLD` (XAUUSD), `SILVER` (XAGUSD), and `US30` are supported automatically."
        )
        await self._safe_reply(update.effective_message, help_msg, parse_mode="Markdown")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /status command."""
        if not self._is_authorized(update):
            await self._safe_reply(update.effective_message, "⛔ Unauthorized. Your ID is not in `TELEGRAM_ALLOWED_USERS`.")
            return

        summary = self.engine.get_account_summary()
        if "error" in summary:
            await self._safe_reply(update.effective_message, f"❌ *MT5 Connection Error:*\n{summary['error']}", parse_mode="Markdown")
            return

        status_msg = (
            f"📊 *MT5 Account Status:*\n\n"
            f"• *Login:* `{summary['login']}`\n"
            f"• *Server:* {summary['server']}\n"
            f"• *Balance:* `{summary['balance']:.2f} {summary['currency']}`\n"
            f"• *Equity:* `{summary['equity']:.2f} {summary['currency']}`\n"
            f"• *Free Margin:* `{summary['margin_free']:.2f} {summary['currency']}`\n"
            f"• *Floating Profit:* `{summary['profit']:.2f} {summary['currency']}`\n"
            f"• *Leverage:* `1:{summary['leverage']}`\n"
            f"• *Trade Allowed:* {'✅ Yes' if summary['trade_allowed'] else '❌ No'}\n"
            f"• *Dry-Run Mode:* {'🟢 Active' if self.config.dry_run else '🔴 Live Trading'}"
        )
        await self._safe_reply(update.effective_message, status_msg, parse_mode="Markdown")

    async def _cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /positions command."""
        if not self._is_authorized(update):
            await self._safe_reply(update.effective_message, "⛔ Unauthorized.")
            return

        positions = self.engine.get_open_positions()
        if not positions:
            await self._safe_reply(update.effective_message, "ℹ️ No open positions on MT5.")
            return

        msg = f"📋 *Open Positions ({len(positions)}):*\n\n"
        for p in positions:
            pnl_emoji = "🟢" if p["profit"] >= 0 else "🔴"
            msg += (
                f"{pnl_emoji} *#{p['ticket']}* | {p['type']} *{p['symbol']}* ({p['volume']} lots)\n"
                f"  Open: `{p['open_price']}` | Curr: `{p['current_price']}`\n"
                f"  SL: `{p['sl']}` | TP: `{p['tp']}`\n"
                f"  Profit: *{p['profit']:.2f}*\n\n"
            )
        await self._safe_reply(update.effective_message, msg, parse_mode="Markdown")

    async def _cmd_closeall(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /closeall command."""
        if not self._is_authorized(update):
            await self._safe_reply(update.effective_message, "⛔ Unauthorized.")
            return

        await self._safe_reply(update.effective_message, "⏳ Closing all positions...")
        res = self.engine.close_all_positions()
        if res.success:
            await self._safe_reply(update.effective_message, f"✅ *Success:* {res.comment}", parse_mode="Markdown")
        else:
            await self._safe_reply(update.effective_message, f"❌ *Failed to close:* {res.comment}", parse_mode="Markdown")

    async def _cmd_test(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Simulates a test signal."""
        test_msg = "BUY EURUSD\nSL: 1.0800\nTP: 1.0900"
        signal = self.parser.parse(test_msg)
        if not signal:
            await self._safe_reply(update.effective_message, "Failed to create test signal.")
            return

        # Force dry run for test command
        prev_dry = self.config.dry_run
        self.config.dry_run = True
        try:
            res = self.engine.execute_signal(signal)
            reply = self._format_execution_response(signal, res)
            await self._safe_reply(update.effective_message, f"🧪 *Test Execution Result:*\n\n{reply}", parse_mode="Markdown")
        finally:
            self.config.dry_run = prev_dry

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes incoming text messages for trading signals."""
        msg = update.effective_message
        if not msg or not msg.text:
            return

        if not self._is_authorized(update):
            logger.warning(f"Ignored message from unauthorized sender: {update.effective_user.id if update.effective_user else 'unknown'}")
            return

        text = msg.text.strip()
        signal = self.parser.parse(text)
        if not signal:
            # Not a trading signal - ignore silently so we don't spam regular conversations
            return

        logger.info(f"Signal detected: {signal.action.value} {signal.symbol} (Vol: {signal.volume})")
        res = self.engine.execute_signal(signal)
        reply = self._format_execution_response(signal, res)
        await self._safe_reply(msg, reply, parse_mode="Markdown")

    def _format_execution_response(self, signal: TradeSignal, res: ExecutionResult) -> str:
        """Formats the execution result into a clear Telegram message."""
        if res.success:
            mode_tag = " _[DRY RUN]_" if res.dry_run else ""
            lines = [
                f"✅ *Trade Executed successfully!*{mode_tag}",
                f"• *Action:* `{res.action} {res.symbol}`",
                f"• *Ticket:* `#{res.order_ticket}`",
                f"• *Volume:* `{res.volume:.2f} lots`",
                f"• *Price:* `{res.price}`",
            ]
            if res.sl:
                lines.append(f"• *Stop Loss:* `{res.sl}`")
            if res.tp:
                lines.append(f"• *Take Profit:* `{res.tp}`")
            if res.comment:
                lines.append(f"• *Note:* {res.comment}")
            return "\n".join(lines)
        else:
            return (
                f"❌ *Trade Execution Failed!*\n"
                f"• *Action:* `{signal.action.value} {signal.symbol}`\n"
                f"• *Reason:* {res.error_message or 'Unknown MT5 error'}"
            )
