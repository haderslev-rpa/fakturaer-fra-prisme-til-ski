"""Beregning af processens automatiske fakturaperiode."""

from __future__ import annotations

from datetime import date
from datetime import timedelta

from configuration import ANTAL_UGER_FORSINKELSE
from configuration import ANTAL_UGER_TILBAGE


def resolve_invoice_period(
    today: date | None = None,
) -> tuple[date, date]:
    """Beregn den inklusive fakturaperiode ud fra dags dato.

    Beregningen følger denne rækkefølge:

    1. Find mandagen i den aktuelle ISO-uge.
    2. Gå ANTAL_UGER_FORSINKELSE hele uger tilbage.
    3. Denne uges mandag og søndag er den seneste uge,
       som processen må behandle.
    4. Gå ANTAL_UGER_TILBAGE minus én uge yderligere tilbage
       for at finde periodens første mandag.

    ANTAL_UGER_TILBAGE inkluderer slutugen. Hvis værdien er 60,
    returneres derfor præcis 60 komplette ISO-uger.

    Args:
        today:
            Valgfri beregningsdato til test.
            Standard er serverens dags dato.

    Returns:
        En tuple med to inklusive datoer:

            (
                fakturadato_fra,
                fakturadato_til,
            )

        fakturadato_fra er altid en mandag.
        fakturadato_til er altid en søndag.
    """
    calculation_date = (
        today
        if today is not None
        else date.today()
    )

    if not isinstance(
        calculation_date,
        date,
    ):
        raise TypeError(
            "today skal være en date-værdi."
        )

    _validate_week_configuration()

    current_week_monday = (
        calculation_date
        - timedelta(
            days=(
                calculation_date.isoweekday()
                - 1
            )
        )
    )

    latest_allowed_week_monday = (
        current_week_monday
        - timedelta(
            weeks=ANTAL_UGER_FORSINKELSE
        )
    )

    period_to_inclusive = (
        latest_allowed_week_monday
        + timedelta(
            days=6
        )
    )

    period_from_inclusive = (
        latest_allowed_week_monday
        - timedelta(
            weeks=(
                ANTAL_UGER_TILBAGE
                - 1
            )
        )
    )

    return (
        period_from_inclusive,
        period_to_inclusive,
    )


def _validate_week_configuration() -> None:
    """Kontrollér de to ugeindstillinger."""
    if isinstance(
        ANTAL_UGER_FORSINKELSE,
        bool,
    ):
        raise TypeError(
            "ANTAL_UGER_FORSINKELSE skal være et heltal."
        )

    if not isinstance(
        ANTAL_UGER_FORSINKELSE,
        int,
    ):
        raise TypeError(
            "ANTAL_UGER_FORSINKELSE skal være et heltal."
        )

    if ANTAL_UGER_FORSINKELSE < 0:
        raise ValueError(
            "ANTAL_UGER_FORSINKELSE må ikke være negativ."
        )

    if isinstance(
        ANTAL_UGER_TILBAGE,
        bool,
    ):
        raise TypeError(
            "ANTAL_UGER_TILBAGE skal være et heltal."
        )

    if not isinstance(
        ANTAL_UGER_TILBAGE,
        int,
    ):
        raise TypeError(
            "ANTAL_UGER_TILBAGE skal være et heltal."
        )

    if ANTAL_UGER_TILBAGE <= 0:
        raise ValueError(
            "ANTAL_UGER_TILBAGE skal være større end 0."
        )
