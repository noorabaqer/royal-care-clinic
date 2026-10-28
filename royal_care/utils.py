"""
utils.py
========
Small helper functions used by several modules:

* ``IdGenerator``  - produces readable, unique identifiers (e.g. ``PAT-0001``).
* ``to_money``     - converts numbers to ``Decimal`` rounded to 2 places.
* ``next_weekday`` - finds the next given weekday (used for "next Monday").
* ``format_money`` - formats a Decimal as a currency string.
"""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from itertools import count
from typing import Dict, Iterator, Union

Number = Union[int, float, str, Decimal]

CURRENCY = "$"


class IdGenerator:
    """Generates sequential, prefixed identifiers such as ``APT-0003``.

    One counter is kept per prefix, so patients and appointments are
    numbered independently.
    """

    _counters: Dict[str, Iterator[int]] = {}

    @classmethod
    def next_id(cls, prefix: str) -> str:
        """Return the next identifier for ``prefix``."""
        if prefix not in cls._counters:
            cls._counters[prefix] = count(1)
        return f"{prefix}-{next(cls._counters[prefix]):04d}"

    @classmethod
    def reset(cls) -> None:
        """Reset all counters (useful to make tests independent)."""
        cls._counters.clear()


def to_money(value: Number) -> Decimal:
    """Convert ``value`` to a Decimal rounded to cents.

    ``Decimal`` is used instead of ``float`` because floating point
    numbers cannot represent most cent values exactly (0.1 + 0.2 != 0.3).
    """
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_money(value: Decimal) -> str:
    """Return ``value`` formatted as currency, e.g. ``$1,250.00``."""
    return f"{CURRENCY}{value:,.2f}"


def next_weekday(start: date, weekday: int) -> date:
    """Return the next date after ``start`` falling on ``weekday`` (Mon=0).

    If ``start`` is itself that weekday, the date one week later is
    returned, which matches the everyday meaning of "next Monday".
    """
    days_ahead = (weekday - start.weekday()) % 7 or 7
    return start + timedelta(days=days_ahead)
