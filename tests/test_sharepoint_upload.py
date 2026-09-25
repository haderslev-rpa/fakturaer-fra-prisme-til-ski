"""Test upload og validering af test.txt i SharePoint."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from automation_server_client import AutomationServer
from q_sharepoint_api.sp_api import get_client


# ------------------------------------------------------------
# KONFIGURATION
# ------------------------------------------------------------

SITE_NAME = "Automatisering"

SHAREPOINT_FOLDER_PATH = (
    "RPA - Processer/"
    "fakturaer-fra-prisme-til-ski"
)

TEST_FILE_NAME = "test.txt"


# ------------------------------------------------------------
# TEST
# ------------------------------------------------------------

def test_upload_text_file() -> None:
    """Upload test.txt og kontrollér, at filen findes.

    Output:
        Funktionen printer SharePoint-filens navn, id,
        webadresse og den validerede sti.

    Filen bliver liggende i SharePoint efter testen, så
    resultatet også kan kontrolleres i brugerfladen.
    """
    AutomationServer.from_environment()

    client = get_client()

    print()
    print("=" * 78)
    print("TEST UPLOAD TIL SHAREPOINT")
    print("=" * 78)
    print()
    print("Site:", SITE_NAME)
    print("Mappe:", SHAREPOINT_FOLDER_PATH)
    print("Filnavn:", TEST_FILE_NAME)

    site_id = client.get_site_id(
        SITE_NAME
    )

    drive_id = client.get_drive_id(
        site_id
    )

    timestamp = datetime.now(
        ZoneInfo("Europe/Copenhagen")
    ).isoformat()

    file_content = (
        "Test fra processen "
        "fakturaer-fra-prisme-til-ski.\n"
        f"Oprettet: {timestamp}\n"
    ).encode(
        "utf-8"
    )

    print()
    print("Uploader testfil...")

    uploaded_file = client.upload_file(
        drive_id=drive_id,
        folder_path=SHAREPOINT_FOLDER_PATH,
        file_name=TEST_FILE_NAME,
        content=file_content,
    )

    uploaded_file_id = str(
        uploaded_file.get(
            "id",
            "",
        )
        or ""
    ).strip()

    uploaded_file_name = str(
        uploaded_file.get(
            "name",
            "",
        )
        or ""
    ).strip()

    uploaded_web_url = str(
        uploaded_file.get(
            "webUrl",
            "",
        )
        or ""
    ).strip()

    if not uploaded_file_id:
        raise RuntimeError(
            "SharePoint returnerede ikke et fil-id."
        )

    if uploaded_file_name != TEST_FILE_NAME:
        raise RuntimeError(
            "SharePoint returnerede et uventet filnavn: "
            f"{uploaded_file_name!r}."
        )

    sharepoint_file_path = (
        f"{SHAREPOINT_FOLDER_PATH}/"
        f"{TEST_FILE_NAME}"
    )

    print()
    print("Validerer filen via SharePoint-stien...")

    validated_file_id = (
        client.get_drive_item_id(
            site_id=site_id,
            file_path=sharepoint_file_path,
        )
    )

    if validated_file_id != uploaded_file_id:
        raise RuntimeError(
            "Den validerede SharePoint-fil har et andet id. "
            f"Upload-id: {uploaded_file_id}. "
            f"Valideret id: {validated_file_id}."
        )

    print()
    print("=" * 78)
    print("UPLOAD OG VALIDERING LYKKEDES")
    print("=" * 78)
    print()
    print("Filnavn:", uploaded_file_name)
    print("Fil-id:", uploaded_file_id)
    print("SharePoint-sti:", sharepoint_file_path)
    print("Webadresse:", uploaded_web_url)
    print()
    print(
        "Testfilen bliver liggende i SharePoint, "
        "så den kan kontrolleres manuelt."
    )


if __name__ == "__main__":
    test_upload_text_file()