"""Duration parsing utilities."""

import re

from t87s.types import Duration

_DURATION_PATTERN = re.compile(r"^(\d+)(ms|s|m|h|d)$")
_UNITS: dict[str, int] = {
    "ms": 1,
    "s": 1000,
    "m": 60_000,
    "h": 3_600_000,
    "d": 86_400_000,
}


def parse_duration(duration: Duration) -> int:
    """Parse duration string to milliseconds. Passthrough if already int."""
    if isinstance(duration, int):
        return duration

    match = _DURATION_PATTERN.match(duration)
    if not match:
        raise ValueError(f"Invalid duration: {duration!r}")

    value, unit = match.groups()
    return int(value) * _UNITS[unit]
