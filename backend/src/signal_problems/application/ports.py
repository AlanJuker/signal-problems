import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import astuple, dataclass
from typing import Protocol

from signal_problems.domain.delays import Delay
from signal_problems.domain.surface import SurfaceDelay


@dataclass(frozen=True, slots=True)
class RawDelayRow:
    """One row of the TTC subway delay log, exactly as published."""

    date: str
    time: str
    station: str
    line: str
    code: str
    min_delay: str
    min_gap: str
    bound: str
    vehicle: str

    @property
    def fingerprint(self) -> str:
        """Content-based key.

        The portal's `_id` is a datastore row number, which isn't guaranteed to stay the same when
        the whole file is re-published each month.
        """
        return hashlib.sha256("|".join(astuple(self)).encode()).hexdigest()[:32]


class DelaySource(Protocol):
    def fetch(self) -> Iterable[RawDelayRow]: ...


class DelayRepository(Protocol):
    def add_new(self, delays: Sequence[Delay]) -> int:
        """Store delays whose fingerprint isn't stored yet. Returns how many were inserted."""
        ...


class SurfaceDelayRepository(Protocol):
    def add_new(self, delays: Sequence[SurfaceDelay]) -> int:
        """Store delays whose fingerprint isn't stored yet. Returns how many were inserted."""
        ...
