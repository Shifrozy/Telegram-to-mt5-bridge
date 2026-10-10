from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class OrderAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    BUY_LIMIT = "BUY_LIMIT"
    SELL_LIMIT = "SELL_LIMIT"
    BUY_STOP = "BUY_STOP"
    SELL_STOP = "SELL_STOP"
    CLOSE = "CLOSE"
    CLOSE_ALL = "CLOSE_ALL"


@dataclass
class TradeSignal:
    """Represents a parsed trading signal."""
    action: OrderAction
    symbol: str
    volume: Optional[float] = None
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    tp_levels: List[float] = field(default_factory=list)
    raw_text: str = ""
    comment: str = "TG-Bridge"


@dataclass
class ExecutionResult:
    """Represents the outcome of an order execution."""
    success: bool
    symbol: str
    action: str
    volume: float = 0.0
    price: float = 0.0
    sl: Optional[float] = None
    tp: Optional[float] = None
    order_ticket: Optional[int] = None
    retcode: Optional[int] = None
    error_message: Optional[str] = None
    dry_run: bool = False
    comment: str = ""
