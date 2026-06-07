# XAUUSD Trader Desktop App
# Chunk 1 — Config Store
# Spec: .kimchi/docs/plan.md

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict
import json


@dataclass
class TraderConfig:
    mt5_path: str
    mt5_account: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    symbol: str = "XAUUSD"
    symbol_aliases: Dict[str, str] = field(
        default_factory=lambda: {
            "GOLD": "XAUUSD",
            "XAU/USD": "XAUUSD",
        }
    )
    base_lot: float = 0.01
    martingale_multiplier: float = 2.0
    max_martingale_levels: int = 3
    position_a_ratio: float = 0.60
    position_b_ratio: float = 0.40
    magic_number: int = 20250605
    telegram_bot_token: str = ""
    sl_pips: int = 50
    tp1_pips: int = 25
    tp2_pips: int = 50
    pip_value: float = 0.10
    mt5_connect_retries: int = 5
    mt5_connect_retry_delay: int = 10
    state_file: str = "state.json"
    config_file: str = "config.json"
    pnl_target: float = 0.0
    pnl_check_interval_seconds: int = 10

    def save(self, path: str | None = None) -> None:
        target = Path(path) if path else Path.cwd() / self.config_file
        with open(target, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def load(path: str | None = None) -> "TraderConfig":
        target = Path(path) if path else Path.cwd() / "config.json"
        if not target.exists():
            return TraderConfig(mt5_path="")
        with open(target) as f:
            data = json.load(f)
        # Apply defaults for missing keys
        defaults = asdict(TraderConfig(mt5_path=""))
        for key, value in defaults.items():
            if key not in data:
                data[key] = value
        return TraderConfig(**data)

    def validate(self) -> None:
        if not self.mt5_path:
            raise ValueError("mt5_path must be non-empty")
        if self.base_lot <= 0:
            raise ValueError("base_lot must be greater than 0")
        total_ratio = self.position_a_ratio + self.position_b_ratio
        if not (0.99 <= total_ratio <= 1.01):
            raise ValueError(
                f"position_a_ratio + position_b_ratio must equal 1.0 "
                f"(got {total_ratio})"
            )