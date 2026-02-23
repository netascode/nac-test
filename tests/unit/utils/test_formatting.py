# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for shared formatting utilities."""

from datetime import datetime

from nac_test.utils.formatting import format_duration, format_timestamp_ms


class TestFormatDuration:
    """Tests for format_duration utility function."""

    def test_none_returns_na(self) -> None:
        assert format_duration(None) == "N/A"

    def test_zero_returns_less_than_one(self) -> None:
        assert format_duration(0) == "< 1s"

    def test_subsecond_returns_less_than_one(self) -> None:
        assert format_duration(0.5) == "< 1s"

    def test_one_second(self) -> None:
        assert format_duration(1.0) == "1.0s"

    def test_seconds_range(self) -> None:
        assert format_duration(45.2) == "45.2s"

    def test_exactly_sixty_shows_minutes(self) -> None:
        assert format_duration(60) == "1m 0s"

    def test_minutes_range(self) -> None:
        assert format_duration(123) == "2m 3s"

    def test_exactly_one_hour(self) -> None:
        assert format_duration(3600) == "1h 0m"

    def test_hours_range(self) -> None:
        assert format_duration(7500) == "2h 5m"

    def test_integer_input(self) -> None:
        assert format_duration(30) == "30.0s"


class TestFormatTimestampMs:
    """Tests for format_timestamp_ms utility function."""

    def test_known_datetime_formats_correctly(self) -> None:
        dt = datetime(2025, 6, 27, 18, 26, 16, 834000)
        result = format_timestamp_ms(dt)
        assert result == "2025-06-27 18:26:16.834"

    def test_millisecond_precision_trims_microseconds(self) -> None:
        dt = datetime(2025, 1, 1, 0, 0, 0, 123456)
        result = format_timestamp_ms(dt)
        # strftime %f -> "123456", trim last 3 -> "123"
        assert result.endswith(".123")

    def test_none_defaults_to_now(self) -> None:
        before = datetime.now()
        result = format_timestamp_ms()
        after = datetime.now()

        # Parse back the result to verify it's between before and after
        parsed = datetime.strptime(result, "%Y-%m-%d %H:%M:%S.%f")
        assert before.replace(microsecond=0) <= parsed.replace(microsecond=0)
        assert parsed.replace(microsecond=0) <= after.replace(microsecond=0)

    def test_output_format_has_expected_length(self) -> None:
        dt = datetime(2025, 12, 31, 23, 59, 59, 999000)
        result = format_timestamp_ms(dt)
        # "YYYY-MM-DD HH:MM:SS.mmm" = 23 chars
        assert len(result) == 23
