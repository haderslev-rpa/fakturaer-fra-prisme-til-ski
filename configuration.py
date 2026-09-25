"""Konfiguration for processen fakturaer-fra-prisme-til-ski."""

from __future__ import annotations

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
# AUTOMATISK FAKTURAPERIODE
# ------------------------------------------------------------

# ANTAL_UGER_FORSINKELSE bestemmer, hvor langt processen går
# tilbage fra den aktuelle ISO-uge, før en uge må behandles.
#
# Værdien 6 betyder, at den nyeste uge i udtrækket altid ligger
# 6 hele ISO-uger før den uge, hvor --queue køres.
#
# Forsinkelsen giver fakturaer med en ældre fakturadato tid til
# at blive bogført og komme med i VendTrans.
ANTAL_UGER_FORSINKELSE = 6

# ANTAL_UGER_TILBAGE bestemmer, hvor mange komplette ISO-uger
# processen undersøger og forsøger at oprette queue-items for.
#
# Værdien 60 betyder præcis 60 komplette uger inklusive den
# seneste tilladte uge efter forsinkelsen.
#
# Eksempel:
# - Aktuel uge er uge 39.
# - ANTAL_UGER_FORSINKELSE er 6.
# - Seneste tilladte uge er uge 33.
# - ANTAL_UGER_TILBAGE er 60.
# - Processen undersøger uge 33 og de 59 foregående ISO-uger.
ANTAL_UGER_TILBAGE = 65


# ------------------------------------------------------------
# LOKAL TEMPMAPPE
# ------------------------------------------------------------

# Standardplacering på Automation Server.
FAKTURA_TEMP_ROOT = Path(
    "/tmp/fakturaer-fra-prisme-til-ski"
)

# Ved lokal debugging kan .env overskrive placeringen:
#
# FAKTURA_TEMP_ROOT=/home/dirujo/tests_local/fakturaer-fra-prisme-til-ski
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

SHAREPOINT_SIMPLE_UPLOAD_LIMIT_BYTES = (
    250
    * 1024
    * 1024
)

SHAREPOINT_UPLOAD_CHUNK_SIZE_BYTES = (
    10
    * 1024
    * 1024
)
