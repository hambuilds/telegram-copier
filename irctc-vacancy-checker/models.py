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