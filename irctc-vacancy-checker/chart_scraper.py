"""Playwright-based scraper for IRCTC online charts."""

import asyncio
from typing import List, Optional
from playwright.async_api import async_playwright, Page, TimeoutError

from models import Station, CoachVacancy, ChartResult
from config import IRCTC_CHARTS_URL, DEFAULT_TIMEOUT


class ChartScraper:
    def __init__(self, headless: bool = True, debug: bool = False):
        self.headless = headless
        self.debug = debug
        self._playwright = None
        self._browser = None

    async def _find_input_by_keywords(self, page: Page, keywords: list[str], timeout: int = 2_000) -> tuple:
        """Try several strategies to locate a text input.

        Returns (locator, selector_name) so the caller knows which one matched.
        Raises TimeoutError if none match.
        """
        strategies = []
        for kw in keywords:
            strategies.append((f"input[placeholder*='{kw}']", f"placeholder*='{kw}'"))
            strategies.append((f"input[placeholder*='{kw}' i]", f"placeholder*='{kw}' (case-insensitive)"))
            strategies.append((f"input[aria-label*='{kw}' i]", f"aria-label*='{kw}'"))
            strategies.append((f"mat-form-field:has-text('{kw}') input", f"mat-form-field text='{kw}'"))
            strategies.append((f"label:has-text('{kw}') + input, label:has-text('{kw}') ~ input", f"adjacent-to-label '{kw}'"))
        strategies.append(("input[type='text']", "first-text-input"))
        strategies.append(("input.p-inputtext", "primeNG-input"))
        strategies.append(("input:not([type='hidden']):visible", "any-visible-input"))

        for selector, name in strategies:
            loc = page.locator(selector).first
            try:
                await loc.wait_for(state="visible", timeout=timeout)
                return loc, name
            except TimeoutError:
                continue
        raise TimeoutError(f"Could not locate input matching keywords {keywords}")

    async def _maybe_screenshot(self, page: Page, label: str) -> None:
        if not self.debug:
            return
        prefix = f"debug_irctc_{label}"
        await page.screenshot(path=f"{prefix}.png")
        html = await page.content()
        with open(f"{prefix}.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[debug] Saved {prefix}.png and {prefix}.html")


    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-http2"]
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _new_page(self) -> Page:
        page = await self._browser.new_page()
        await page.set_extra_http_headers({
            "sec-ch-ua": '"Not.A/Brand";v="99", "Chromium";v="136"',
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
        })
        await page.goto(IRCTC_CHARTS_URL, wait_until="domcontentloaded")
        # Angular/PrimeNG apps need time to bootstrap after DOM is ready.
        # Give it up to 15 s to settle; if background connections persist
        # (common on IRCTC), just proceed — by then the UI is rendered.
        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except TimeoutError:
            pass
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
            # 1. Fill train number (React Select)
            try:
                train_input, sel_name = await self._find_input_by_keywords(
                    page, ["Train Name", "Train", "Number"]
                )
                print(f"[scraper] Found train input via strategy: {sel_name}")
            except TimeoutError:
                await self._maybe_screenshot(page, "train_input_not_found")
                raise RuntimeError("Unable to find train input on IRCTC page. Check debug_irctc_train_input_not_found.png")
            try:
                await train_input.click(force=True)
            except TimeoutError:
                pass
            await train_input.fill(train_number)
            await asyncio.sleep(0.5)
            try:
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                print(f"[scraper] Selected train via dropdown")
            except Exception:
                print("[scraper] No train dropdown appeared; proceeding anyway")

            # 2. Fill journey date (React Select or standard input)
            try:
                date_input, sel_name = await self._find_input_by_keywords(
                    page, ["Journey Date", "Date"]
                )
                print(f"[scraper] Found date input via strategy: {sel_name}")
            except TimeoutError:
                await self._maybe_screenshot(page, "date_input_not_found")
                raise RuntimeError("Unable to find journey date input on IRCTC page. Check debug_irctc_date_input_not_found.png")
            try:
                await date_input.click(force=True)
            except TimeoutError:
                pass
            await date_input.fill(journey_date)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)

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