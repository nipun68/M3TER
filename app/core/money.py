"""
Core Money implementation reproducing types/money.go with exact checked int64 arithmetic.
Guarantees zero floating-point imprecision.
"""
from __future__ import annotations
import math
from typing import Any, Dict, List


INT64_MAX = 9223372036854775807
INT64_MIN = -9223372036854775808

ZERO_DECIMAL_CURRENCIES = {
    "jpy", "krw", "vnd", "clp", "pyg", "idr"
}

CURRENCY_SYMBOLS = {
    "usd": "$",
    "eur": "€",
    "gbp": "£",
    "jpy": "¥",
    "cad": "C$",
    "aud": "A$",
    "chf": "CHF ",
    "cny": "¥",
    "sek": "kr ",
    "nzd": "NZ$",
}


class MoneyOverflowError(ArithmeticError):
    """Raised when checked monetary arithmetic exceeds 64-bit integer range."""
    pass


class CurrencyMismatchError(ValueError):
    """Raised when operating on Money with mismatched currencies."""
    pass


class Money:
    __slots__ = ("_amount", "_currency")

    def __init__(self, amount: int = 0, currency: str = "usd") -> None:
        if not isinstance(amount, int):
            raise TypeError(f"amount must be an integer, got {type(amount).__name__}")
        self._amount: int = int(amount)
        self._currency: str = currency.lower().strip()

    @property
    def amount(self) -> int:
        return self._amount

    @property
    def currency(self) -> str:
        return self._currency

    def _assert_same_currency(self, other: Money) -> None:
        if self._currency != other._currency:
            raise CurrencyMismatchError(
                f"money: currency mismatch: {self._currency} != {other._currency}"
            )

    def add(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(self._amount + other._amount, self._currency)

    def subtract(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(self._amount - other._amount, self._currency)

    def multiply(self, qty: int) -> Money:
        return Money(self._amount * qty, self._currency)

    def divide(self, divisor: int) -> Money:
        if divisor == 0:
            raise ZeroDivisionError("money: division by zero")
        # Integer division truncating toward zero
        if (self._amount < 0) ^ (divisor < 0):
            return Money(- (abs(self._amount) // abs(divisor)), self._currency)
        return Money(self._amount // divisor, self._currency)

    def percent(self, pct: int) -> Money:
        # Integer-only, truncating toward zero
        product = self._amount * pct
        if product < 0:
            return Money(- (abs(product) // 100), self._currency)
        return Money(product // 100, self._currency)

    def negate(self) -> Money:
        return Money(-self._amount, self._currency)

    def abs(self) -> Money:
        return Money(abs(self._amount), self._currency)

    def checked_add(self, other: Money) -> Money:
        self._assert_same_currency(other)
        res = self._amount + other._amount
        if res > INT64_MAX or res < INT64_MIN:
            raise MoneyOverflowError(f"money overflow: {self._amount} + {other._amount}")
        return Money(res, self._currency)

    def checked_subtract(self, other: Money) -> Money:
        self._assert_same_currency(other)
        res = self._amount - other._amount
        if res > INT64_MAX or res < INT64_MIN:
            raise MoneyOverflowError(f"money overflow: {self._amount} - {other._amount}")
        return Money(res, self._currency)

    def checked_multiply(self, qty: int) -> Money:
        res = self._amount * qty
        if res > INT64_MAX or res < INT64_MIN:
            raise MoneyOverflowError(f"money overflow: {self._amount} * {qty}")
        return Money(res, self._currency)

    def checked_percent(self, pct: int) -> Money:
        product = self._amount * pct
        if product > INT64_MAX or product < INT64_MIN:
            raise MoneyOverflowError(f"money overflow: {self._amount} * {pct}%")
        if product < 0:
            return Money(- (abs(product) // 100), self._currency)
        return Money(product // 100, self._currency)

    def is_zero(self) -> bool:
        return self._amount == 0

    def is_positive(self) -> bool:
        return self._amount > 0

    def is_negative(self) -> bool:
        return self._amount < 0

    def equal(self, other: Money) -> bool:
        return self._amount == other._amount and self._currency == other._currency

    def less_than(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self._amount < other._amount

    def greater_than(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self._amount > other._amount

    def min(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return self if self._amount < other._amount else other

    def max(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return self if self._amount > other._amount else other

    def format_major(self) -> str:
        decimals = 0 if self._currency in ZERO_DECIMAL_CURRENCIES else 2
        if decimals == 0:
            return str(self._amount)
        is_negative = self._amount < 0
        abs_amount = abs(self._amount)
        major = abs_amount // 100
        minor = abs_amount % 100
        result = f"{major}.{minor:02d}"
        return f"-{result}" if is_negative else result

    def __str__(self) -> str:
        symbol = CURRENCY_SYMBOLS.get(self._currency, self._currency.upper() + " ")
        return f"{symbol}{self.format_major()}"

    def __repr__(self) -> str:
        return f"Money({self._amount}, {self._currency!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return False
        return self.equal(other)

    def __lt__(self, other: Money) -> bool:
        return self.less_than(other)

    def __gt__(self, other: Money) -> bool:
        return self.greater_than(other)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "amount": self._amount,
            "currency": self._currency,
            "display": str(self),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Money:
        if not data:
            return cls(0, "usd")
        return cls(amount=int(data.get("amount", 0)), currency=str(data.get("currency", "usd")))


def usd(cents: int) -> Money:
    return Money(cents, "usd")


def eur(cents: int) -> Money:
    return Money(cents, "eur")


def gbp(pence: int) -> Money:
    return Money(pence, "gbp")


def jpy(yen: int) -> Money:
    return Money(yen, "jpy")


def cad(cents: int) -> Money:
    return Money(cents, "cad")


def aud(cents: int) -> Money:
    return Money(cents, "aud")


def zero(currency: str = "usd") -> Money:
    return Money(0, currency)


def sum_money(*values: Money) -> Money:
    if not values:
        return zero("usd")
    res = values[0]
    for v in values[1:]:
        res = res.add(v)
    return res
