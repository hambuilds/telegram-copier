# IRCTC Vacancy Checker

Automated tool for checking train seat availability on the IRCTC online charts page, including split-journey options.

## Prerequisites

- Python 3.10+
- Chrome or Chromium browser

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
python main.py --train 12601 --from CLT --to MAS --class SL --date 2026-06-09
```

Options:
- `--train` — Train number (e.g. `12601`)
- `--from`  — Boarding station code (e.g. `CLT`)
- `--to`    — Destination station code (e.g. `MAS`)
- `--class` — Coach/class type (`SL`, `3A`, `3E`, `2A`, `1A`, `CC`, `2S`)
- `--date`  — Journey date in `YYYY-MM-DD` format
- `--no-headless` — Show browser window (useful for debugging)

## Running Tests

```bash
python3 -m pytest tests/ -v
```