from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


STATS_TIMEZONE = ZoneInfo("Europe/Copenhagen")


@dataclass(frozen=True)
class StatPeriod:
    year: int

    @property
    def timestamps(self) -> tuple[int, int]:
        """Calendar years include January 1 and exclude the next January 1."""
        return (
            int(datetime(self.year, 1, 1, tzinfo=STATS_TIMEZONE).timestamp()),
            int(datetime(self.year + 1, 1, 1, tzinfo=STATS_TIMEZONE).timestamp()),
        )

    @classmethod
    def from_token(cls, token: str):
        if token.lower() == "year":
            return cls(datetime.now(STATS_TIMEZONE).year)
        if len(token) == 4 and token.isascii() and token.isdigit():
            year = int(token)
            if not 1 <= year < 9999:
                raise ValueError("Choose a year between 0001 and 9998.")
            return cls(year)
        return None
