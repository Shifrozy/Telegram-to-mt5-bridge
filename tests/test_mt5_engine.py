import pytest
from src.config import BridgeConfig
from src.models import TradeSignal, OrderAction
from src.mt5_engine import MT5Engine


def test_dry_run_execution():
    config = BridgeConfig(dry_run=True, default_lot_size=0.01)
    engine = MT5Engine(config)

    signal = TradeSignal(
        action=OrderAction.BUY,
        symbol="EURUSD",
        volume=0.05,
        sl=1.0800,
        tp=1.0900,
        comment="Test Trade"
    )

    result = engine.execute_signal(signal)
    assert result.success is True
    assert result.dry_run is True
    assert result.symbol == "EURUSD"
    assert result.action == "BUY"
    assert result.volume == 0.05
    assert result.sl == 1.0800
    assert result.tp == 1.0900
    assert result.order_ticket == 99999999


def test_dry_run_close_signal():
    config = BridgeConfig(dry_run=True)
    engine = MT5Engine(config)

    signal = TradeSignal(
        action=OrderAction.CLOSE,
        symbol="XAUUSD",
    )

    result = engine.execute_signal(signal)
    assert result.success is True
    assert result.dry_run is True
    assert result.symbol == "XAUUSD"
