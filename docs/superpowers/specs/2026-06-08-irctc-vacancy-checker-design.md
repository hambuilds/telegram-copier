# IRCTC Vacancy Checker — Design Document

> **Date:** 2026-06-08  
> **Goal:** Build a Python CLI tool that automates the IRCTC online-charts page to check direct and split-journey seat availability for a given train, route, and coach class.

## User Requirements

1. **Input:** train number, boarding station code, destination station code, coach/class type (Sleeper, 3AC, 3AC Economy, etc.)
2. **Check DIRECT ticket availability** from boarding point to destination.
3. **Check SPLIT-JOURNEY options:** if no direct ticket, find intermediate stations where two separate tickets could be booked (e.g., B→C and C→F).
4. **Account for multiple boarding points** (A, B, C, D, E, F) along the train route.
5. **Configurable** for different train routes and station codes.
6. **Output** clearly shows available options (direct or split) with seat counts.

## Architecture

### High-level Flow

```
CLI args → Validate inputs → Open IRCTC charts page →
  Select train + date → Extract all stops from boarding dropdown →
  For each relevant boarding point:
    Select boarding point → Get chart → Parse vacancy per coach →
  Run journey planner → Output results
```

### Key Discovery

When the **Train** and **Journey Date** fields are populated on `https://www.irctc.co.in/online-charts/`, the **Boarding Station** dropdown automatically populates with **all stops** for that train on that date. This means we can extract the complete ordered route for any train in a single page interaction, eliminating the need for a separate route-scraping module.

### Components

| Component | Responsibility |
|-----------|---------------|
| `main.py` | CLI argument parsing, input validation, orchestration, formatted output |
| `chart_scraper.py` | Playwright-based browser automation for the IRCTC online-charts page. Handles form fill, chart retrieval, HTML parsing, and station-list extraction from the boarding dropdown. |
| `journey_planner.py` | Pure logic module. Takes structured chart data and computes direct availability and all valid split-journey options. |
| `config.py` | Default constants (URL, timeouts, class-type mappings) |

### Data Model

```python
@dataclass
class Station:
    code: str          # e.g., "CLT"
    name: str          # e.g., "Kozhikode"

@dataclass
class CoachVacancy:
    coach_number: str  # e.g., "S1", "B3"
    class_type: str    # e.g., "SL", "3A"
    vacant_count: int

@dataclass
class ChartResult:
    train_number: str
    journey_date: str
    boarding_station: str
    stations: list[Station]      # all stops for this train
    coaches: list[CoachVacancy]  # vacancy data from chart
```

### Journey Planner Logic

1. **Direct Check:**  
   Look at the chart for boarding station `B`. If any coach of the requested `class_type` has `vacant_count > 0`, direct is available. Report the total vacant seats across all matching coaches.

2. **Split-Journey Check:**  
   Using the ordered `stations` list from the chart scraper:
   - Iterate each intermediate station `C` that lies strictly between `B` and `F`.
   - For each `C`, fetch the chart with boarding station `C`.
   - Check `B→C` availability from chart `B`.
   - Check `C→F` availability from chart `C`.
   - If both have >0 seats, record as a valid split option: `B→C` + `C→F` with seat counts.

> **Performance note:** Split-journey analysis requires `(N-1)` chart fetches where `N` is the number of intermediate stations. This is bound by the number of stops and is acceptable for a CLI tool.

### Browser Automation Strategy (Playwright)

- Navigate to `https://www.irctc.co.in/online-charts/`
- Fill **Train Name/Number** (typeahead dropdown → select)
- Fill **Journey Date** (date picker)
- Wait for **Boarding Station** dropdown to populate
- **Extract** all `<option>` values to get the full route
- Select the desired boarding station
- Click **Get Train Chart**
- Wait for chart table to load
- Parse the HTML table into `ChartResult`

### Error Handling

| Error | Behavior |
|-------|----------|
| Invalid train number | Report error; suggest checking train number |
| Chart not yet prepared | Report "Chart not available"; suggest checking closer to departure |
| Network timeout | Retry once with exponential backoff; then fail |
| No valid split found | Report "No direct or split availability found" |

### CLI Interface

```bash
python main.py \
  --train 12601 \
  --from CLT \
  --to MAS \
  --class SL \
  --date 2026-06-09 \
  [--headless]
```

**Output format (terminal):**
```
Train: 12601 (Mangalore Mail)
Date:  2026-06-09
Route: CLT → TCR → ERS → ALLP → KYJ → QLN → TEN → MDU → DG → TPJ → ALU → MAS

DIRECT AVAILABILITY (CLT → MAS):
  Sleeper (SL): 12 seats available
  (Coaches: S1=4, S2=3, S3=5)

SPLIT-JOURNEY OPTIONS:
  Option 1: CLT → TCR (S1=2) + TCR → MAS (S1=8)  → Total 10 seats
  Option 2: CLT → ERS (S1=2) + ERS → MAS (S1=6)  → Total  8 seats
```

## Technology Stack

- **Python 3.10+**
- **Playwright** (`playwright`) — browser automation
- **Argparse** — built-in CLI
- **Dataclasses** — built-in data structures

## Testing Strategy

- Unit tests for `journey_planner.py` using mocked `ChartResult` data (no browser required).
- Integration/smoke test for `chart_scraper.py` against a local Playwright session (optional; may be gated by IRCTC anti-bot measures).
- End-to-end test for `main.py` using mocked scraper outputs.

## Open Questions Resolved

- **Train route source:** Extracted dynamically from the boarding-station dropdown on the charts page (validated by user).
- **Journey date:** Required CLI argument (`--date`); no default.
- **Destination-specific availability:** Since the chart for boarding station `B` shows vacant berths from `B` onward, a vacant berth in coach S1 on chart `B` is valid for any destination after `B`. Destination-specific filtering is handled by logic, not by the page.
