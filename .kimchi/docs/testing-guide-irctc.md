# Beginner's Guide: Testing IRCTC Vacancy Checker

A step-by-step guide for absolute beginners who have never run Python tests before.

---

## Table of Contents
1. [Before You Start — What You Need](#before-you-start--what-you-need)
2. [Step 1: Open Your Terminal](#step-1-open-your-terminal)
3. [Step 2: Navigate to the Project Folder](#step-2-navigate-to-the-project-folder)
4. [Step 3: Install What's Needed](#step-3-install-whats-needed)
5. [Step 4: Run the Tests](#step-4-run-the-tests)
6. [Step 5: Read the Results](#step-5-read-the-results)
7. [Common Errors & How to Fix Them](#common-errors--how-to-fix-them)
8. [What Each Test File Actually Tests](#what-each-test-file-actually-tests)

---

## Before You Start — What You Need

You only need **two** things already installed on your computer:

| Requirement | How to Check | If Missing |
|-------------|-------------|------------|
| **Python 3.10 or newer** | Run: `python3 --version` | [Download here](https://www.python.org/downloads/) |
| **pip** (Python's package installer) | Run: `pip3 --version` | Comes with Python 3.4+ |

> **Tip:** On Windows, you might use `py` instead of `python3`. On some Linux systems, it might just be `python`. Try all three if one doesn't work.

---

## Step 1: Open Your Terminal

Your terminal is the text-based command window on your computer.

| Operating System | How to Open |
|------------------|-------------|
| **macOS** | Press `Cmd + Space`, type `Terminal`, press Enter |
| **Linux** | Press `Ctrl + Alt + T` or search for "Terminal" |
| **Windows** | Press `Win + R`, type `cmd`, press Enter (or use PowerShell) |

---

## Step 2: Navigate to the Project Folder

You need to tell the terminal to work inside the project folder. This is like opening a folder in File Explorer.

### Find the project folder path

The project lives in a folder called `irctc-vacancy-checker`. If you're unsure where it is, run this in your terminal:

```bash
# macOS / Linux
find ~ -type d -name "irctc-vacancy-checker" 2>/dev/null

# Windows (Command Prompt)
dir /s /b %USERPROFILE%\irctc-vacancy-checker

# Windows (PowerShell)
Get-ChildItem -Path $env:USERPROFILE -Recurse -Filter "irctc-vacancy-checker" -Directory
```

### Move into the folder

Once you know the path, run:

```bash
cd /path/to/irctc-vacancy-checker
```

**Example:** If the project is on your Desktop:
```bash
# macOS / Linux
cd ~/Desktop/irctc-vacancy-checker

# Windows
cd C:\Users\YourName\Desktop\irctc-vacancy-checker
```

**Verify you're in the right place:**
```bash
ls        # macOS / Linux

dir       # Windows
```

You should see files like `main.py`, `models.py`, `config.py`, and a `tests/` folder.

---

## Step 3: Install What's Needed

Python projects often need extra "packages" (small tools written by others). This project needs `pytest` (the test runner) and a few helper packages.

### Option A: Install from requirements.txt (Recommended)

Running this one command installs everything at once:

```bash
pip3 install -r requirements.txt
```

You should see output ending with something like `Successfully installed pytest-9.0.3 ...`.

### Option B: Install manually

If `requirements.txt` doesn't work, install the essentials directly:

```bash
pip3 install pytest pytest-asyncio playwright
```

### Verify pytest is installed

```bash
python3 -m pytest --version
```

Expected output (the exact version number may differ):
```
pytest 9.0.3
```

> **Note:** `python3 -m pytest` means "use Python to run the pytest module." It's more reliable than just typing `pytest` because it guarantees you're using the pytest tied to your current Python installation.

---

## Step 4: Run the Tests

Now for the main event! There are **two** commands you can use. Try the first one; if it fails, use the second.

### Command 1 — The Simple Way

```bash
python3 -m pytest tests/ -v
```

If you see **"No tests collected"**, that means Python can't find the project's own code files. Jump to **Command 2**.

### Command 2 — If Command 1 Fails

Python needs to know where the code files live. We tell it by setting a variable called `PYTHONPATH`:

**macOS / Linux:**
```bash
PYTHONPATH=$(pwd) python3 -m pytest tests/ -v
```

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH="$(Get-Location)"; python3 -m pytest tests/ -v
```

**Windows (Command Prompt):**
```cmd
set PYTHONPATH=%CD% && python3 -m pytest tests/ -v
```

> **What is `PYTHONPATH`?** It's just a list of folders where Python looks for code. `$(pwd)` (macOS/Linux) and `%CD%` (Windows) mean "the folder I'm currently in."

---

## Step 5: Read the Results

When tests pass, you see something like this:

```
========================= test session starts ==========================
platform linux -- Python 3.14.0, pytest-9.0.3, pluggy-1.5.0
rootdir: /home/user/irctc-vacancy-checker
collected 12 items

tests/test_models.py::test_station_repr PASSED                    [  8%]
tests/test_models.py::test_chart_vacant_for_class PASSED          [ 16%]
tests/test_models.py::test_normalize_class_type PASSED             [ 25%]
tests/test_models.py::test_normalize_class_type_invalid PASSED     [ 33%]
tests/test_journey_planner.py::test_find_station_index PASSED     [ 41%]
tests/test_journey_planner.py::test_analyze_direct_available PASSED [ 50%]
tests/test_journey_planner.py::test_analyze_direct_unavailable PASSED [ 58%]
tests/test_journey_planner.py::test_analyze_split_journey_found PASSED [ 66%]
tests/test_journey_planner.py::test_analyze_split_journey_none PASSED [ 75%]
tests/test_journey_planner.py::test_analyze_split_journey_none PASSED [ 83%]
tests/test_main.py::test_parser_required_args PASSED             [ 91%]
tests/test_main.py::test_parser_valid_args PASSED                [100%]
tests/test_chart_scraper.py::test_parse_chart_table PASSED       [100%]

========================== 12 passed in 0.05s ==========================
```

### What those lines mean

| Part | Meaning |
|------|---------|
| `collected 12 items` | pytest found 12 tests total |
| `tests/test_models.py::test_station_repr` | The file `tests/test_models.py` has a test called `test_station_repr` |
| `PASSED` | That test ran without any problems |
| `12 passed in 0.05s` | All done! Every test succeeded in 0.05 seconds |

### What if a test fails?

A failure looks like this:

```
tests/test_models.py::test_station_repr FAILED
```

When a test fails, pytest prints a detailed **traceback** (a list of which line failed and why). Read the error message — it usually tells you exactly what went wrong.

---

## Common Errors & How to Fix Them

| Error Message | What It Means | How to Fix |
|---------------|---------------|------------|
| `ModuleNotFoundError: No module named 'pytest'` | pytest isn't installed | Run `pip3 install pytest pytest-asyncio` |
| `Pytest: No tests collected` | Python can't find the code files | Add `PYTHONPATH=$(pwd)` before the command (see Step 4, Command 2) |
| `ModuleNotFoundError: No module named 'models'` | Same as above — path issue | Same fix: use `PYTHONPATH` |
| `ImportError: cannot import name 'X' from 'models'` | The code file `models.py` was changed and the test references something that no longer exists | Check if you edited `models.py` recently; the test might need updating |
| `AssertionError: assert 5 == 3` | The test expected one number but got another | The code logic has a bug — look at which test failed and trace the logic |
| `playwright` errors on chart scraper tests | Playwright browser binaries aren't installed | Run `playwright install chromium` |

---

## What Each Test File Actually Tests

Here's a friendly summary of what the 12 tests verify:

### `test_models.py` — "Does the data make sense?"
- **test_station_repr** — Checks that a station prints nicely (e.g., `CLT (Kozhikode)`)
- **test_chart_vacant_for_class** — Checks that we can count empty seats per coach type
- **test_normalize_class_type** — Checks that `"sleeper"` gets turned into `"SL"`
- **test_normalize_class_type_invalid** — Checks that `"XX"` causes an error (as it should)

### `test_journey_planner.py` — "Does the journey planner logic work?"
- **test_find_station_index** — Checks that we can find where a station sits in a route list
- **test_analyze_direct_available** — Checks direct journey when seats ARE available
- **test_analyze_direct_unavailable** — Checks direct journey when seats are NOT available
- **test_analyze_split_journey_found** — Checks split-journey finds a valid middle station
- **test_analyze_split_journey_none** — Checks split-journey correctly reports "no options"

### `test_main.py` — "Does the command-line tool accept the right arguments?"
- **test_parser_required_args** — Checks the program complains if you forget `--train`, `--from`, etc.
- **test_parser_valid_args** — Checks the program accepts a full, correct command

### `test_chart_scraper.py` — "Does the web scraper parse data correctly?"
- **test_parse_chart_table** — Uses a **mock** (a fake version of a web page) to test parsing table data

> **About the scraper test:** It doesn't actually visit any website! It creates a fake "page" object so the test is fast and doesn't need an internet connection.

---

## Quick Reference — All Commands in One Place

### One-Time Setup
```bash
cd /path/to/irctc-vacancy-checker
pip3 install -r requirements.txt
```

### Run Tests (Every Time)

**macOS / Linux:**
```bash
cd /path/to/irctc-vacancy-checker
PYTHONPATH=$(pwd) python3 -m pytest tests/ -v
```

**Windows (PowerShell):**
```powershell
cd C:\path\to\irctc-vacancy-checker
$env:PYTHONPATH="$(Get-Location)"; python3 -m pytest tests/ -v
```

**Windows (Command Prompt):**
```cmd
cd C:\path\to\irctc-vacancy-checker
set PYTHONPATH=%CD% && python3 -m pytest tests/ -v
```
