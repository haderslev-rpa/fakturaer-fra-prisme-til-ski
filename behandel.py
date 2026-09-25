"""Behandling af ét ugentligt ATS-item."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
import zipfile

from automation_server_client import WorkItemError
from q_haderslev_vbo.automation_server.ats_update_item_data import (
    update_item_data,
)
from q_oioubl_faktura_parser.functionality.storage import (
    StorageClient,
)

from configuration import EFFECTIVE_FAKTURA_TEMP_ROOT
from sharepoint_upload import upload_and_validate_zip


logger = logging.getLogger(
    __name__
)


class States:
    """Processtates for ét uge-item."""

    FORBERED_MAPPE = (
        "1.0 Arbejdsmappe klargjort"
    )
    DOWNLOAD_FILER = (
        "2.0 Fakturafiler hentet"
    )
    OPRET_ZIP = (
        "3.0 ZIP-fil oprettet"
    )
    VALIDER_LOKAL_ZIP = (
        "4.0 Lokal ZIP-fil valideret"
    )
    UPLOAD_SHAREPOINT = (
        "5.0 ZIP-fil uploadet og valideret i SharePoint"
    )
    RYD_OP_LOKALT = (
        "6.0 Lokale tempfiler slettet"
    )
    AFSLUT = (
        "7.0 Uge afsluttet"
    )


def behandel_item(
    item,
) -> None:
    """Download, ZIP, upload til SharePoint og ryd op.

    Lokale filer slettes først, når SharePoint-uploaden er
    valideret med samme filnavn, item-id og filstørrelse.

    Ved fejl før SharePoint-valideringen beholdes lokale filer,
    så processen kan fejlsøges og genkøres.
    """
    data = item.data
    box = data.get(
        "box"
    )

    if not isinstance(
        box,
        dict,
    ):
        raise WorkItemError(
            "Itemet mangler box-data."
        )

    reference = _required_text(
        box.get(
            "reference"
        ),
        "box.reference",
    )

    invoice_files = box.get(
        "fakturaer"
    )

    if not isinstance(
        invoice_files,
        list,
    ):
        raise WorkItemError(
            "box.fakturaer skal være en liste."
        )

    root_folder = Path(
        EFFECTIVE_FAKTURA_TEMP_ROOT
    )

    work_folder = (
        root_folder
        / reference
    )

    zip_path = (
        root_folder
        / f"{reference}.zip"
    )

    root_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    _remove_path(
        work_folder
    )
    _remove_path(
        zip_path
    )

    work_folder.mkdir(
        parents=True,
        exist_ok=False,
    )

    _set_state(
        data,
        item,
        States.FORBERED_MAPPE,
    )

    storage_client = StorageClient()
    downloaded_files: list[Path] = []

    for invoice_file in invoice_files:
        if not isinstance(
            invoice_file,
            dict,
        ):
            raise WorkItemError(
                "En fakturarække er ikke en dictionary."
            )

        source_path = _required_text(
            invoice_file.get(
                "dokumentsti"
            ),
            "dokumentsti",
        )

        filename = _safe_filename(
            _required_text(
                invoice_file.get(
                    "filnavn"
                ),
                "filnavn",
            )
        )

        destination_path = _unique_path(
            work_folder,
            filename,
        )

        downloaded_files.append(
            storage_client.download_file(
                file_path=source_path,
                destination_path=(
                    destination_path
                ),
            )
        )

    _set_state(
        data,
        item,
        States.DOWNLOAD_FILER,
    )

    with zipfile.ZipFile(
        zip_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for downloaded_file in downloaded_files:
            archive.write(
                downloaded_file,
                arcname=downloaded_file.name,
            )

    _set_state(
        data,
        item,
        States.OPRET_ZIP,
    )

    _validate_zip(
        zip_path=zip_path,
        expected_files=len(
            downloaded_files
        ),
    )

    _set_state(
        data,
        item,
        States.VALIDER_LOKAL_ZIP,
    )

    sharepoint_result = upload_and_validate_zip(
        zip_path
    )

    update_item_data(
        data,
        box_updates={
            "sharepoint_filnavn": (
                sharepoint_result.file_name
            ),
            "sharepoint_item_id": (
                sharepoint_result.item_id
            ),
            "sharepoint_sti": (
                sharepoint_result.sharepoint_path
            ),
            "sharepoint_web_url": (
                sharepoint_result.web_url
            ),
            "sharepoint_filstoerrelse": (
                sharepoint_result.file_size
            ),
        },
        item=item,
    )

    _set_state(
        data,
        item,
        States.UPLOAD_SHAREPOINT,
    )

    # SharePoint-filen er nu valideret. De lokale tempdata
    # har ikke længere en funktion og slettes derfor.
    _remove_path(
        work_folder
    )
    _remove_path(
        zip_path
    )

    _set_state(
        data,
        item,
        States.RYD_OP_LOKALT,
    )

    _set_state(
        data,
        item,
        States.AFSLUT,
    )

    logger.info(
        "ZIP-filen er uploadet og valideret: %s",
        sharepoint_result.sharepoint_path,
    )


def _validate_zip(
    zip_path: Path,
    expected_files: int,
) -> None:
    """Kontrollér ZIP-filens eksistens og indhold."""
    if not zip_path.is_file():
        raise WorkItemError(
            "ZIP-filen blev ikke oprettet: "
            f"{zip_path}"
        )

    if not zipfile.is_zipfile(
        zip_path
    ):
        raise WorkItemError(
            "Filen er ikke en gyldig ZIP-fil: "
            f"{zip_path}"
        )

    with zipfile.ZipFile(
        zip_path,
        mode="r",
    ) as archive:
        bad_file = archive.testzip()

        if bad_file is not None:
            raise WorkItemError(
                "ZIP-filen indeholder en beskadiget fil: "
                f"{bad_file}"
            )

        actual_files = len(
            [
                filename
                for filename in archive.namelist()
                if not filename.endswith(
                    "/"
                )
            ]
        )

    if actual_files != expected_files:
        raise WorkItemError(
            "ZIP-filen indeholder "
            f"{actual_files} filer, "
            f"men forventede {expected_files}."
        )


def _unique_path(
    folder: Path,
    filename: str,
) -> Path:
    """Returnér en ledig filsti og nummerér dubletter."""
    candidate = (
        folder
        / filename
    )

    if not candidate.exists():
        return candidate

    filename_path = Path(
        filename
    )
    stem = filename_path.stem
    suffix = filename_path.suffix
    number = 1

    while True:
        candidate = (
            folder
            / f"{stem} ({number}){suffix}"
        )

        if not candidate.exists():
            return candidate

        number += 1


def _safe_filename(
    filename: str,
) -> str:
    """Fjern mapper fra et modtaget filnavn."""
    normalized_filename = filename.replace(
        chr(92),
        "/",
    )

    safe_name = Path(
        normalized_filename
    ).name.strip()

    if not safe_name:
        raise WorkItemError(
            "Filnavnet er ugyldigt."
        )

    if safe_name in {
        ".",
        "..",
    }:
        raise WorkItemError(
            "Filnavnet er ugyldigt."
        )

    return safe_name


def _remove_path(
    path: Path,
) -> None:
    """Slet en fil eller mappe, hvis den findes."""
    if path.is_dir():
        shutil.rmtree(
            path
        )
    elif path.exists():
        path.unlink()


def _set_state(
    data: dict,
    item,
    state: str,
) -> None:
    """Tilføj en state og gem item-data."""
    update_item_data(
        data,
        item=item,
        state=state,
    )


def _required_text(
    value,
    variable_name: str,
) -> str:
    """Kontrollér en obligatorisk tekstværdi."""
    text_value = str(
        value
        or ""
    ).strip()

    if not text_value:
        raise WorkItemError(
            f"{variable_name} skal udfyldes."
        )

    return text_value
