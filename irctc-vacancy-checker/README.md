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

## How It Works

1. Opens the IRCTC online-charts page with Playwright.
2. Selects train number and journey date.
3. Extracts the full route from the boarding-station dropdown.
4. Fetches the reservation chart for the boarding station.
5. If direct availability is low/none, fetches charts for every intermediate station to find valid split-journey pairs.

## Running Tests

```bash
python3 -m pytest tests/ -v
```