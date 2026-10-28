from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from signal_problems.domain.lines import Line
from signal_problems.domain.stations import Station

# ponytail: a flat average stop-to-stop time. Per-segment run times from the TTC's GTFS feed would
# make the window tighter for long trips.
MINUTES_PER_STOP = 2
# A delay that starts shortly before you reach the platform still holds your train.
MARGIN_MINUTES = 15


@dataclass(frozen=True, slots=True)
class Trip:
    line: Line
    stations: tuple[Station, ...]
    weekday: int  # Monday = 0
    departure: time

    def window(self) -> tuple[time, time]:
        """Times of day during which a delay on this trip's stations would affect it."""
        # Any date works; it only has to leave room on both sides of midnight.
        day = date(2000, 1, 2)
        depart = datetime.combine(day, self.departure)
        travel = timedelta(minutes=MINUTES_PER_STOP * (len(self.stations) - 1))
        margin = timedelta(minutes=MARGIN_MINUTES)
        start = max(depart - margin, datetime.combine(day, time.min))
        end = min(depart + travel + margin, datetime.combine(day, time.max))
        return start.time(), end.time()

    def affects(self, moment: datetime) -> bool:
        start, end = self.window()
        return moment.weekday() == self.weekday and start <= moment.time() <= end

    def hours_covered(self) -> list[tuple[int, float]]:
        """Each hour of the day the window touches, with the share of that hour inside it."""
        start, end = self.window()
        first, last = start.hour * 60 + start.minute, end.hour * 60 + end.minute
        return [
            (hour, (min(last, hour * 60 + 60) - max(first, hour * 60)) / 60)
            for hour in range(start.hour, end.hour + 1)
        ]


def chance_of_any(cells: Iterable[tuple[float, float]]) -> float:
    """Chance of at least one delay, from each cell's hourly probability and the share of that
    hour the trip spends in it, assuming delays are spread evenly within an hour.

    ponytail: cells are treated as independent. Network-wide disruptions hit several stations at
    once, so this overstates the chance a little; a model of whole trips would fix it.
    """
    none = 1.0
    for probability, share in cells:
        none *= (1 - probability) ** share
    return 1 - none


@dataclass(frozen=True, slots=True)
class CommuteRisk:
    days_observed: int  # how many of that weekday the data covers
    days_hit: int  # of those, days with at least one 5+ minute delay on the trip

    @property
    def share(self) -> float:
        return self.days_hit / self.days_observed if self.days_observed else 0.0


def count_weekdays(first: date, last: date, weekday: int) -> int:
    """How many times `weekday` occurs between two dates, both included."""
    if last < first:
        return 0
    offset = (weekday - first.weekday()) % 7
    return 0 if offset > (last - first).days else ((last - first).days - offset) // 7 + 1
