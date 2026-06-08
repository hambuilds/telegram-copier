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