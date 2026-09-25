"""Saml originale OIOUBL-dokumenter for et fakturadatointerval."""

from __future__ import annotations

from decimal import Decimal
from decimal import InvalidOperation
import logging
from typing import Any

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


logger = logging.getLogger(
    __name__
)


def collect_week_documents(
    date_from,
    date_to,
) -> tuple[
    list[dict[str, str]],
    dict[str, int],
]:
    """Saml ugens originale OIOUBL-filer.

    Output er en tuple med:

        1. En liste med filer.
        2. Statistik for intervallet.

    Hver fil har præcis denne struktur:

        {
            "fakturanummer": "1114013",
            "kreditorkonto": "000113",
            "filnavn": "faktura.xml",
            "dokumentsti": "fuld UNC-dokumentsti",
        }
    """
    creditor_invoices = hent_kreditorfakturaer(
        date_from,
        date_to,
        voucher_prefix=VOUCHER_PREFIX,
        data_area_id=DATA_AREA_ID,
        top=PRISME_TOP,
    )

    invoice_sources = (
        hent_oprindelige_fakturaposter(
            fakturadato_fra=date_from,
            fakturadato_til=date_to,
            data_area_id=DATA_AREA_ID,
            top=PRISME_TOP,
        )
    )

    source_index = _build_source_index(
        invoice_sources
    )

    document_references = (
        hent_dokumentreferencer(
            ref_table_id=6084,
            oprettet_fra=date_from,
            oprettet_til=date_to,
            dokumenttyper=DOKUMENTTYPER,
            data_area_id=DATA_AREA_ID,
            top=PRISME_TOP,
        )
    )

    document_index = (
        _build_document_index(
            document_references
        )
    )

    document_information_cache: dict[
        int,
        Any,
    ] = {}

    result: list[
        dict[str, str]
    ] = []

    statistics = {
        "kreditorfakturaer": len(
            creditor_invoices
        ),
        "kilde_fallback": 0,
        "dokument_fallback": 0,
        "ignorerede": 0,
        "filer": 0,
    }

    for creditor_invoice in creditor_invoices:
        invoice_key = _invoice_key(
            creditor_invoice
        )

        source_candidates = source_index.get(
            invoice_key,
            [],
        )

        invoice_source = _find_one_exact_source(
            creditor_invoice,
            source_candidates,
        )

        if invoice_source is None:
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

            invoice_source = (
                _find_one_exact_source(
                    creditor_invoice,
                    fallback_sources,
                )
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
                and document.get(
                    "ValueRecId"
                )
            )
        ]

        if len(oioubl_documents) != 1:
            statistics[
                "ignorerede"
            ] += 1

            logger.warning(
                "Ignorerer faktura %s / %s: "
                "forventede 1 OIOUBL, fandt %s.",
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

            continue

        value_rec_id = oioubl_documents[
            0
        ]["ValueRecId"]

        if (
            value_rec_id
            not in document_information_cache
        ):
            document_information_cache[
                value_rec_id
            ] = get_dokumentinformation(
                value_rec_id=value_rec_id,
                domain_suffix=(
                    DOMAIN_SUFFIX
                ),
            )

        document_information = (
            document_information_cache[
                value_rec_id
            ]
        )

        if (
            not document_information.original_file_name
            or not document_information.document_path
        ):
            statistics[
                "ignorerede"
            ] += 1

            logger.warning(
                "Ignorerer faktura %s / %s: "
                "filnavn eller dokumentsti mangler.",
                creditor_invoice.get(
                    "Fakturanummer"
                ),
                creditor_invoice.get(
                    "Kreditorkonto"
                ),
            )

            continue

        result.append(
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

    statistics[
        "filer"
    ] = len(
        result
    )

    print(
        "Ignorerede kreditorposteringer "
        f"i ugen: {statistics['ignorerede']}"
    )

    return (
        result,
        statistics,
    )


def _build_source_index(
    invoice_sources: list[dict[str, Any]],
) -> dict[
    tuple,
    list[dict[str, Any]],
]:
    """Byg et indeks over oprindelige fakturaposter."""
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
    """Gruppér dokumenter efter ReferenceRecId."""
    result: dict[
        int,
        list[dict[str, Any]],
    ] = {}

    for document in documents:
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


def _find_one_exact_source(
    creditor_invoice: dict[str, Any],
    source_candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Returnér præcis ét entydigt fakturamatch."""
    expected_key = _invoice_key(
        creditor_invoice
    )

    matches = [
        source
        for source in source_candidates
        if _invoice_key(
            source
        )
        == expected_key
    ]

    if len(matches) != 1:
        return None

    return matches[0]


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
