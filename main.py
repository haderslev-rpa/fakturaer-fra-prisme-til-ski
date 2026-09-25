"""Automation Server-proces til ugeopdelte OIOUBL-fakturaer."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from pprint import pprint
import sys

from automation_server_client import AutomationServer
from automation_server_client import WorkItemError
from q_haderslev_vbo.automation_server.ats_is_item_in_queue import (
    is_item_in_queue,
)
from q_haderslev_vbo.automation_server.ats_update_item_data import (
    update_item_data,
)
from q_prisme365_api.api_client import initialiser_prisme

from behandel import behandel_item
from configuration import EFFECTIVE_FAKTURA_TEMP_ROOT
from configuration import FAKTURADATO_FRA
from configuration import FAKTURADATO_TIL
from configuration import PRISME_CREDENTIAL_NAME
from data_collection import build_queue_payloads
from data_collection import collect_all_week_data
from models import WeekInterval
from week_helpers import allowed_references
from week_helpers import cleanup_old_week_artifacts
from week_helpers import iter_week_intervals


# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s [%(levelname)s] "
        "%(name)s: %(message)s"
    ),
)

logging.getLogger(
    "httpx"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "automation_server_client"
).setLevel(
    logging.WARNING
)

# API-klienten logger ellers hvert enkelt GET-kald på INFO.
logging.getLogger(
    "q_prisme365_api.api_client"
).setLevel(
    logging.WARNING
)

logger = logging.getLogger(
    __name__
)


# ------------------------------------------------------------
# QUEUE-MODE
# ------------------------------------------------------------

async def populate_queue(
    workqueue,
    debug: bool,
) -> None:
    """Opret ét queue-item pr. manglende ISO-uge.

    Procesrækkefølgen er:

    1. Find alle uge-referencer, der mangler i køen.
    2. Hent tre datalister pr. manglende uge.
    3. Match alle lister lokalt på tværs af uger.
    4. Udfør præcise fallback-kald for manglende match.
    5. Opret uge-items i ATS-køen.
    """
    logger.info(
        "Populate queue mode startet "
        "(debug=%s)",
        debug,
    )

    if workqueue.id is None:
        raise RuntimeError(
            "Workqueuen mangler id."
        )

    missing_intervals = _find_missing_intervals(
        workqueue
    )

    if not missing_intervals:
        logger.info(
            "Alle uge-referencer findes allerede i køen."
        )
        return

    initialiser_prisme(
        credential_name=(
            PRISME_CREDENTIAL_NAME
        )
    )

    logger.info(
        "Henter først alle API-data for %s "
        "manglende uge(r).",
        len(
            missing_intervals
        ),
    )

    week_data = collect_all_week_data(
        missing_intervals
    )

    logger.info(
        "Alle ugeudtræk er hentet. "
        "Starter lokal Python-matchning."
    )

    queue_payloads = build_queue_payloads(
        week_data
    )

    for interval in missing_intervals:
        files, statistics = queue_payloads[
            interval.reference
        ]

        interval_to_inclusive = (
            interval.date_to_exclusive
            - timedelta(
                days=1
            )
        )

        iso_calendar = (
            interval.date_from.isocalendar()
        )

        data_json: dict = {}

        update_item_data(
            data_json,
            box_updates={
                "reference": interval.reference,
                "uge": iso_calendar.week,
                "aar": iso_calendar.year,
                "periode_fra": (
                    interval.date_from.isoformat()
                ),
                "periode_til": (
                    interval_to_inclusive.isoformat()
                ),
                "fakturaer": files,
                "statistik": statistics,
            },
            update=False,
        )

        workqueue.add_item(
            data=data_json,
            reference=interval.reference,
        )

        logger.info(
            "Item med reference %r er tilføjet "
            "med %s fil(er).",
            interval.reference,
            len(
                files
            ),
        )


def _find_missing_intervals(
    workqueue,
) -> list[WeekInterval]:
    """Find ugeintervaller, der ikke allerede findes i køen."""
    missing_intervals: list[WeekInterval] = []

    for (
        interval_from,
        interval_to_exclusive,
        item_reference,
    ) in iter_week_intervals(
        FAKTURADATO_FRA,
        FAKTURADATO_TIL,
    ):
        item_exists = is_item_in_queue(
            queue_id=workqueue.id,
            item_reference=item_reference,
            new=True,
            in_progress=True,
            completed=True,
            failed=True,
            pending_user_action=True,
        )

        if item_exists:
            logger.info(
                "Springer over: Item med reference "
                "%r findes allerede i køen.",
                item_reference,
            )
            continue

        missing_intervals.append(
            WeekInterval(
                date_from=interval_from,
                date_to_exclusive=(
                    interval_to_exclusive
                ),
                reference=item_reference,
            )
        )

    return missing_intervals


# ------------------------------------------------------------
# PROCESS-MODE
# ------------------------------------------------------------

async def process_workqueue(
    workqueue,
    debug: bool,
) -> None:
    """Behandl køens uge-items uden Playwright."""
    logger.info(
        "Process workqueue mode startet "
        "(debug=%s)",
        debug,
    )

    allowed = allowed_references(
        FAKTURADATO_FRA,
        FAKTURADATO_TIL,
    )

    deleted_paths = cleanup_old_week_artifacts(
        EFFECTIVE_FAKTURA_TEMP_ROOT,
        allowed,
    )

    for deleted_path in deleted_paths:
        logger.info(
            "Slettede gammel procesfil "
            "eller mappe: %s",
            deleted_path,
        )

    for item in workqueue:
        with item:
            data = item.data

            try:
                print(
                    "=" * 36
                    + " NEXT ITEM "
                    + "=" * 36
                )

                pprint(
                    data
                )

                behandel_item(
                    item
                )

                update_item_data(
                    data,
                    item=item,
                    status="Completed",
                    status_code="Færdig",
                    state="Completed",
                )

                item.update(
                    data
                )

                item.complete(
                    "Completed"
                )

            except WorkItemError as error:
                logger.error(
                    "WorkItemError for item %s: %s",
                    item.reference,
                    error,
                )

                item.fail(
                    str(
                        error
                    )
                )

            except Exception:
                logger.exception(
                    "Uventet fejl for item %s",
                    item.reference,
                )
                raise


# ------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------

if __name__ == "__main__":
    DEBUG = (
        "--debug"
        in sys.argv
    )

    QUEUE_MODE = (
        "--queue"
        in sys.argv
    )

    automation_server = (
        AutomationServer.from_environment()
    )

    workqueue = (
        automation_server.workqueue()
    )

    if QUEUE_MODE:
        asyncio.run(
            populate_queue(
                workqueue,
                debug=DEBUG,
            )
        )
        sys.exit(
            0
        )

    asyncio.run(
        process_workqueue(
            workqueue,
            debug=DEBUG,
        )
    )
