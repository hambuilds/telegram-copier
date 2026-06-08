# IRCTC Vacancy Checker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that automates the IRCTC online-charts page to check direct and split-journey seat availability.

**Architecture:** Playwright browser automation for chart scraping + pure-Python logic for journey planning. Four-module design: config, chart scraper, journey planner, CLI orchestrator.

**Tech Stack:** Python 3.10+, Playwright, argparse, dataclasses, pytest.

**Project root:** `irctc-vacancy-checker/`

---

### Task 1: Project Scaffold

**Files:**
- Create: `irctc-vacancy-checker/requirements.txt`
- Create: `irctc-vacancy-checker/README.md` (skeleton)
- Create: `irctc-vacancy-checker/tests/__init__.py`

- [ ] **Step 1: Create directory structure and requirements**

```bash
mkdir -p irctc-vacancy-checker/tests
touch irctc-vacancy-checker/tests/__init__.py
```

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/requirements.txt`:

```text
playwright>=1.40.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

- [ ] **Step 2: Install dependencies**

Run:
```bash
cd irctc-vacancy-checker
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

Expected: `chromium v<version>` downloaded successfully.

- [ ] **Step 3: Commit**

```bash
git add irctc-vacancy-checker/
git commit -m "feat: scaffold irctc-vacancy-checker project"
```

---

### Task 2: Data Models and Config

**Files:**
- Create: `irctc-vacancy-checker/config.py`
- Create: `irctc-vacancy-checker/models.py`
- Test: `irctc-vacancy-checker/tests/test_models.py`

- [ ] **Step 1: Write config module**

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/config.py`:

```python
"""Default configuration constants."""

IRCTC_CHARTS_URL = "https://www.irctc.co.in/online-charts/"
DEFAULT_TIMEOUT = 30_000  # ms
MAX_RETRIES = 1

CLASS_TYPE_MAP = {
    "SL": ["SL", "Sleeper", "Sleeper Class"],
    "3A": ["3A", "Third AC", "3AC"],
    "3E": ["3E", "3AC Economy", "Third AC Economy"],
    "2A": ["2A", "Second AC", "2AC"],
    "1A": ["1A", "First AC", "1AC"],
    "CC": ["CC", "Chair Car"],
    "2S": ["2S", "Second Sitting"],
}

def normalize_class_type(user_input: str) -> str:
    """Map user-friendly class name to canonical short code."""
    upper = user_input.upper().strip()
    for canon, aliases in CLASS_TYPE_MAP.items():
        if upper == canon or upper in [a.upper() for a in aliases]:
            return canon
    raise ValueError(f"Unknown class type: {user_input}")
```

- [ ] **Step 2: Write data models**

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/models.py`:

```python
"""Domain data models."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Station:
    code: str
    name: str

    def __repr__(self) -> str:
        return f"{self.code} ({self.name})"


@dataclass
class CoachVacancy:
    coach_number: str
    class_type: str
    vacant_count: int


@dataclass
class ChartResult:
    train_number: str
    journey_date: str
    boarding_station: str
    stations: List[Station] = field(default_factory=list)
    coaches: List[CoachVacancy] = field(default_factory=list)

    def vacant_for_class(self, class_type: str) -> List[CoachVacancy]:
        """Return coaches matching the canonical class type."""
        return [c for c in self.coaches if c.class_type.upper() == class_type.upper()]

    def total_vacant_for_class(self, class_type: str) -> int:
        return sum(c.vacant_count for c in self.vacant_for_class(class_type))
```

- [ ] **Step 3: Write model tests**

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/tests/test_models.py`:

```python
"""Tests for data models."""

import pytest
from models import Station, CoachVacancy, ChartResult
from config import normalize_class_type


def test_station_repr():
    s = Station("CLT", "Kozhikode")
    assert repr(s) == "CLT (Kozhikode)"


def test_chart_vacant_for_class():
    chart = ChartResult(
        train_number="12601",
        journey_date="2026-06-09",
        boarding_station="CLT",
        coaches=[
            CoachVacancy("S1", "SL", 4),
            CoachVacancy("S2", "SL", 3),
            CoachVacancy("B1", "3A", 2),
        ],
    )
    assert len(chart.vacant_for_class("SL")) == 2
    assert chart.total_vacant_for_class("SL") == 7
    assert chart.total_vacant_for_class("3A") == 2


def test_normalize_class_type():
    assert normalize_class_type("SL") == "SL"
    assert normalize_class_type("sleeper") == "SL"
    assert normalize_class_type("3AC") == "3A"


def test_normalize_class_type_invalid():
    with pytest.raises(ValueError, match="Unknown class type"):
        normalize_class_type("XX")
```

- [ ] **Step 4: Run tests**

Run:
```bash
cd irctc-vacancy-checker
python3 -m pytest tests/test_models.py -v
```

Expected: 4 tests passing.

- [ ] **Step 5: Commit**

```bash
git add irctc-vacancy-checker/config.py irctc-vacancy-checker/models.py irctc-vacancy-checker/tests/test_models.py
git commit -m "feat: add config and data models with tests"
```

---

### Task 3: Journey Planner Logic

**Files:**
- Create: `irctc-vacancy-checker/journey_planner.py`
- Test: `irctc-vacancy-checker/tests/test_journey_planner.py`

- [ ] **Step 1: Write journey planner**

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/journey_planner.py`:

```python
"""Pure logic for direct and split-journey availability analysis."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict

from models import ChartResult, CoachVacancy, Station


@dataclass
class DirectResult:
    available: bool
    total_seats: int
    coach_breakdown: List[CoachVacancy] = field(default_factory=list)


@dataclass
class SplitOption:
    intermediate_station: str
    leg1_seats: int
    leg2_seats: int
    leg1_coaches: List[CoachVacancy] = field(default_factory=list)
    leg2_coaches: List[CoachVacancy] = field(default_factory=list)

    @property
    def total_seats(self) -> int:
        return min(self.leg1_seats, self.leg2_seats)


@dataclass
class JourneyPlan:
    train_number: str
    journey_date: str
    from_station: str
    to_station: str
    class_type: str
    direct: DirectResult
    split_options: List[SplitOption] = field(default_factory=list)


def find_station_index(stations: List[Station], code: str) -> int:
    for idx, s in enumerate(stations):
        if s.code.upper() == code.upper():
            return idx
    raise ValueError(f"Station code {code} not found in route")


def analyze_direct(
    chart: ChartResult,
    class_type: str,
) -> DirectResult:
    """Check direct availability from chart's boarding station to destination."""
    coaches = chart.vacant_for_class(class_type)
    total = sum(c.vacant_count for c in coaches)
    return DirectResult(
        available=total > 0,
        total_seats=total,
        coach_breakdown=coaches,
    )


def analyze_split_journey(
    base_chart: ChartResult,
    intermediate_charts: Dict[str, ChartResult],
    to_station: str,
    class_type: str,
) -> List[SplitOption]:
    """
    Find all valid split-journey options.

    Parameters
    ----------
    base_chart : ChartResult
        Chart for the original boarding station.
    intermediate_charts : dict[str, ChartResult]
        Mapping of intermediate station code -> chart with that station as boarding point.
    to_station : str
        Final destination station code.
    class_type : str
        Canonical class type code.
    """
    options: List[SplitOption] = []
    stations = base_chart.stations
    from_idx = find_station_index(stations, base_chart.boarding_station)
    to_idx = find_station_index(stations, to_station)

    if from_idx >= to_idx:
        return options

    for c_idx in range(from_idx + 1, to_idx):
        inter_code = stations[c_idx].code
        leg1 = analyze_direct(base_chart, class_type)
        inter_chart = intermediate_charts.get(inter_code)
        if inter_chart is None:
            continue
        leg2 = analyze_direct(inter_chart, class_type)
        if leg1.available and leg2.available:
            options.append(
                SplitOption(
                    intermediate_station=inter_code,
                    leg1_seats=leg1.total_seats,
                    leg2_seats=leg2.total_seats,
                    leg1_coaches=leg1.coach_breakdown,
                    leg2_coaches=leg2.coach_breakdown,
                )
            )
    return options
```

- [ ] **Step 2: Write planner tests**

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/tests/test_journey_planner.py`:

```python
"""Tests for journey planner logic."""

import pytest
from models import Station, CoachVacancy, ChartResult
from journey_planner import (
    analyze_direct,
    analyze_split_journey,
    find_station_index,
    DirectResult,
    SplitOption,
)


def make_chart(boarding: str, coaches: list, stations: list = None) -> ChartResult:
    default_stations = [
        Station("CLT", "Kozhikode"),
        Station("TCR", "Thrissur"),
        Station("ERS", "Ernakulam"),
        Station("ALLP", "Alappuzha"),
        Station("KYJ", "Kayamkulam"),
    ]
    return ChartResult(
        train_number="12601",
        journey_date="2026-06-09",
        boarding_station=boarding,
        stations=stations or default_stations,
        coaches=coaches,
    )


def test_find_station_index():
    stations = [Station("A", "Alpha"), Station("B", "Beta"), Station("C", "Gamma")]
    assert find_station_index(stations, "B") == 1
    with pytest.raises(ValueError):
        find_station_index(stations, "Z")


def test_analyze_direct_available():
    chart = make_chart("CLT", [CoachVacancy("S1", "SL", 5), CoachVacancy("S2", "SL", 3)])
    result = analyze_direct(chart, "SL")
    assert result.available is True
    assert result.total_seats == 8


def test_analyze_direct_unavailable():
    chart = make_chart("CLT", [CoachVacancy("B1", "3A", 2)])
    result = analyze_direct(chart, "SL")
    assert result.available is False
    assert result.total_seats == 0


def test_analyze_split_journey_found():
    base = make_chart("CLT", [CoachVacancy("S1", "SL", 10)])
    inter = make_chart("TCR", [CoachVacancy("S1", "SL", 6)])
    inter.boarding_station = "TCR"
    options = analyze_split_journey(
        base,
        {"TCR": inter},
        to_station="KYJ",
        class_type="SL",
    )
    assert len(options) == 1
    assert options[0].intermediate_station == "TCR"
    assert options[0].leg1_seats == 10
    assert options[0].leg2_seats == 6
    assert options[0].total_seats == 6


def test_analyze_split_journey_none():
    base = make_chart("CLT", [CoachVacancy("S1", "SL", 10)])
    inter = make_chart("TCR", [CoachVacancy("S1", "SL", 0)])
    inter.boarding_station = "TCR"
    options = analyze_split_journey(
        base,
        {"TCR": inter},
        to_station="KYJ",
        class_type="SL",
    )
    assert len(options) == 0
```

- [ ] **Step 3: Run tests**

Run:
```bash
cd irctc-vacancy-checker
python3 -m pytest tests/test_journey_planner.py -v
```

Expected: 5 tests passing.

- [ ] **Step 4: Commit**

```bash
git add irctc-vacancy-checker/journey_planner.py irctc-vacancy-checker/tests/test_journey_planner.py
git commit -m "feat: add journey planner logic with tests"
```

---

### Task 4: Chart Scraper (Playwright)

**Files:**
- Create: `irctc-vacancy-checker/chart_scraper.py`
- Test: `irctc-vacancy-checker/tests/test_chart_scraper.py`

- [ ] **Step 1: Write chart scraper**

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/chart_scraper.py`:

```python
"""Playwright-based scraper for IRCTC online charts."""

import asyncio
from typing import List, Optional
from playwright.async_api import async_playwright, Page

from models import Station, CoachVacancy, ChartResult
from config import IRCTC_CHARTS_URL, DEFAULT_TIMEOUT


class ChartScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _new_page(self) -> Page:
        page = await self._browser.new_page()
        await page.goto(IRCTC_CHARTS_URL, wait_until="networkidle")
        return page

    async def fetch_chart(
        self,
        train_number: str,
        journey_date: str,
        boarding_station: str,
        stations: Optional[List[Station]] = None,
    ) -> ChartResult:
        """
        Fetch reservation chart for a specific train, date, and boarding station.

        If `stations` is provided (e.g. from an earlier route extraction),
        the scraper skips re-extraction and uses the supplied list.
        """
        page = await self._new_page()
        try:
            # 1. Fill train number (typeahead)
            train_input = page.locator("input[placeholder*='Train Name']")
            await train_input.fill(train_number)
            await page.wait_for_selector("mat-option", timeout=DEFAULT_TIMEOUT)
            await page.locator("mat-option").first.click()

            # 2. Fill journey date
            date_input = page.locator("input[placeholder*='Journey Date']")
            await date_input.fill(journey_date)
            # Close date picker if it opened
            await page.keyboard.press("Escape")

            # 3. Extract stations from boarding dropdown if not provided
            if stations is None:
                boarding_select = page.locator("mat-select[formcontrolname='boardingStation']")
                await boarding_select.click()
                await page.wait_for_selector("mat-option", timeout=DEFAULT_TIMEOUT)
                opts = await page.locator("mat-option").all()
                stations = []
                for opt in opts:
                    text = await opt.inner_text()
                    code = text.strip().split()[0]  # e.g. "CLT - KOZHIKODE"
                    name = text.strip()
                    stations.append(Station(code, name))
                await page.keyboard.press("Escape")
            else:
                boarding_select = page.locator("mat-select[formcontrolname='boardingStation']")
                await boarding_select.click()
                await page.wait_for_selector("mat-option", timeout=DEFAULT_TIMEOUT)

            # 4. Select boarding station
            option_texts = await page.locator("mat-option").all_inner_texts()
            target_opt = None
            for idx, txt in enumerate(option_texts):
                if boarding_station.upper() in txt.upper():
                    target_opt = page.locator("mat-option").nth(idx)
                    break
            if target_opt is None:
                raise ValueError(f"Boarding station {boarding_station} not found in dropdown")
            await target_opt.click()

            # 5. Click Get Train Chart
            await page.locator("button:has-text('Get Train Chart')").click()

            # 6. Wait for chart table to appear
            await page.wait_for_selector("table", timeout=DEFAULT_TIMEOUT)

            # 7. Parse vacancy data from the chart table
            coaches = await self._parse_chart_table(page)

            return ChartResult(
                train_number=train_number,
                journey_date=journey_date,
                boarding_station=boarding_station.upper(),
                stations=stations,
                coaches=coaches,
            )
        finally:
            await page.close()

    async def _parse_chart_table(self, page: Page) -> List[CoachVacancy]:
        """Parse the HTML table containing coach vacancy data."""
        rows = await page.locator("table tr").all()
        coaches: List[CoachVacancy] = []
        for row in rows[1:]:  # skip header
            cells = await row.locator("td").all_inner_texts()
            if len(cells) >= 3:
                coach_num = cells[0].strip()
                class_type = cells[1].strip()
                try:
                    vacant = int(cells[2].strip())
                except ValueError:
                    vacant = 0
                coaches.append(CoachVacancy(coach_num, class_type, vacant))
        return coaches
```

- [ ] **Step 2: Write scraper tests (mock-based)**

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/tests/test_chart_scraper.py`:

```python
"""Mock-based tests for chart scraper internals."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from chart_scraper import ChartScraper


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.locator.return_value = AsyncMock()
    return page


@pytest.mark.asyncio
async def test_parse_chart_table():
    scraper = ChartScraper()
    page = MagicMock()
    row = MagicMock()
    row.locator.return_value.all_inner_texts = AsyncMock(return_value=["S1", "SL", "5"])
    page.locator.return_value.all = AsyncMock(return_value=[MagicMock(), row])
    result = await scraper._parse_chart_table(page)
    assert len(result) == 1
    assert result[0].coach_number == "S1"
    assert result[0].class_type == "SL"
    assert result[0].vacant_count == 5
```

- [ ] **Step 3: Run tests**

Run:
```bash
cd irctc-vacancy-checker
python3 -m pytest tests/test_chart_scraper.py -v
```

Expected: 1 test passing (mock-based unit test).

- [ ] **Step 4: Commit**

```bash
git add irctc-vacancy-checker/chart_scraper.py irctc-vacancy-checker/tests/test_chart_scraper.py
git commit -m "feat: add chart scraper with mock tests"
```

---

### Task 5: CLI Main Entry Point

**Files:**
- Create: `irctc-vacancy-checker/main.py`
- Test: `irctc-vacancy-checker/tests/test_main.py`

- [ ] **Step 1: Write main CLI**

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/main.py`:

```python
"""CLI entry point for IRCTC Vacancy Checker."""

import argparse
import asyncio
import sys
from typing import Dict

from config import normalize_class_type
from models import ChartResult
from chart_scraper import ChartScraper
from journey_planner import analyze_direct, analyze_split_journey, JourneyPlan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check IRCTC train seat availability")
    parser.add_argument("--train", required=True, help="Train number (e.g. 12601)")
    parser.add_argument("--from", dest="origin", required=True, help="Boarding station code (e.g. CLT)")
    parser.add_argument("--to", dest="destination", required=True, help="Destination station code (e.g. MAS)")
    parser.add_argument("--class", dest="class_type", required=True, help="Coach/class type (e.g. SL, 3A)")
    parser.add_argument("--date", required=True, help="Journey date (YYYY-MM-DD)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser headlessly")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="Show browser window")
    return parser


async def run(args) -> JourneyPlan:
    class_type = normalize_class_type(args.class_type)
    origin = args.origin.upper()
    destination = args.destination.upper()

    async with ChartScraper(headless=args.headless) as scraper:
        # 1. Fetch base chart for origin boarding station
        base_chart = await scraper.fetch_chart(
            train_number=args.train,
            journey_date=args.date,
            boarding_station=origin,
        )

        # 2. Determine intermediate stations between origin and destination
        station_codes = [s.code.upper() for s in base_chart.stations]
        try:
            from_idx = station_codes.index(origin)
            to_idx = station_codes.index(destination)
        except ValueError as exc:
            raise ValueError(f"Station not found in train route: {exc}")

        if from_idx >= to_idx:
            raise ValueError(f"Destination {destination} must come after origin {origin} on the route.")

        # 3. Fetch charts for every intermediate boarding point
        intermediate_charts: Dict[str, ChartResult] = {}
        for idx in range(from_idx + 1, to_idx):
            inter_code = base_chart.stations[idx].code
            inter_chart = await scraper.fetch_chart(
                train_number=args.train,
                journey_date=args.date,
                boarding_station=inter_code,
                stations=base_chart.stations,
            )
            intermediate_charts[inter_code] = inter_chart

        # 4. Analyze direct availability
        direct = analyze_direct(base_chart, class_type)

        # 5. Analyze split options
        splits = analyze_split_journey(base_chart, intermediate_charts, destination, class_type)

    return JourneyPlan(
        train_number=args.train,
        journey_date=args.date,
        from_station=origin,
        to_station=destination,
        class_type=class_type,
        direct=direct,
        split_options=splits,
    )


def print_plan(plan: JourneyPlan) -> None:
    print(f"\nTrain: {plan.train_number}")
    print(f"Date:  {plan.journey_date}")
    print(f"Route: {' → '.join(s.code for s in plan.direct.coach_breakdown[0].__dict__.get('stations', []))}")
    print(f"\nDIRECT AVAILABILITY ({plan.from_station} → {plan.to_station}):")
    if plan.direct.available:
        print(f"  {plan.class_type}: {plan.direct.total_seats} seats available")
        for c in plan.direct.coach_breakdown:
            print(f"    Coach {c.coach_number}: {c.vacant_count} seats")
    else:
        print(f"  No direct {plan.class_type} availability found.")

    if plan.split_options:
        print(f"\nSPLIT-JOURNEY OPTIONS:")
        for i, opt in enumerate(plan.split_options, 1):
            print(f"  Option {i}: {plan.from_station} → {opt.intermediate_station} ({opt.leg1_seats} seats)")
            print(f"           {opt.intermediate_station} → {plan.to_station} ({opt.leg2_seats} seats)")
            print(f"           → Guaranteed: {opt.total_seats} seats")
    elif not plan.direct.available:
        print("\nNo split-journey options found either.")


async def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        plan = await run(args)
        print_plan(plan)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
```

Wait — `print_plan` has a bug: `plan.direct.coach_breakdown[0].__dict__.get('stations', [])` won't work. The `JourneyPlan` doesn't carry stations. I need to fix `main.py` to also pass stations through, or redesign.

Let's add `stations` to `JourneyPlan`:

Add to `journey_planner.py` in `JourneyPlan`:
```python
    stations: List[Station] = field(default_factory=list)
```

And in `main.py` pass `stations=base_chart.stations`.

Then in `print_plan`:
```python
    route_str = " → ".join(s.code for s in plan.stations)
```

- [ ] **Step 2: Fix journey_planner.py to include stations in JourneyPlan**

Edit `journey_planner.py`, add `stations: List[Station] = field(default_factory=list)` to `JourneyPlan`.

- [ ] **Step 3: Fix print_plan in main.py**

Use `plan.stations` instead of the broken attribute access.

- [ ] **Step 4: Write main tests**

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/tests/test_main.py`:

```python
"""Tests for CLI main module."""

import pytest
from main import build_parser


def test_parser_required_args():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_valid_args():
    parser = build_parser()
    args = parser.parse_args(["--train", "12601", "--from", "CLT", "--to", "MAS", "--class", "SL", "--date", "2026-06-09"])
    assert args.train == "12601"
    assert args.origin == "CLT"
    assert args.destination == "MAS"
    assert args.class_type == "SL"
    assert args.date == "2026-06-09"
    assert args.headless is True
```

- [ ] **Step 5: Run all tests**

Run:
```bash
cd irctc-vacancy-checker
python3 -m pytest tests/ -v
```

Expected: All tests passing.

- [ ] **Step 6: Commit**

```bash
git add irctc-vacancy-checker/main.py irctc-vacancy-checker/tests/test_main.py
git commit -m "feat: add CLI entry point with tests"
```

---

### Task 6: README, Final Integration, and Smoke Test

**Files:**
- Modify: `irctc-vacancy-checker/README.md`

- [ ] **Step 1: Write README**

Write `/home/user1/ai-engineering-from-scratch/projects/irctc-vacancy-checker/README.md`:

```markdown
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
```

- [ ] **Step 2: Final lint/type check**

Run:
```bash
cd irctc-vacancy-checker
python3 -m py_compile main.py chart_scraper.py journey_planner.py models.py config.py
python3 -m pytest tests/ -v
```

Expected: No syntax errors; all tests pass.

- [ ] **Step 3: Commit**

```bash
git add irctc-vacancy-checker/README.md
git commit -m "docs: add README and finalize project"
```

---

## Spec Self-Review Checklist

1. **Spec coverage:** Every requirement from the ferment is covered:
   - Input parsing via CLI → Task 5
   - Direct availability check → Task 3
   - Split-journey logic → Task 3
   - Boarding point extraction → Task 4
   - Configurable routes → Task 4 + 5
   - Clear output → Task 5

2. **Placeholder scan:** No TBD, TODO, or incomplete sections.

3. **Type consistency:** `class_type` is normalized to canonical codes everywhere. `ChartResult.stations` list is reused across split-journey calls.

4. **Feasibility:** Each task touches 1-3 files and is independently buildable.
