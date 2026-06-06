"""
format_manager.py — Signal format manager for XAUUSD Trader Desktop.

Manages built-in and user-defined signal parsing formats.
Built-in presets cover the most common Telegram signal layouts.
Users can add custom formats via a token-tagger GUI that generates
a regex behind the scenes.

References:
  - Lesson: xauusd-trader-desktop/format_manager.py
  - Original: signal_parser.py (legacy regexes ported as presets)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from signal_parser import Signal

_log = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Field regex fragments (named groups)
# -------------------------------------------------------------------

FIELD_PATTERNS: Dict[str, str] = {
    "action": r"(?P<action>BUY|SELL)",
    "symbol": r"(?P<symbol>XAUUSD|GOLD|XAU/USD|[A-Z]{3,6})",
    "entry": r"(?P<entry>\d+\.?\d*)",
    "sl": r"(?P<sl>\d+\.?\d*)",
    "tp1": r"(?P<tp1>\d+\.?\d*)",
    "tp2": r"(?P<tp2>\d+\.?\d*)",
}

# Tokens recognised when splitting a sample message for tagging.
_TOKEN_RE = re.compile(r"\d+\.?\d*|[A-Za-z0-9_/]+|[^A-Za-z0-9_\s]+")

# -------------------------------------------------------------------
# Built-in presets (populated once on first use)
# -------------------------------------------------------------------

_BUILTIN_PROFILES: Optional[List[SignalFormatProfile]] = None


def _builtin_profiles() -> List[SignalFormatProfile]:
    global _BUILTIN_PROFILES
    if _BUILTIN_PROFILES is not None:
        return _BUILTIN_PROFILES
    _BUILTIN_PROFILES = [
        SignalFormatProfile(
            id="builtin-standard",
            name="Standard (multi-line / simple)",
            pattern=(
                r"(?is)\b(?P<action>BUY|SELL)\s+(?P<symbol>XAUUSD|GOLD|XAU/USD)\s*[@\s]\s*(?P<entry>\d+\.?\d*)"
                r".*?SL[:\s]+(?P<sl>\d+\.?\d*)"
                r".*?TP1[:\s]+(?P<tp1>\d+\.?\d*)"
                r".*?TP2[:\s]+(?P<tp2>\d+\.?\d*)"
            ),
            is_builtin=True,
        ),
        SignalFormatProfile(
            id="builtin-compact",
            name="Compact (|, / separators)",
            pattern=(
                r"(?is)"
                r"(?P<symbol>XAUUSD|GOLD|XAU/USD)?\s*"
                r"(?P<action>BUY|SELL)\s+"
                r"(?:XAUUSD|GOLD|XAU/USD)?\s*"
                r"(?P<entry>\d+\.?\d*)"
                r"(?:\s*[@\|/])?\s*SL\s+(?P<sl>\d+\.?\d*)"
                r"(?:\s*[@\|/])?\s*TP1\s+(?P<tp1>\d+\.?\d*)"
                r"(?:\s*[@\|/])?\s*TP2\s+(?P<tp2>\d+\.?\d*)"
            ),
            is_builtin=True,
        ),
        SignalFormatProfile(
            id="builtin-tradingview",
            name="TradingView Alert",
            pattern=(
                r"(?is)\b(?P<action>BUY|SELL)\s+(?P<symbol>XAUUSD|GOLD|XAU/USD)"
                r"\s*[@]?\s*(?P<entry>\d+\.?\d*)"
                r"\s*SL[=:\s]+(?P<sl>\d+\.?\d*)"
                r"\s*TP1[=:\s]+(?P<tp1>\d+\.?\d*)"
                r"\s*TP2[=:\s]+(?P<tp2>\d+\.?\d*)"
            ),
            is_builtin=True,
        ),
    ]
    return _BUILTIN_PROFILES


# -------------------------------------------------------------------
# Data classes
# -------------------------------------------------------------------


@dataclass
class SignalFormatProfile:
    """A single signal parsing profile."""

    id: str
    name: str
    pattern: str
    is_builtin: bool = True
    template: str | None = None  # Optional friendly template string for the GUI

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "pattern": self.pattern,
            "is_builtin": self.is_builtin,
            "template": self.template,
        }

    @staticmethod
    def from_dict(data: dict) -> SignalFormatProfile:
        return SignalFormatProfile(
            id=data["id"],
            name=data["name"],
            pattern=data["pattern"],
            is_builtin=data.get("is_builtin", False),
            template=data.get("template", None),
        )


@dataclass
class TaggedToken:
    """One token from the sample message plus its user-assigned tag."""

    text: str
    tag: str  # "literal", "ignore", "action", "symbol", "entry", "sl", "tp1", "tp2"

    def to_dict(self) -> dict:
        return {"text": self.text, "tag": self.tag}

    @staticmethod
    def from_dict(data: dict) -> TaggedToken:
        return TaggedToken(text=data.get("text", ""), tag=data.get("tag", "literal"))


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _safe_symbol(m: re.Match, text: str) -> str:
    """Extract symbol from match, with fallback to text search or XAUUSD."""
    raw = None
    try:
        raw = m.group("symbol")
    except (IndexError, AttributeError):
        pass
    if raw:
        return raw.upper()
    # Fallback: search for a known symbol anywhere in the full text
    sym_match = re.search(r"\b(XAUUSD|GOLD|XAU/USD)\b", text, re.IGNORECASE)
    if sym_match:
        return sym_match.group(1).upper()
    return "XAUUSD"


def _extract_signal(m: re.Match, text: str, aliases: Dict[str, str]) -> Signal:
    """Build a Signal from a successful regex match."""
    action = m.group("action").upper()
    raw_symbol = _safe_symbol(m, text)
    canonical = aliases.get(raw_symbol, raw_symbol)
    return Signal(
        action=action,
        symbol=canonical,
        entry=float(m.group("entry")),
        sl=float(m.group("sl")),
        tp1=float(m.group("tp1")),
        tp2=float(m.group("tp2")),
    )


# -------------------------------------------------------------------
# Regex builder
# -------------------------------------------------------------------


def build_regex_from_tokens(tokens: List[TaggedToken]) -> str:
    """
    Convert a list of user-tagged tokens into a regex pattern string.

    Literal tokens are escaped.  Field tags become named capture groups.
    ``ignore`` tags become ``.*?`` (non-greedy).  Whitespace ``\\s+`` is
    inserted between adjacent non-ignore fragments.
    """
    fragments: List[str] = []

    for token in tokens:
        tag = token.tag
        text = token.text

        if tag in FIELD_PATTERNS:
            fragments.append(FIELD_PATTERNS[tag])
        elif tag == "ignore":
            # Collapse consecutive ignores into one .*?
            if fragments and fragments[-1] == ".*?":
                continue
            fragments.append(".*?")
        else:
            # literal (or unknown)
            fragments.append(re.escape(text))

    # Insert \s+ between adjacent non-ignore fragments
    joined: List[str] = []
    for i, frag in enumerate(fragments):
        joined.append(frag)
        if i + 1 < len(fragments):
            nxt = fragments[i + 1]
            if frag != ".*?" and nxt != ".*?":
                joined.append(r"\s+")

    return "(?is)" + "".join(joined)


def tokenize_sample(text: str) -> List[str]:
    """Split ``text`` into whitespace-separated tokens for tagging."""
    return text.split()


def tokens_to_tagged(text: str, tags: List[str]) -> List[TaggedToken]:
    """Zip tokenized ``text`` with a parallel list of tag strings."""
    tokens = tokenize_sample(text)
    if len(tokens) != len(tags):
        raise ValueError(
            f"Token count ({len(tokens)}) != tag count ({len(tags)})"
        )
    return [TaggedToken(t, g) for t, g in zip(tokens, tags)]


# -------------------------------------------------------------------
# Format Manager
# -------------------------------------------------------------------


class FormatManager:
    """
    Loads built-in format presets plus any user-created custom profiles,
    and attempts to parse raw signal text using them.
    """

    _formats_path: str = "formats.json"

    def __init__(self, custom_profiles: Optional[List[SignalFormatProfile]] = None) -> None:
        self._builtins = _builtin_profiles()
        self._customs: List[SignalFormatProfile] = list(custom_profiles or [])
        self._compiled: Dict[str, re.Pattern] = {}

    # -- persistence helpers ------------------------------------------------

    @classmethod
    def load_from_config(cls, path: str | None = None) -> FormatManager:
        """Load custom profiles from the JSON file if present."""
        target = Path(path or cls._formats_path)
        if not target.exists():
            return cls()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            profiles = [
                SignalFormatProfile.from_dict(p)
                for p in data.get("profiles", [])
                if not p.get("is_builtin", False)
            ]
            return cls(custom_profiles=profiles)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            _log.warning("Could not load signal formats: %s", exc)
            return cls()

    def save_to_config(self, path: str | None = None) -> None:
        """Persist custom profiles into the JSON file."""
        target = Path(path or self._formats_path)
        data: dict = {}
        if target.exists():
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        data["profiles"] = [p.to_dict() for p in self._customs]
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # -- profile management -------------------------------------------------

    def all_profiles(self) -> List[SignalFormatProfile]:
        """Return builtins followed by customs."""
        return self._builtins + self._customs

    def custom_profiles(self) -> List[SignalFormatProfile]:
        return list(self._customs)

    def add_custom_profile(
        self,
        name: str,
        pattern: str,
        template: str | None = None,
        profile_id: str | None = None,
    ) -> SignalFormatProfile:
        """Add a new custom profile after validating the regex compiles."""
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern: {exc}")

        # Ensure unique id
        existing_ids = {p.id for p in self.all_profiles()}
        new_id = profile_id or f"custom-{len(self._customs) + 1:03d}"
        while new_id in existing_ids:
            new_id = f"custom-{len(self._customs) + 1:03d}-dup"

        profile = SignalFormatProfile(
            id=new_id,
            name=name,
            pattern=pattern,
            is_builtin=False,
            template=template,
        )
        self._customs.append(profile)
        return profile

    def delete_custom_profile(self, profile_id: str) -> bool:
        """Remove a custom profile by ID.  Built-ins cannot be deleted."""
        for i, p in enumerate(self._customs):
            if p.id == profile_id:
                del self._customs[i]
                return True
        return False

    def _get_compiled(self, profile: SignalFormatProfile) -> re.Pattern:
        """Return a compiled regex, caching results."""
        cache_key = profile.id + "::" + profile.pattern
        if cache_key not in self._compiled:
            flags = re.IGNORECASE | re.DOTALL
            self._compiled[cache_key] = re.compile(profile.pattern, flags)
        return self._compiled[cache_key]

    # -- matching -----------------------------------------------------------

    def match(self, text: str, aliases: Dict[str, str]) -> Signal | None:
        """
        Try every profile (built-ins first, then customs) against ``text``.

        Returns the first successful ``Signal`` or ``None``.
        """
        text = text.strip()
        if not text:
            return None

        for profile in self.all_profiles():
            compiled = self._get_compiled(profile)
            m = compiled.search(text)
            if not m:
                continue
            try:
                signal = _extract_signal(m, text, aliases)
                return signal
            except (IndexError, AttributeError, ValueError):
                # Named group missing or not a number
                continue

        return None

    def test_pattern(self, pattern: str, samples: List[str]) -> List[Optional[Signal]]:
        """
        Test a raw regex pattern (not yet saved) against a list of sample
        strings.  Returns a parallel list of Signal or None.
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
        except re.error as exc:
            raise ValueError(f"Invalid regex: {exc}")

        results: List[Optional[Signal]] = []
        for text in samples:
            text = text.strip()
            m = compiled.search(text) if text else None
            if not m:
                results.append(None)
                continue
            try:
                signal = _extract_signal(m, text, {})
                results.append(signal)
            except (IndexError, AttributeError, ValueError):
                results.append(None)
        return results


# -------------------------------------------------------------------
# Convenience: drop-in replacement for parse_signal()
# -------------------------------------------------------------------

# Module-level singleton, created on first use.
_default_manager: FormatManager | None = None


def get_manager() -> FormatManager:
    """Return the module-level FormatManager singleton."""
    global _default_manager
    if _default_manager is None:
        _default_manager = FormatManager.load_from_config()
    return _default_manager


def parse_signal(text: str, aliases: Dict[str, str]) -> Signal | None:
    """
    Backward-compatible wrapper that delegates to a ``FormatManager``.
    Loads custom profiles from ``formats.json`` on first call.
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = FormatManager.load_from_config()
    return _default_manager.match(text, aliases)
