"""Lokale tests af inklusive ugeintervaller uden API-kald."""

from datetime import date

from week_helpers import iter_week_intervals


def test_period_end_is_inclusive() -> None:
    """Kontrollér at slutdatoen bliver medtaget."""
    intervals = list(
        iter_week_intervals(
            date(2027, 2, 28),
            date(2027, 2, 28),
        )
    )

    assert intervals == [
        (
            date(2027, 2, 28),
            date(2027, 3, 1),
            "uge 8 - 2027",
        )
    ]


if __name__ == "__main__":
    test_period_end_is_inclusive()
    print(
        "Alle uge-tests er OK."
    )
