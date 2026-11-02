"""
Unit tests for Money checked arithmetic replicating types/money_test.go.
"""
import pytest
from app.core.money import (
    Money,
    usd,
    eur,
    gbp,
    jpy,
    zero,
    sum_money,
    MoneyOverflowError,
    CurrencyMismatchError,
    INT64_MAX,
    INT64_MIN,
)


def test_money_creation_and_formatting():
    m1 = usd(4900)
    assert m1.amount == 4900
    assert m1.currency == "usd"
    assert m1.format_major() == "49.00"
    assert str(m1) == "$49.00"

    m_jpy = jpy(100)
    assert m_jpy.amount == 100
    assert m_jpy.currency == "jpy"
    assert m_jpy.format_major() == "100"
    assert str(m_jpy) == "¥100"

    m_neg = usd(-1050)
    assert m_neg.format_major() == "-10.50"
    assert str(m_neg) == "$-10.50"


def test_money_arithmetic():
    a = usd(1000)
    b = usd(500)

    assert a.add(b) == usd(1500)
    assert a.subtract(b) == usd(500)
    assert a.multiply(3) == usd(3000)
    assert a.divide(4) == usd(250)
    assert a.percent(15) == usd(150)
    assert a.negate() == usd(-1000)
    assert a.negate().abs() == usd(1000)


def test_percent_truncation_toward_zero():
    # 10% of 101 cents is 10 cents, not 11
    assert usd(101).percent(10) == usd(10)
    # 10% of -101 cents is -10 cents, not -11
    assert usd(-101).percent(10) == usd(-10)


def test_currency_mismatch():
    a = usd(100)
    b = eur(100)
    with pytest.raises(CurrencyMismatchError):
        a.add(b)
    with pytest.raises(CurrencyMismatchError):
        a.subtract(b)
    with pytest.raises(CurrencyMismatchError):
        a.less_than(b)


def test_checked_arithmetic_overflow():
    max_m = Money(INT64_MAX, "usd")
    one = usd(1)

    with pytest.raises(MoneyOverflowError):
        max_m.checked_add(one)

    min_m = Money(INT64_MIN, "usd")
    with pytest.raises(MoneyOverflowError):
        min_m.checked_subtract(one)

    with pytest.raises(MoneyOverflowError):
        usd(INT64_MAX // 2 + 10).checked_multiply(3)


def test_sum_money():
    total = sum_money(usd(100), usd(250), usd(450))
    assert total == usd(800)

    empty_sum = sum_money()
    assert empty_sum == zero("usd")
