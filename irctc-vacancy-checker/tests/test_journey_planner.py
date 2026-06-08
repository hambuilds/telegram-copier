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