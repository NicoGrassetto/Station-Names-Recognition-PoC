"""Pure domain object for an in-progress booking.

``BookingSession`` is the form being filled in during a conversation. It is
intentionally free of transport / framework concerns (no WebSocket, no
Azure SDK, no FastAPI imports) so it can be unit-tested, serialized, and
reused independently of how the data is collected.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger("booking")

Language = Literal["French", "English", "Flemish", "Dutch", "German"]
AgeCategory = Literal["child", "youth", "adult", "senior"]
TravelClass = Literal[1, 2]


class BookingSession:
    # Sentinel used to suppress logging during __init__.
    _initialized: bool = False

    def __init__(self) -> None:
        self.arrival_station: str | None = None
        self.departure_station: str = "Waremme"
        self.language: Language | None = None
        self.mini_group: bool = False
        self.train_plus: bool = False
        self.bicycle: bool = False
        self.season_ticket: bool | None = None
        self.city_pass: bool | None = None
        self.bru_pass: bool | None = None
        self.age: int | None = None
        self.travel_class: TravelClass = 2
        # Flip the sentinel last so subsequent mutations are logged.
        object.__setattr__(self, "_initialized", True)
        logger.info("BookingSession created %s", self.snapshot())

    def __setattr__(self, name: str, value: Any) -> None:
        old = getattr(self, name, "<unset>") if self._initialized else "<init>"
        object.__setattr__(self, name, value)
        if self._initialized and old != value:
            logger.info("BookingSession.%s : %r -> %r", name, old, value)

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-friendly view of all booking fields."""
        return {
            "arrival_station": self.arrival_station,
            "departure_station": self.departure_station,
            "language": self.language,
            "mini_group": self.mini_group,
            "train_plus": self.train_plus,
            "bicycle": self.bicycle,
            "season_ticket": self.season_ticket,
            "city_pass": self.city_pass,
            "bru_pass": self.bru_pass,
            "age": self.age,
            "age_category": self.age_category,
            "travel_class": self.travel_class,
        }

    @property
    def age_category(self) -> AgeCategory | None:
        """Map ``age`` to an NMBS-style fare category.

        - child  : 0–11
        - youth  : 12–25
        - adult  : 26–64
        - senior : 65+
        """
        if self.age is None or self.age < 0:
            return None
        if self.age <= 11:
            return "child"
        if self.age <= 25:
            return "youth"
        if self.age <= 64:
            return "adult"
        return "senior"
