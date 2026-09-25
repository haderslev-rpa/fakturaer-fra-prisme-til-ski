"""Lokale tests af ugekonfigurationen."""

from datetime import date

import period_helpers


def test_60_weeks_after_6_week_delay() -> None:
    """Kontrollér præcis 60 uger efter 6 ugers forsinkelse."""
    original_delay = (
        period_helpers.ANTAL_UGER_FORSINKELSE
    )
    original_weeks = (
        period_helpers.ANTAL_UGER_TILBAGE
    )

    try:
        period_helpers.ANTAL_UGER_FORSINKELSE = 6
        period_helpers.ANTAL_UGER_TILBAGE = 60

        date_from, date_to = (
            period_helpers.resolve_invoice_period(
                today=date(2026, 9, 25)
            )
        )

        assert date_from == date(2025, 6, 23)
        assert date_to == date(2026, 8, 16)

        number_of_days = (
            date_to
            - date_from
        ).days + 1

        assert number_of_days == 60 * 7

    finally:
        period_helpers.ANTAL_UGER_FORSINKELSE = (
            original_delay
        )
        period_helpers.ANTAL_UGER_TILBAGE = (
            original_weeks
        )


def test_one_week() -> None:
    """Kontrollér at værdien 1 giver præcis én uge."""
    original_delay = (
        period_helpers.ANTAL_UGER_FORSINKELSE
    )
    original_weeks = (
        period_helpers.ANTAL_UGER_TILBAGE
    )

    try:
        period_helpers.ANTAL_UGER_FORSINKELSE = 6
        period_helpers.ANTAL_UGER_TILBAGE = 1

        date_from, date_to = (
            period_helpers.resolve_invoice_period(
                today=date(2026, 9, 25)
            )
        )

        assert date_from == date(2026, 8, 10)
        assert date_to == date(2026, 8, 16)

    finally:
        period_helpers.ANTAL_UGER_FORSINKELSE = (
            original_delay
        )
        period_helpers.ANTAL_UGER_TILBAGE = (
            original_weeks
        )


if __name__ == "__main__":
    test_60_weeks_after_6_week_delay()
    test_one_week()

    print(
        "Alle ugekonfigurationstests er OK."
    )
