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
    stations: List[Station] = field(default_factory=list)


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