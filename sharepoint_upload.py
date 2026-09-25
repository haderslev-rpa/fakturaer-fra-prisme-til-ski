"""Upload og validering af ZIP-filer i SharePoint."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import quote

import requests
from q_sharepoint_api.sp_api import get_client

from configuration import SHAREPOINT_FOLDER_PATH
from configuration import SHAREPOINT_SIMPLE_UPLOAD_LIMIT_BYTES
from configuration import SHAREPOINT_SITE_NAME
from configuration import SHAREPOINT_UPLOAD_CHUNK_SIZE_BYTES


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


@dataclass(frozen=True)
class SharePointUploadResult:
    """Resultat af en uploadet og valideret SharePoint-fil."""

    item_id: str
    file_name: str
    file_size: int
    web_url: str
    sharepoint_path: str


def upload_and_validate_zip(
    zip_path: Path,
) -> SharePointUploadResult:
    """Upload en ZIP-fil og validér navn, id og filstørrelse.

    Små filer uploades med den eksisterende simple Graph-upload.
    Filer over grænsen uploades i bidder via en upload session.

    Hvis upload eller validering fejler, forsøger funktionen at
    slette den uploadede SharePoint-fil igen.

    Args:
        zip_path:
            Lokal sti til en eksisterende ZIP-fil.

    Returns:
        SharePointUploadResult med id, navn, størrelse,
        webadresse og SharePoint-sti.
    """
    local_zip_path = Path(
        zip_path
    )

    if not local_zip_path.is_file():
        raise FileNotFoundError(
            "ZIP-filen findes ikke: "
            f"{local_zip_path}"
        )

    local_file_size = local_zip_path.stat().st_size

    if local_file_size <= 0:
        raise ValueError(
            "ZIP-filen er tom: "
            f"{local_zip_path}"
        )

    client = get_client()

    site_id = client.get_site_id(
        SHAREPOINT_SITE_NAME
    )

    drive_id = client.get_drive_id(
        site_id
    )

    uploaded_item_id: str | None = None

    try:
        if (
            local_file_size
            <= SHAREPOINT_SIMPLE_UPLOAD_LIMIT_BYTES
        ):
            uploaded_item = _upload_small_file(
                client=client,
                drive_id=drive_id,
                zip_path=local_zip_path,
            )
        else:
            uploaded_item = _upload_large_file(
                client=client,
                drive_id=drive_id,
                zip_path=local_zip_path,
            )

        uploaded_item_id = _required_text(
            uploaded_item.get(
                "id"
            ),
            "SharePoint item-id",
        )

        return _validate_uploaded_file(
            client=client,
            site_id=site_id,
            local_zip_path=local_zip_path,
            expected_item_id=uploaded_item_id,
        )

    except Exception:
        if uploaded_item_id:
            try:
                client.delete_item(
                    drive_id,
                    uploaded_item_id,
                )
            except Exception:
                # Den oprindelige uploadfejl skal bevares.
                pass

        raise


def _upload_small_file(
    client,
    drive_id: str,
    zip_path: Path,
) -> dict:
    """Upload en fil med SharePoint-klientens simple upload."""
    with zip_path.open(
        mode="rb"
    ) as file:
        content = file.read()

    return client.upload_file(
        drive_id=drive_id,
        folder_path=SHAREPOINT_FOLDER_PATH,
        file_name=zip_path.name,
        content=content,
    )


def _upload_large_file(
    client,
    drive_id: str,
    zip_path: Path,
) -> dict:
    """Upload en stor fil via Microsoft Graph upload session."""
    encoded_path = _encode_drive_path(
        f"{SHAREPOINT_FOLDER_PATH}/"
        f"{zip_path.name}"
    )

    create_session_url = (
        f"{GRAPH_BASE_URL}/drives/{drive_id}"
        f"/root:/{encoded_path}:/createUploadSession"
    )

    response = requests.post(
        create_session_url,
        headers=client.auth.graph_headers(),
        json={
            "item": {
                "@microsoft.graph.conflictBehavior": (
                    "replace"
                ),
                "name": zip_path.name,
            }
        },
        timeout=60,
    )

    response.raise_for_status()

    upload_url = _required_text(
        response.json().get(
            "uploadUrl"
        ),
        "uploadUrl",
    )

    file_size = zip_path.stat().st_size
    start_byte = 0
    completed_item: dict | None = None

    with zip_path.open(
        mode="rb"
    ) as file:
        while start_byte < file_size:
            chunk = file.read(
                SHAREPOINT_UPLOAD_CHUNK_SIZE_BYTES
            )

            if not chunk:
                break

            end_byte = (
                start_byte
                + len(chunk)
                - 1
            )

            chunk_response = requests.put(
                upload_url,
                headers={
                    "Content-Length": str(
                        len(chunk)
                    ),
                    "Content-Range": (
                        f"bytes {start_byte}-{end_byte}/"
                        f"{file_size}"
                    ),
                },
                data=chunk,
                timeout=300,
            )

            chunk_response.raise_for_status()

            if chunk_response.status_code in {
                200,
                201,
            }:
                completed_item = chunk_response.json()

            start_byte = (
                end_byte
                + 1
            )

    if completed_item is None:
        raise RuntimeError(
            "Upload-sessionen returnerede ikke "
            "det færdige SharePoint-element."
        )

    return completed_item


def _validate_uploaded_file(
    client,
    site_id: str,
    local_zip_path: Path,
    expected_item_id: str,
) -> SharePointUploadResult:
    """Validér den uploadede fil via dens SharePoint-sti."""
    sharepoint_path = (
        f"{SHAREPOINT_FOLDER_PATH}/"
        f"{local_zip_path.name}"
    )

    encoded_path = _encode_drive_path(
        sharepoint_path
    )

    metadata_url = (
        f"{GRAPH_BASE_URL}/sites/{site_id}"
        f"/drive/root:/{encoded_path}:"
    )

    response = requests.get(
        metadata_url,
        headers=client.auth.graph_headers(),
        timeout=60,
    )

    response.raise_for_status()

    metadata = response.json()

    actual_item_id = _required_text(
        metadata.get(
            "id"
        ),
        "valideret SharePoint item-id",
    )

    actual_file_name = _required_text(
        metadata.get(
            "name"
        ),
        "valideret SharePoint-filnavn",
    )

    actual_file_size = metadata.get(
        "size"
    )

    if actual_item_id != expected_item_id:
        raise RuntimeError(
            "Den validerede SharePoint-fil har "
            "et andet item-id."
        )

    if actual_file_name != local_zip_path.name:
        raise RuntimeError(
            "Den validerede SharePoint-fil har "
            "et andet filnavn."
        )

    if actual_file_size != local_zip_path.stat().st_size:
        raise RuntimeError(
            "Den validerede SharePoint-fil har "
            "en anden filstørrelse. "
            f"Lokal: {local_zip_path.stat().st_size}. "
            f"SharePoint: {actual_file_size}."
        )

    return SharePointUploadResult(
        item_id=actual_item_id,
        file_name=actual_file_name,
        file_size=actual_file_size,
        web_url=str(
            metadata.get(
                "webUrl"
            )
            or ""
        ).strip(),
        sharepoint_path=sharepoint_path,
    )


def _encode_drive_path(
    path: str,
) -> str:
    """URL-kod en sti, men bevar slash mellem mapperne."""
    normalized_path = str(
        path
    ).strip().lstrip(
        "/"
    ).replace(
        "\\",
        "/",
    )

    return quote(
        normalized_path,
        safe="/",
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
        raise ValueError(
            f"{variable_name} skal udfyldes."
        )

    return text_value
