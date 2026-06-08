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