"""Konfiguration for processen fakturaer-fra-prisme-til-ski."""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


# ------------------------------------------------------------
# PROCES
# ------------------------------------------------------------

PROCESS_NAME = "fakturaer-fra-prisme-til-ski"


# ------------------------------------------------------------
# PRISME
# ------------------------------------------------------------

PRISME_CREDENTIAL_NAME = "API_PRISME365_1"
DATA_AREA_ID = "had"
VOUCHER_PREFIX = "EFAK-"
DOKUMENTTYPER = ("OIOUBL",)
DOMAIN_SUFFIX = "prisme-365.dk"
PRISME_TOP = 10000


# ------------------------------------------------------------
# FAKTURAPERIODE
# ------------------------------------------------------------

# Begge datoer er inklusive.
FAKTURADATO_FRA = date(2025, 11, 1)
FAKTURADATO_TIL = date(2026, 1, 31)


# ------------------------------------------------------------
# LOKAL TEMPMAPPE
# ------------------------------------------------------------

FAKTURA_TEMP_ROOT = Path(
    "/tmp/fakturaer-fra-prisme-til-ski"
)

_env_temp_root = os.getenv(
    "FAKTURA_TEMP_ROOT",
    "",
).strip()

EFFECTIVE_FAKTURA_TEMP_ROOT = (
    Path(_env_temp_root).expanduser()
    if _env_temp_root
    else FAKTURA_TEMP_ROOT
)


# ------------------------------------------------------------
# SHAREPOINT
# ------------------------------------------------------------

SHAREPOINT_SITE_NAME = "Automatisering"

# Stien er relativ til sitets standarddokumentbibliotek.
SHAREPOINT_FOLDER_PATH = (
    "RPA - Processer/"
    "fakturaer-fra-prisme-til-ski"
)

# Simple Graph-upload bruges til og med 250 MiB.
# Større filer bruger automatisk en upload session.
SHAREPOINT_SIMPLE_UPLOAD_LIMIT_BYTES = (
    250
    * 1024
    * 1024
)

# Graph kræver, at upload-sessionens bidder er et multiplum
# af 320 KiB. 10 MiB er præcis 32 * 320 KiB.
SHAREPOINT_UPLOAD_CHUNK_SIZE_BYTES = (
    10
    * 1024
    * 1024
)
