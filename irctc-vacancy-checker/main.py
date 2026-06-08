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
        stations=base_chart.stations,
    )


def print_plan(plan: JourneyPlan) -> None:
    print(f"\nTrain: {plan.train_number}")
    print(f"Date:  {plan.journey_date}")
    route_str = " → ".join(s.code for s in plan.stations) if plan.stations else f"{plan.from_station} → {plan.to_station}"
    print(f"Route: {route_str}")
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