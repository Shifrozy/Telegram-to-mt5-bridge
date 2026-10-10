import re
from typing import Optional, List, Dict
from src.models import TradeSignal, OrderAction

# Common symbol aliases
SYMBOL_ALIASES: Dict[str, str] = {
    "GOLD": "XAUUSD",
    "SILVER": "XAGUSD",
    "OIL": "USOUSD",
    "WTI": "USOUSD",
    "BRENT": "UKOUSD",
    "US30": "US30",
    "DJ30": "US30",
    "DOW": "US30",
    "NAS100": "NAS100",
    "USTEC": "NAS100",
    "NDX": "NAS100",
    "US500": "US500",
    "SPX500": "US500",
    "BTC": "BTCUSD",
    "ETH": "ETHUSD",
}

# Regex patterns for orders
ACTION_PATTERNS = [
    (r"\b(BUY\s+LIMIT)\b", OrderAction.BUY_LIMIT),
    (r"\b(SELL\s+LIMIT)\b", OrderAction.SELL_LIMIT),
    (r"\b(BUY\s+STOP)\b", OrderAction.BUY_STOP),
    (r"\b(SELL\s+STOP)\b", OrderAction.SELL_STOP),
    (r"\b(CLOSE\s+ALL)\b", OrderAction.CLOSE_ALL),
    (r"\b(CLOSE)\b", OrderAction.CLOSE),
    (r"\b(BUY\s+NOW|BUY|LONG)\b", OrderAction.BUY),
    (r"\b(SELL\s+NOW|SELL|SHORT)\b", OrderAction.SELL),
]


class SignalParser:
    """Parses telegram messages into structured TradeSignal instances."""

    def __init__(self, default_volume: Optional[float] = None):
        self.default_volume = default_volume

    def parse(self, text: str) -> Optional[TradeSignal]:
        """
        Parses text and extracts trading signal. Returns None if no trade action found.
        """
        if not text or not text.strip():
            return None

        # Clean text: uppercase and remove decorative emojis/bullets
        cleaned_text = text.strip()
        upper_text = cleaned_text.upper()

        # Check for Close All
        if "CLOSE ALL" in upper_text:
            return TradeSignal(
                action=OrderAction.CLOSE_ALL,
                symbol="ALL",
                raw_text=cleaned_text,
                comment="Close All"
            )

        # 1. Identify Action
        action: Optional[OrderAction] = None
        for pattern, act in ACTION_PATTERNS:
            if re.search(pattern, upper_text):
                action = act
                break

        if not action:
            return None

        # 2. Identify Symbol
        symbol = self._extract_symbol(upper_text)
        if not symbol and action != OrderAction.CLOSE_ALL:
            return None

        # 3. Extract Stop Loss (SL)
        sl = self._extract_price(upper_text, [
            r"SL\s*[:=-]?\s*(\d+(?:\.\d+)?)",
            r"STOP\s*LOSS\s*[:=-]?\s*(\d+(?:\.\d+)?)",
            r"STOP\s*[:=-]?\s*(\d+(?:\.\d+)?)",
        ])

        # 4. Extract Take Profits (TP, TP1, TP2, ...)
        tp_levels = self._extract_all_tps(upper_text)
        tp = tp_levels[0] if tp_levels else None

        # 5. Extract Entry Price (if given, e.g. @ 1.2345 or ENTRY 1.2345)
        price = self._extract_price(upper_text, [
            r"(?:AT|@|ENTRY|PRICE)\s*[:=-]?\s*(\d+(?:\.\d+)?)",
        ])

        # 6. Extract Volume (lot size) if specified (e.g., LOT: 0.1 or VOL: 0.05 or BUY EURUSD 0.05)
        volume = self._extract_volume(upper_text) or self.default_volume

        return TradeSignal(
            action=action,
            symbol=symbol,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
            tp_levels=tp_levels,
            raw_text=cleaned_text,
            comment="TG-Bridge"
        )

    def _extract_symbol(self, text: str) -> Optional[str]:
        """Extracts and normalizes currency pair, commodity, or crypto symbol."""
        # Check alias keys first (like GOLD, SILVER, US30)
        for alias, normalized in SYMBOL_ALIASES.items():
            if re.search(rf"\b{alias}\b", text):
                return normalized

        # Common Forex format e.g. EURUSD, GBP/USD, USDJPY, AUDNZD
        fx_match = re.search(r"\b([A-Z]{3})[\/_]?([A-Z]{3})\b", text)
        if fx_match:
            # Avoid matching words like BUY, SELL, NOW
            candidate = f"{fx_match.group(1)}{fx_match.group(2)}"
            common_currencies = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "XAU", "XAG", "BTC", "ETH"}
            if fx_match.group(1) in common_currencies or fx_match.group(2) in common_currencies:
                return candidate

        # Crypto e.g. BTCUSD, ETHUSD, SOLUSD
        crypto_match = re.search(r"\b(BTC|ETH|SOL|XRP|ADA|BNB|LTC)(?:USDT|USD)?\b", text)
        if crypto_match:
            base = crypto_match.group(1)
            return f"{base}USD"

        # Indices e.g. US30, NAS100, SPX500, GER30, GER40, UK100
        index_match = re.search(r"\b(US30|NAS100|SPX500|GER30|GER40|UK100|JPN225)\b", text)
        if index_match:
            return index_match.group(1)

        return None

    def _extract_price(self, text: str, patterns: List[str]) -> Optional[float]:
        """Extracts a numeric float value matching one of the regex patterns."""
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None

    def _extract_all_tps(self, text: str) -> List[float]:
        """Extracts all take profit values (TP, TP1, TP2, etc.)."""
        tps = []

        # 1. Numbered TPs like TP1: 1.0900 or TP1 1.0900
        numbered = re.findall(r"\bTP[1-9]\s*[:=-]?\s*(\d+(?:\.\d+)?)", text)
        for val_str in numbered:
            try:
                val = float(val_str)
                if val not in tps:
                    tps.append(val)
            except ValueError:
                continue

        # 2. Numbered TPs with space like TP 1: 1.0900
        spaced_numbered = re.findall(r"\bTP\s+[1-9]\s*[:=-]\s*(\d+(?:\.\d+)?)", text)
        for val_str in spaced_numbered:
            try:
                val = float(val_str)
                if val not in tps:
                    tps.append(val)
            except ValueError:
                continue

        # 3. Standard TP without index like TP: 1.0900 or TP 2620.00
        if not tps:
            standard = re.findall(r"\bTP\s*[:=-]?\s*(\d+(?:\.\d+)?)", text)
            for val_str in standard:
                try:
                    val = float(val_str)
                    if val not in tps:
                        tps.append(val)
                except ValueError:
                    continue

        # 4. If still none found, check for TAKE PROFIT
        if not tps:
            take_profit = re.findall(r"\bTAKE\s*PROFIT(?:\s*[1-9])?\s*[:=-]?\s*(\d+(?:\.\d+)?)", text)
            for val_str in take_profit:
                try:
                    val = float(val_str)
                    if val not in tps:
                        tps.append(val)
                except ValueError:
                    continue

        return tps

    def _extract_volume(self, text: str) -> Optional[float]:
        """Extracts lot size / volume if specified in the message."""
        # Explicit lot: LOT: 0.1 or LOTS 0.05 or VOL: 0.2
        explicit = re.search(r"\b(?:LOT|LOTS|VOL|VOLUME)\s*[:=-]?\s*(\d+(?:\.\d+)?)\b", text)
        if explicit:
            try:
                return float(explicit.group(1))
            except ValueError:
                pass

        # Positional lot after action & symbol: BUY EURUSD 0.1
        positional = re.search(r"\b(?:BUY|SELL)\s+[A-Z0-9_\/]+\s+(\d+\.\d+)\b", text)
        if positional:
            try:
                val = float(positional.group(1))
                # Reasonable lot size sanity check (< 100)
                if 0.001 <= val <= 100.0:
                    return val
            except ValueError:
                pass

        return None
