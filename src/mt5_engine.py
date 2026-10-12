import logging
from typing import Optional, List, Dict, Any
import MetaTrader5 as mt5

from src.config import BridgeConfig
from src.models import TradeSignal, OrderAction, ExecutionResult

logger = logging.getLogger(__name__)

# Common MT5 Return Codes Mapping
RETCODE_DESCRIPTIONS: Dict[int, str] = {
    getattr(mt5, "TRADE_RETCODE_DONE", 10009): "Order placed successfully (Done)",
    getattr(mt5, "TRADE_RETCODE_PLACED", 10008): "Order placed in queue",
    getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010): "Order partially executed",
    getattr(mt5, "TRADE_RETCODE_NO_MONEY", 10019): "Not enough money to complete the request",
    getattr(mt5, "TRADE_RETCODE_PRICE_CHANGED", 10004): "Price changed / Requote",
    getattr(mt5, "TRADE_RETCODE_PRICE_OFF", 10005): "No prices for symbol",
    getattr(mt5, "TRADE_RETCODE_INVALID_PRICE", 10015): "Invalid order price",
    getattr(mt5, "TRADE_RETCODE_INVALID_STOPS", 10016): "Invalid stops (SL or TP too close or misplaced)",
    getattr(mt5, "TRADE_RETCODE_INVALID_VOLUME", 10014): "Invalid order volume / lot size",
    getattr(mt5, "TRADE_RETCODE_MARKET_CLOSED", 10018): "Market is closed",
    getattr(mt5, "TRADE_RETCODE_TRADE_DISABLED", 10017): "Trading is disabled on account",
    getattr(mt5, "TRADE_RETCODE_CONNECTION", 10031): "No connection with trade server",
    getattr(mt5, "TRADE_RETCODE_TOO_MANY_REQUESTS", 10024): "Too many trade requests",
    getattr(mt5, "TRADE_RETCODE_INVALID_FILL", 10030): "Unsupported order filling type",
}


class MT5Engine:
    """Manages connection, symbol resolution, and order execution on MetaTrader 5."""

    def __init__(self, config: BridgeConfig):
        self.config = config
        self._is_initialized = False
        self._symbol_cache: Dict[str, str] = {}

    def initialize(self) -> bool:
        """Initializes connection to MT5 terminal."""
        if self._is_initialized and mt5.terminal_info() is not None:
            return True

        init_kwargs = {}
        if self.config.mt5_path:
            init_kwargs["path"] = self.config.mt5_path
        if self.config.mt5_login:
            init_kwargs["login"] = self.config.mt5_login
        if self.config.mt5_password:
            init_kwargs["password"] = self.config.mt5_password
        if self.config.mt5_server:
            init_kwargs["server"] = self.config.mt5_server

        logger.info("Initializing MetaTrader 5...")
        if init_kwargs:
            initialized = mt5.initialize(**init_kwargs)
        else:
            initialized = mt5.initialize()

        if not initialized:
            error = mt5.last_error()
            logger.error(f"MT5 initialization failed: {error}")
            self._is_initialized = False
            return False

        # If specific login was requested and terminal was open on another account
        if self.config.mt5_login:
            current_acc = mt5.account_info()
            if not current_acc or current_acc.login != self.config.mt5_login:
                login_kwargs = {"login": self.config.mt5_login}
                if self.config.mt5_password:
                    login_kwargs["password"] = self.config.mt5_password
                if self.config.mt5_server:
                    login_kwargs["server"] = self.config.mt5_server
                logger.info(f"Logging in / switching to MT5 account {self.config.mt5_login}...")
                if not mt5.login(**login_kwargs):
                    error = mt5.last_error()
                    logger.error(f"MT5 login to {self.config.mt5_login} failed: {error}")
                    self._is_initialized = False
                    return False

        self._is_initialized = True
        acc_info = mt5.account_info()
        if acc_info:
            logger.info(
                f"MT5 Connected: Login={acc_info.login}, Server={acc_info.server}, "
                f"Balance={acc_info.balance} {acc_info.currency}"
            )
        else:
            logger.warning("MT5 initialized, but no account info returned.")
        return True

    def shutdown(self):
        """Disconnects from MT5 terminal."""
        if self._is_initialized:
            mt5.shutdown()
            self._is_initialized = False
            logger.info("MT5 disconnected.")

    def is_connected(self) -> bool:
        """Checks if terminal is initialized and connected."""
        if not self._is_initialized:
            return False
        term = mt5.terminal_info()
        return term is not None and term.connected

    def get_account_summary(self) -> Dict[str, Any]:
        """Returns account balance, equity, profit, and leverage."""
        if not self.initialize():
            return {"error": "Failed to connect to MT5"}

        acc = mt5.account_info()
        if not acc:
            return {"error": "Account info not available"}

        return {
            "login": acc.login,
            "server": acc.server,
            "currency": acc.currency,
            "balance": acc.balance,
            "equity": acc.equity,
            "margin": acc.margin,
            "margin_free": acc.margin_free,
            "profit": acc.profit,
            "leverage": acc.leverage,
            "trade_allowed": acc.trade_allowed,
        }

    def resolve_symbol(self, raw_symbol: str) -> Optional[str]:
        """
        Finds the exact broker symbol name, handling broker-specific suffixes
        (e.g., EURUSD -> EURUSDm or EURUSD.pro).
        """
        raw_symbol = raw_symbol.strip().upper()
        if raw_symbol in self._symbol_cache:
            return self._symbol_cache[raw_symbol]

        # 1. Check exact match
        s_info = mt5.symbol_info(raw_symbol)
        if s_info:
            self._symbol_cache[raw_symbol] = raw_symbol
            return raw_symbol

        # 2. Check with configured suffix
        if self.config.symbol_suffix:
            candidate = f"{raw_symbol}{self.config.symbol_suffix}"
            if mt5.symbol_info(candidate):
                self._symbol_cache[raw_symbol] = candidate
                return candidate

        # 3. Auto-detect suffix by scanning available symbols
        if self.config.auto_detect_suffix:
            all_symbols = mt5.symbols_get()
            if all_symbols:
                for s in all_symbols:
                    name = s.name.upper()
                    # Match base e.g. EURUSD in EURUSDm or EURUSD.raw
                    if name.startswith(raw_symbol) and len(name) <= len(raw_symbol) + 5:
                        self._symbol_cache[raw_symbol] = s.name
                        logger.info(f"Resolved symbol '{raw_symbol}' to broker symbol '{s.name}'")
                        return s.name

        return None

    def _determine_filling_type(self, symbol: str) -> int:
        """Determines supported order filling mode for the symbol."""
        info = mt5.symbol_info(symbol)
        if not info:
            return mt5.ORDER_FILLING_IOC

        filling_mode = info.filling_mode
        # Bit 1 (value 2): IOC
        if filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        # Bit 0 (value 1): FOK
        elif filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
        # Bit 2 (value 4): RETURN
        return mt5.ORDER_FILLING_RETURN

    def execute_signal(self, signal: TradeSignal) -> ExecutionResult:
        """Executes a TradeSignal on MT5 or simulates in dry-run mode."""
        # Check Dry Run
        if self.config.dry_run:
            logger.info(f"[DRY RUN] Simulating execution of signal: {signal}")
            return ExecutionResult(
                success=True,
                symbol=signal.symbol,
                action=signal.action.value,
                volume=signal.volume or self.config.default_lot_size,
                price=signal.price or 1.0000,
                sl=signal.sl,
                tp=signal.tp,
                order_ticket=99999999,
                retcode=mt5.TRADE_RETCODE_DONE,
                error_message="Simulated in Dry-Run mode",
                dry_run=True,
                comment=signal.comment,
            )

        if not self.initialize():
            return ExecutionResult(
                success=False,
                symbol=signal.symbol,
                action=signal.action.value,
                error_message="MT5 connection failed",
            )

        # Handle Close actions
        if signal.action == OrderAction.CLOSE_ALL:
            return self.close_all_positions()
        elif signal.action == OrderAction.CLOSE:
            resolved_symbol = self.resolve_symbol(signal.symbol)
            if not resolved_symbol:
                return ExecutionResult(
                    success=False,
                    symbol=signal.symbol,
                    action="CLOSE",
                    error_message=f"Symbol '{signal.symbol}' not found on broker",
                )
            return self.close_positions_for_symbol(resolved_symbol)

        # Resolve symbol
        symbol = self.resolve_symbol(signal.symbol)
        if not symbol:
            return ExecutionResult(
                success=False,
                symbol=signal.symbol,
                action=signal.action.value,
                error_message=f"Broker does not support symbol '{signal.symbol}'",
            )

        # Enable in Market Watch
        if not mt5.symbol_select(symbol, True):
            return ExecutionResult(
                success=False,
                symbol=symbol,
                action=signal.action.value,
                error_message=f"Failed to select symbol '{symbol}' in Market Watch",
            )

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return ExecutionResult(
                success=False,
                symbol=symbol,
                action=signal.action.value,
                error_message=f"Failed to get price tick for '{symbol}'",
            )

        # Determine price, order type, and action
        volume = signal.volume or self.config.default_lot_size
        type_filling = self._determine_filling_type(symbol)

        if signal.action == OrderAction.BUY:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        elif signal.action == OrderAction.SELL:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        elif signal.action == OrderAction.BUY_LIMIT:
            order_type = mt5.ORDER_TYPE_BUY_LIMIT
            price = signal.price or tick.ask
        elif signal.action == OrderAction.SELL_LIMIT:
            order_type = mt5.ORDER_TYPE_SELL_LIMIT
            price = signal.price or tick.bid
        elif signal.action == OrderAction.BUY_STOP:
            order_type = mt5.ORDER_TYPE_BUY_STOP
            price = signal.price or tick.ask
        elif signal.action == OrderAction.SELL_STOP:
            order_type = mt5.ORDER_TYPE_SELL_STOP
            price = signal.price or tick.bid
        else:
            return ExecutionResult(
                success=False,
                symbol=symbol,
                action=signal.action.value,
                error_message=f"Unsupported action: {signal.action}",
            )

        request = {
            "action": mt5.TRADE_ACTION_DEAL if "LIMIT" not in signal.action.value and "STOP" not in signal.action.value else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "deviation": int(self.config.default_deviation),
            "magic": int(self.config.magic_number),
            "comment": signal.comment or "TG-Bridge",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": type_filling,
        }

        if signal.sl:
            request["sl"] = float(signal.sl)
        if signal.tp:
            request["tp"] = float(signal.tp)

        logger.info(f"Sending MT5 order request: {request}")
        result = mt5.order_send(request)

        if result is None:
            error = mt5.last_error()
            return ExecutionResult(
                success=False,
                symbol=symbol,
                action=signal.action.value,
                error_message=f"order_send failed: {error}",
            )

        desc = RETCODE_DESCRIPTIONS.get(result.retcode, f"Code: {result.retcode}")
        success = result.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED)

        return ExecutionResult(
            success=success,
            symbol=symbol,
            action=signal.action.value,
            volume=volume,
            price=result.price or price,
            sl=signal.sl,
            tp=signal.tp,
            order_ticket=result.order,
            retcode=result.retcode,
            error_message=None if success else f"{desc} ({result.comment})",
            dry_run=False,
            comment=result.comment,
        )

    def close_positions_for_symbol(self, symbol: str) -> ExecutionResult:
        """Closes all open positions for a given symbol."""
        positions = mt5.positions_get(symbol=symbol)
        if positions is None or len(positions) == 0:
            return ExecutionResult(
                success=True,
                symbol=symbol,
                action="CLOSE",
                comment=f"No open positions found for {symbol}",
            )

        closed_count = 0
        for pos in positions:
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                continue

            close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": symbol,
                "volume": pos.volume,
                "type": close_type,
                "price": close_price,
                "deviation": self.config.default_deviation,
                "magic": self.config.magic_number,
                "comment": "Close via TG",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._determine_filling_type(symbol),
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                closed_count += 1

        return ExecutionResult(
            success=closed_count > 0,
            symbol=symbol,
            action="CLOSE",
            comment=f"Closed {closed_count}/{len(positions)} positions",
        )

    def close_all_positions(self) -> ExecutionResult:
        """Closes all open positions across all symbols."""
        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            return ExecutionResult(
                success=True,
                symbol="ALL",
                action="CLOSE_ALL",
                comment="No open positions to close",
            )

        closed_count = 0
        total = len(positions)
        for pos in positions:
            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                continue

            close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "price": close_price,
                "deviation": self.config.default_deviation,
                "magic": self.config.magic_number,
                "comment": "Close All via TG",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._determine_filling_type(pos.symbol),
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                closed_count += 1

        return ExecutionResult(
            success=closed_count == total,
            symbol="ALL",
            action="CLOSE_ALL",
            comment=f"Closed {closed_count}/{total} positions",
        )

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Returns details of all open positions."""
        if not self.initialize():
            return []

        positions = mt5.positions_get()
        if not positions:
            return []

        results = []
        for pos in positions:
            results.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": pos.volume,
                "open_price": pos.price_open,
                "current_price": pos.price_current,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit,
            })
        return results
