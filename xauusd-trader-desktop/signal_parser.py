"""
signal_parser.py — XAUUSD signal parser.

Parses trading signals (BUY/SELL with entry, SL, TP1, TP2) from plain-text
messages in three common Telegram formats:
  1. Multi-line   — each field on its own line
  2. Compact      — single-line with | or / separators
  3. Simple       — action + symbol + price, SL/TP lines follow

References:
  - Lesson: xauusd-trader-desktop/signal_parser.py
  - Spec:   telegram-mt5-bot/main.py (original regex implementations)
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Signal:
    """Represents a parsed trading signal."""
    action: str   # "BUY" or "SELL"
    symbol: str   # canonical symbol, e.g. "XAUUSD"
    entry: float
    sl: float
    tp1: float
    tp2: float


# -------------------------------------------------------------------
# Regex patterns ported from telegram-mt5-bot/main.py
# -------------------------------------------------------------------

ACTION_RE = re.compile(r"\b(BUY|SELL)\b", re.IGNORECASE)
SYMBOL_RE = re.compile(r"\b(XAUUSD|GOLD|XAU/USD)\b", re.IGNORECASE)

# Multi-line: each field on its own line
MULTI_LINE_RE = re.compile(
    r"(?i)\b(BUY|SELL)\s+(XAUUSD|GOLD|XAU/USD)\s*[@\s]\s*(\d+\.?\d*)"
    r".*?SL[:\s]+(\d+\.?\d*)"
    r".*?TP1[:\s]+(\d+\.?\d*)"
    r".*?TP2[:\s]+(\d+\.?\d*)",
    re.IGNORECASE | re.DOTALL,
)

# Compact single-line variants
COMPACT_RE = re.compile(
    r"(?:[-\s]*(?:GOLD|XAUUSD|XAU/USD)\s+)?\b(BUY|SELL)\s+(?:GOLD|XAUUSD|XAU/USD)?\s*(\d+\.?\d*)"
    r"(?:\s*[@\|\/])?\s*SL\s+(\d+\.?\d*)"
    r"(?:\s*[@\|\/])?\s*TP1\s+(\d+\.?\d*)"
    r"(?:\s*[@\|\/])?\s*TP2\s+(\d+\.?\d*)",
    re.IGNORECASE | re.DOTALL,
)

# Simple "BUY XAUUSD @ 2350.00" — entry only; SL/TP come from separate lines
SIMPLE_RE = re.compile(
    r"^(BUY|SELL)\s+(XAUUSD|GOLD|XAU/USD)\s*[@\s]\s*(\d+\.?\d*)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _canonical(symbol: str, aliases: dict[str, str]) -> str:
    """Resolve an alias to its canonical form, case-insensitively."""
    return aliases.get(symbol.upper(), symbol.upper())


def parse_signal(text: str, aliases: dict[str, str]) -> Signal | None:
    """
    Parse a plain-text message into a ``Signal`` dataclass.

    Tries three patterns in order:
      1. Multi-line  — action + symbol + entry on first line, then SL/TP1/TP2
      2. Compact     — single-line with ``|`` or ``/`` separators
      3. Simple      — action + symbol + entry only; SL/TP1/TP2 resolved from
                       additional lines in the same message

    Args:
        text:    raw message string (may contain newlines)
        aliases: mapping of symbol aliases to their canonical form,
                 e.g. ``{"GOLD": "XAUUSD", "XAU/USD": "XAUUSD"}``

    Returns:
        A ``Signal`` instance, or ``None`` if no pattern matches.
    """
    text = text.strip()
    if not text:
        return None

    # -----------------------------------------------------------------
    # Pattern 1 — multi-line
    # -----------------------------------------------------------------
    m = MULTI_LINE_RE.search(text)
    if m:
        action, raw_symbol, entry, sl, tp1, tp2 = m.groups()
        return Signal(
            action=action.upper(),
            symbol=_canonical(raw_symbol, aliases),
            entry=float(entry),
            sl=float(sl),
            tp1=float(tp1),
            tp2=float(tp2),
        )

    # -----------------------------------------------------------------
    # Pattern 2 — compact single-line
    # -----------------------------------------------------------------
    m = COMPACT_RE.search(text)
    if m:
        action, entry, sl, tp1, tp2 = m.groups()
        sym_match = SYMBOL_RE.search(text)
        raw_symbol = sym_match.group(1) if sym_match else "XAUUSD"
        return Signal(
            action=action.upper(),
            symbol=_canonical(raw_symbol, aliases),
            entry=float(entry),
            sl=float(sl),
            tp1=float(tp1),
            tp2=float(tp2),
        )

    # -----------------------------------------------------------------
    # Pattern 3 — simple "BUY XAUUSD @ 2350.00" + separate SL/TP lines
    # -----------------------------------------------------------------
    m = SIMPLE_RE.search(text)
    if m:
        action, raw_symbol, entry = m.groups()
        sl_match = re.search(r"SL[:\s]+(\d+\.?\d*)", text, re.IGNORECASE)
        tp1_match = re.search(r"TP1[:\s]+(\d+\.?\d*)", text, re.IGNORECASE)
        tp2_match = re.search(r"TP2[:\s]+(\d+\.?\d*)", text, re.IGNORECASE)
        if sl_match and tp1_match and tp2_match:
            return Signal(
                action=action.upper(),
                symbol=_canonical(raw_symbol, aliases),
                entry=float(entry),
                sl=float(sl_match.group(1)),
                tp1=float(tp1_match.group(1)),
                tp2=float(tp2_match.group(1)),
            )

    return None