"""Tests for duration parsing."""

import pytest

from t87s import parse_duration


class TestParseDuration:
    """Tests for parse_duration function."""

    def test_milliseconds(self) -> None:
        """Test parsing milliseconds."""
        assert parse_duration("100ms") == 100
        assert parse_duration("1ms") == 1
        assert parse_duration("0ms") == 0

    def test_seconds(self) -> None:
        """Test parsing seconds."""
        assert parse_duration("1s") == 1000
        assert parse_duration("30s") == 30000
        assert parse_duration("0s") == 0

    def test_minutes(self) -> None:
        """Test parsing minutes."""
        assert parse_duration("1m") == 60_000
        assert parse_duration("5m") == 300_000
        assert parse_duration("0m") == 0

    def test_hours(self) -> None:
        """Test parsing hours."""
        assert parse_duration("1h") == 3_600_000
        assert parse_duration("2h") == 7_200_000
        assert parse_duration("0h") == 0

    def test_days(self) -> None:
        """Test parsing days."""
        assert parse_duration("1d") == 86_400_000
        assert parse_duration("7d") == 604_800_000
        assert parse_duration("0d") == 0

    def test_integer_passthrough(self) -> None:
        """Test that integers pass through unchanged."""
        assert parse_duration(1000) == 1000
        assert parse_duration(0) == 0
        assert parse_duration(999999) == 999999

    def test_invalid_format(self) -> None:
        """Test that invalid formats raise ValueError."""
        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("invalid")

        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("10x")

        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("s10")

        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("")

        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("10")
