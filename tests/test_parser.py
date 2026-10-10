import pytest
from src.parser import SignalParser
from src.models import OrderAction


def test_standard_buy_signal():
    parser = SignalParser(default_volume=0.01)
    text = """
    BUY EURUSD
    SL: 1.0820
    TP: 1.0920
    """
    signal = parser.parse(text)
    assert signal is not None
    assert signal.action == OrderAction.BUY
    assert signal.symbol == "EURUSD"
    assert signal.sl == 1.0820
    assert signal.tp == 1.0920
    assert signal.volume == 0.01


def test_gold_alias_and_inlined():
    parser = SignalParser(default_volume=0.02)
    text = "SELL GOLD @ 2650.50 SL 2665.00 TP 2620.00"
    signal = parser.parse(text)
    assert signal is not None
    assert signal.action == OrderAction.SELL
    assert signal.symbol == "XAUUSD"
    assert signal.price == 2650.50
    assert signal.sl == 2665.00
    assert signal.tp == 2620.00
    assert signal.volume == 0.02


def test_multi_tp_and_explicit_volume():
    parser = SignalParser(default_volume=0.01)
    text = """
    🚀 BUY GBPUSD 0.05
    SL: 1.2950
    TP1: 1.3050
    TP2: 1.3100
    TP3: 1.3150
    """
    signal = parser.parse(text)
    assert signal is not None
    assert signal.action == OrderAction.BUY
    assert signal.symbol == "GBPUSD"
    assert signal.volume == 0.05
    assert signal.sl == 1.2950
    assert signal.tp == 1.3050
    assert signal.tp_levels == [1.3050, 1.3100, 1.3150]


def test_pending_orders():
    parser = SignalParser()
    text = "BUY LIMIT EURUSD 1.0750 SL: 1.0700 TP: 1.0850"
    signal = parser.parse(text)
    assert signal is not None
    assert signal.action == OrderAction.BUY_LIMIT
    assert signal.symbol == "EURUSD"
    assert signal.sl == 1.0700
    assert signal.tp == 1.0850

    text2 = "SELL STOP XAUUSD 2630 SL: 2640 TP: 2610"
    signal2 = parser.parse(text2)
    assert signal2 is not None
    assert signal2.action == OrderAction.SELL_STOP
    assert signal2.symbol == "XAUUSD"


def test_close_signals():
    parser = SignalParser()
    assert parser.parse("CLOSE EURUSD").action == OrderAction.CLOSE
    assert parser.parse("CLOSE ALL").action == OrderAction.CLOSE_ALL


def test_ignores_regular_conversations():
    parser = SignalParser()
    assert parser.parse("Hello everyone, how is trading today?") is None
    assert parser.parse("I bought some coffee earlier") is None
    assert parser.parse("What do you think about market trend?") is None
    assert parser.parse("") is None
