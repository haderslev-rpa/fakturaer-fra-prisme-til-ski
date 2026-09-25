"""Hent alle API-data først og match derefter lokalt."""

from __future__ import annotations

from datetime import date
from datetime import timedelta
from decimal import Decimal
from decimal import InvalidOperation
import logging
from typing import Any
from typing import Callable

from q_prisme365_api.functionality.dokumenter import (
    get_dokumentinformation,
    hent_dokumentreferencer,
    search_dokumenter,
)
from q_prisme365_api.functionality.kreditorfakturaer import (
    hent_kreditorfakturaer,
    hent_oprindelige_fakturaposter,
)

from configuration import DATA_AREA_ID
from configuration import DOKUMENTTYPER
from configuration import DOMAIN_SUFFIX
from configuration import PRISME_TOP
from configuration import VOUCHER_PREFIX
from models import WeekData
from models import WeekInterval


logger = logging.getLogger(
    __name__
)


def collect_all_week_data(
    intervals: list[WeekInterval],
) -> list[WeekData]:
    """Hent tre API-lister for alle manglende uger.

    Alle kald udføres før matchningen starter:

    1. VendTrans pr. uge.
    2. VendInvoiceInfo pr. uge.
    3. DocuRef pr. uge.

    Hvis et ugeudtræk rammer API-grænsen på 10.000 rækker,
    opdeles kun dette udtræk automatisk i mindre datointervaller.

    Output er én WeekData pr. uge.
    """
    week_data: list[WeekData] = []

    for interval in intervals:
        logger.info(
            "Henter tre datalister for %s",
            interval.reference,
        )

        creditor_invoices = _fetch_with_limit_guard(
            fetcher=_fetch_creditor_invoices,
            date_from=interval.date_from,
            date_to_exclusive=(
                interval.date_to_exclusive
            ),
            dataset_name="VendTrans",
        )

        invoice_sources = _fetch_with_limit_guard(
            fetcher=_fetch_invoice_sources,
            date_from=interval.date_from,
            date_to_exclusive=(
                interval.date_to_exclusive
            ),
            dataset_name="VendInvoiceInfo",
        )

        document_references = _fetch_with_limit_guard(
            fetcher=_fetch_document_references,
            date_from=interval.date_from,
            date_to_exclusive=(
                interval.date_to_exclusive
            ),
            dataset_name="DocuRef",
        )

        week_data.append(
            WeekData(
                interval=interval,
                creditor_invoices=(
                    creditor_invoices
                ),
                invoice_sources=(
                    invoice_sources
                ),
                document_references=(
                    document_references
                ),
            )
        )

    return week_data


def build_queue_payloads(
    week_data: list[WeekData],
) -> dict[
    str,
    tuple[
        list[dict[str, str]],
        dict[str, int],
    ],
]:
    """Match de samlede lister og byg uge-resultater.

    Først samles alle ugernes data i fælles Python-lister.
    Derefter bygges indeks på tværs af ugegrænser.

    Manglende faktura- og dokumentmatch hentes bagefter
    med præcise fallback-kald.

    Alle fundne OIOUBL-filer medtages.

    Regler:

        0 OIOUBL:
            Kreditorposteringen ignoreres.

        1 OIOUBL:
            Én fil tilføjes.

        Flere OIOUBL:
            Alle filerne tilføjes.

    Returns:
        En dictionary med ét resultat pr. uge.

        Eksempel:

        {
            "uge 45 - 2025": (
                [
                    {
                        "fakturanummer": "1114013",
                        "kreditorkonto": "000113",
                        "filnavn": "faktura.xml",
                        "dokumentsti": "fuld UNC-sti",
                    }
                ],
                {
                    "kreditorfakturaer": 1,
                    "filer": 1,
                    "ignorerede": 0,
                    "kilde_fallback": 0,
                    "dokument_fallback": 0,
                    "fakturaer_med_flere_oioubl": 0,
                },
            )
        }
    """
    all_invoice_sources = [
        row
        for data in week_data
        for row in data.invoice_sources
    ]

    all_document_references = [
        row
        for data in week_data
        for row in data.document_references
    ]

    source_index = _build_source_index(
        all_invoice_sources
    )

    document_index = _build_document_index(
        all_document_references
    )

    document_information_cache: dict[
        int,
        Any,
    ] = {}

    payloads: dict[
        str,
        tuple[
            list[dict[str, str]],
            dict[str, int],
        ],
    ] = {}

    for data in week_data:
        files: list[dict[str, str]] = []

        statistics = {
            "kreditorfakturaer": len(
                data.creditor_invoices
            ),
            "filer": 0,
            "ignorerede": 0,
            "kilde_fallback": 0,
            "dokument_fallback": 0,
            "fakturaer_med_flere_oioubl": 0,
        }

        for creditor_invoice in data.creditor_invoices:
            invoice_source = _find_invoice_source(
                creditor_invoice=(
                    creditor_invoice
                ),
                source_index=source_index,
                statistics=statistics,
            )

            if (
                invoice_source is None
                or not invoice_source.get(
                    "RecIdLoc"
                )
            ):
                statistics[
                    "ignorerede"
                ] += 1

                logger.warning(
                    "Ignorerer faktura %s / %s: "
                    "intet entydigt fakturamatch.",
                    creditor_invoice.get(
                        "Fakturanummer"
                    ),
                    creditor_invoice.get(
                        "Kreditorkonto"
                    ),
                )

                continue

            invoice_rec_id = invoice_source[
                "RecIdLoc"
            ]

            documents = document_index.get(
                invoice_rec_id,
                [],
            )

            if not documents:
                statistics[
                    "dokument_fallback"
                ] += 1

                documents = search_dokumenter(
                    ref_rec_id=invoice_rec_id,
                    tabel=(
                        "ventende_kreditorfaktura"
                    ),
                    dokumenttyper=DOKUMENTTYPER,
                    data_area_id=DATA_AREA_ID,
                    hent_dokumentplacering=False,
                    top=100,
                )

            oioubl_documents = [
                document
                for document in documents
                if (
                    document.get(
                        "ErFysiskFil"
                    )
                    and str(
                        document.get(
                            "TypeId"
                        )
                        or ""
                    ).casefold()
                    == "oioubl"
                    and isinstance(
                        document.get(
                            "ValueRecId"
                        ),
                        int,
                    )
                    and document.get(
                        "ValueRecId"
                    )
                    > 0
                )
            ]

            if not oioubl_documents:
                statistics[
                    "ignorerede"
                ] += 1

                logger.warning(
                    "Ignorerer faktura %s / %s: "
                    "der blev ikke fundet nogen "
                    "fysisk OIOUBL-fil.",
                    creditor_invoice.get(
                        "Fakturanummer"
                    ),
                    creditor_invoice.get(
                        "Kreditorkonto"
                    ),
                )

                continue

            if len(oioubl_documents) > 1:
                statistics[
                    "fakturaer_med_flere_oioubl"
                ] += 1

                logger.info(
                    "Faktura %s / %s har %s "
                    "OIOUBL-filer. Alle filer medtages.",
                    creditor_invoice.get(
                        "Fakturanummer"
                    ),
                    creditor_invoice.get(
                        "Kreditorkonto"
                    ),
                    len(
                        oioubl_documents
                    ),
                )

            added_files_for_invoice = 0
            seen_value_rec_ids: set[int] = set()

            for oioubl_document in oioubl_documents:
                value_rec_id = oioubl_document[
                    "ValueRecId"
                ]

                # Undgå samme fysiske dokument to gange,
                # hvis DocuRef-listen indeholder dubletter.
                if value_rec_id in seen_value_rec_ids:
                    continue

                seen_value_rec_ids.add(
                    value_rec_id
                )

                if (
                    value_rec_id
                    not in document_information_cache
                ):
                    try:
                        document_information_cache[
                            value_rec_id
                        ] = get_dokumentinformation(
                            value_rec_id=value_rec_id,
                            domain_suffix=(
                                DOMAIN_SUFFIX
                            ),
                        )

                    except Exception:
                        logger.exception(
                            "Kunne ikke hente "
                            "dokumentinformation for "
                            "faktura %s / %s og "
                            "ValueRecId %s.",
                            creditor_invoice.get(
                                "Fakturanummer"
                            ),
                            creditor_invoice.get(
                                "Kreditorkonto"
                            ),
                            value_rec_id,
                        )

                        continue

                document_information = (
                    document_information_cache[
                        value_rec_id
                    ]
                )

                if (
                    not document_information
                    .original_file_name
                    or not document_information
                    .document_path
                ):
                    logger.warning(
                        "Springer OIOUBL-dokument over "
                        "for faktura %s / %s: "
                        "filnavn eller dokumentsti "
                        "mangler for ValueRecId %s.",
                        creditor_invoice.get(
                            "Fakturanummer"
                        ),
                        creditor_invoice.get(
                            "Kreditorkonto"
                        ),
                        value_rec_id,
                    )

                    continue

                files.append(
                    {
                        "fakturanummer": (
                            creditor_invoice[
                                "Fakturanummer"
                            ]
                        ),
                        "kreditorkonto": (
                            creditor_invoice[
                                "Kreditorkonto"
                            ]
                        ),
                        "filnavn": (
                            document_information
                            .original_file_name
                        ),
                        "dokumentsti": (
                            document_information
                            .document_path
                        ),
                    }
                )

                added_files_for_invoice += 1

            # Kreditorposteringen ignoreres kun, hvis
            # ingen af dens OIOUBL-referencer kunne
            # omsættes til en anvendelig fysisk fil.
            if added_files_for_invoice == 0:
                statistics[
                    "ignorerede"
                ] += 1

                logger.warning(
                    "Ignorerer faktura %s / %s: "
                    "ingen af de %s OIOUBL-referencer "
                    "havde både filnavn og dokumentsti.",
                    creditor_invoice.get(
                        "Fakturanummer"
                    ),
                    creditor_invoice.get(
                        "Kreditorkonto"
                    ),
                    len(
                        oioubl_documents
                    ),
                )

        statistics[
            "filer"
        ] = len(
            files
        )

        print(
            f"{data.interval.reference}: "
            f"Filer {statistics['filer']}, "
            f"ignorerede "
            f"{statistics['ignorerede']}, "
            f"fakturaer med flere OIOUBL "
            f"{statistics['fakturaer_med_flere_oioubl']}."
        )

        payloads[
            data.interval.reference
        ] = (
            files,
            statistics,
        )

    return payloads


def _fetch_with_limit_guard(
    fetcher: Callable[
        [date, date],
        list[dict[str, Any]],
    ],
    date_from: date,
    date_to_exclusive: date,
    dataset_name: str,
) -> list[dict[str, Any]]:
    """Hent et datointerval og opdel det ved 10.000 rækker.

    Normalt kaldes fetcher én gang pr. uge. Hvis resultatet
    rammer PRISME_TOP, deles intervallet rekursivt i mindre dele.
    """
    rows = fetcher(
        date_from,
        date_to_exclusive,
    )

    if len(rows) < PRISME_TOP:
        return rows

    interval_days = (
        date_to_exclusive
        - date_from
    ).days

    if interval_days <= 1:
        raise RuntimeError(
            f"{dataset_name} ramte grænsen "
            f"på {PRISME_TOP} rækker for "
            f"{date_from}. Intervallet kan "
            "ikke opdeles yderligere."
        )

    split_date = (
        date_from
        + timedelta(
            days=(
                interval_days
                // 2
            )
        )
    )

    logger.warning(
        "%s ramte %s rækker fra %s til før %s. "
        "Opdeler intervallet ved %s.",
        dataset_name,
        PRISME_TOP,
        date_from,
        date_to_exclusive,
        split_date,
    )

    return (
        _fetch_with_limit_guard(
            fetcher=fetcher,
            date_from=date_from,
            date_to_exclusive=split_date,
            dataset_name=dataset_name,
        )
        + _fetch_with_limit_guard(
            fetcher=fetcher,
            date_from=split_date,
            date_to_exclusive=(
                date_to_exclusive
            ),
            dataset_name=dataset_name,
        )
    )


def _fetch_creditor_invoices(
    date_from: date,
    date_to_exclusive: date,
) -> list[dict[str, Any]]:
    """Hent VendTrans for ét halvåbent interval."""
    return hent_kreditorfakturaer(
        date_from,
        date_to_exclusive,
        voucher_prefix=VOUCHER_PREFIX,
        data_area_id=DATA_AREA_ID,
        top=PRISME_TOP,
    )


def _fetch_invoice_sources(
    date_from: date,
    date_to_exclusive: date,
) -> list[dict[str, Any]]:
    """Hent VendInvoiceInfo for ét halvåbent interval."""
    return hent_oprindelige_fakturaposter(
        fakturadato_fra=date_from,
        fakturadato_til=(
            date_to_exclusive
        ),
        data_area_id=DATA_AREA_ID,
        top=PRISME_TOP,
    )


def _fetch_document_references(
    date_from: date,
    date_to_exclusive: date,
) -> list[dict[str, Any]]:
    """Hent DocuRef for ét halvåbent interval."""
    return hent_dokumentreferencer(
        ref_table_id=6084,
        oprettet_fra=date_from,
        oprettet_til=(
            date_to_exclusive
        ),
        dokumenttyper=DOKUMENTTYPER,
        data_area_id=DATA_AREA_ID,
        top=PRISME_TOP,
    )


def _find_invoice_source(
    creditor_invoice: dict[str, Any],
    source_index: dict[
        tuple,
        list[dict[str, Any]],
    ],
    statistics: dict[str, int],
) -> dict[str, Any] | None:
    """Find fakturakilden lokalt eller via præcist fallback."""
    invoice_key = _invoice_key(
        creditor_invoice
    )

    source_candidates = source_index.get(
        invoice_key,
        [],
    )

    if len(source_candidates) == 1:
        return source_candidates[0]

    statistics[
        "kilde_fallback"
    ] += 1

    fallback_sources = (
        hent_oprindelige_fakturaposter(
            fakturanummer=(
                creditor_invoice[
                    "Fakturanummer"
                ]
            ),
            kreditorkonto=(
                creditor_invoice[
                    "Kreditorkonto"
                ]
            ),
            data_area_id=DATA_AREA_ID,
            top=20,
        )
    )

    exact_matches = [
        source
        for source in fallback_sources
        if _invoice_key(
            source
        )
        == invoice_key
    ]

    if len(exact_matches) != 1:
        return None

    return exact_matches[0]


def _build_source_index(
    invoice_sources: list[dict[str, Any]],
) -> dict[
    tuple,
    list[dict[str, Any]],
]:
    """Byg indeks på nummer, konto, dato og beløb."""
    result: dict[
        tuple,
        list[dict[str, Any]],
    ] = {}

    for invoice_source in invoice_sources:
        result.setdefault(
            _invoice_key(
                invoice_source
            ),
            [],
        ).append(
            invoice_source
        )

    return result


def _build_document_index(
    documents: list[dict[str, Any]],
) -> dict[
    int,
    list[dict[str, Any]],
]:
    """Byg dokumentindeks på ReferenceRecId."""
    result: dict[
        int,
        list[dict[str, Any]],
    ] = {}

    seen_reference_ids: set[int] = set()

    for document in documents:
        document_reference_id = document.get(
            "DokumentReferenceRecId"
        )

        if (
            isinstance(
                document_reference_id,
                int,
            )
            and document_reference_id
            in seen_reference_ids
        ):
            continue

        if isinstance(
            document_reference_id,
            int,
        ):
            seen_reference_ids.add(
                document_reference_id
            )

        reference_rec_id = document.get(
            "ReferenceRecId"
        )

        if not isinstance(
            reference_rec_id,
            int,
        ):
            continue

        if reference_rec_id <= 0:
            continue

        result.setdefault(
            reference_rec_id,
            [],
        ).append(
            document
        )

    return result


def _invoice_key(
    row: dict[str, Any],
) -> tuple[
    str,
    str,
    str,
    Decimal | None,
]:
    """Byg matchnøglen nummer, konto, dato og absolut beløb."""
    return (
        str(
            row.get(
                "Fakturanummer"
            )
            or ""
        ).strip().casefold(),
        str(
            row.get(
                "Kreditorkonto"
            )
            or ""
        ).strip().casefold(),
        str(
            row.get(
                "Fakturadato"
            )
            or ""
        )[:10],
        _absolute_decimal(
            row.get(
                "Beløb"
            )
        ),
    )


def _absolute_decimal(
    value: Any,
) -> Decimal | None:
    """Konvertér et valgfrit beløb til positiv Decimal."""
    try:
        return abs(
            Decimal(
                str(
                    value
                )
            )
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return None
