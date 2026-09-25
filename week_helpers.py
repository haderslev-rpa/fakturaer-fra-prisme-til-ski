"""Hjælpefunktioner til ISO-uger og sikker oprydning."""

from __future__ import annotations

from datetime import date
from datetime import timedelta
from pathlib import Path
import re
import shutil
from typing import Iterator


WEEK_NAME_PATTERN = re.compile(
    r"^uge ([1-9]|[1-4][0-9]|5[0-3]) - ([0-9]{4})(?:\.zip)?$"
)


def iter_week_intervals(
    date_from: date,
    date_to: date,
) -> Iterator[tuple[date, date, str]]:
    """Returnér ugeintervaller for en inklusiv periode.

    Outputtets slutdato er eksklusiv, så API-kald kan bruge:

        dato ge interval_fra
        dato lt interval_til
    """
    if not isinstance(
        date_from,
        date,
    ):
        raise TypeError(
            "date_from skal være en date-værdi."
        )

    if not isinstance(
        date_to,
        date,
    ):
        raise TypeError(
            "date_to skal være en date-værdi."
        )

    if date_from > date_to:
        raise ValueError(
            "date_from må ikke være efter date_to."
        )

    end_exclusive = (
        date_to
        + timedelta(
            days=1
        )
    )

    current_date = date_from

    while current_date < end_exclusive:
        iso_calendar = (
            current_date.isocalendar()
        )

        next_monday = (
            current_date
            + timedelta(
                days=(
                    8
                    - current_date.isoweekday()
                )
            )
        )

        interval_to = min(
            next_monday,
            end_exclusive,
        )

        reference = (
            f"uge {iso_calendar.week} "
            f"- {iso_calendar.year}"
        )

        yield (
            current_date,
            interval_to,
            reference,
        )

        current_date = interval_to


def allowed_references(
    date_from: date,
    date_to: date,
) -> set[str]:
    """Returnér alle tilladte uge-referencer."""
    return {
        reference
        for _, _, reference in iter_week_intervals(
            date_from,
            date_to,
        )
    }


def cleanup_old_week_artifacts(
    root_folder: Path,
    allowed: set[str],
) -> list[Path]:
    """Slet kun processtyrede ugefiler uden for perioden."""
    root_path = Path(
        root_folder
    )

    root_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    deleted_paths: list[Path] = []

    for path in root_path.iterdir():
        if not WEEK_NAME_PATTERN.fullmatch(
            path.name
        ):
            continue

        reference = (
            path.stem
            if path.suffix.casefold() == ".zip"
            else path.name
        )

        if reference in allowed:
            continue

        if path.is_dir():
            shutil.rmtree(
                path
            )
        else:
            path.unlink()

        deleted_paths.append(
            path
        )

    return deleted_paths
