# fakturaer-fra-prisme-til-ski

Processen opretter ét ATS-item pr. ISO-uge. Hvert item indeholder de originale OIOUBL-filer for ugens bogførte EFAK-kreditorfakturaer.


┌──────────────────────────────────────────────────────────────┐
│ START: Planlagt månedlig kørsel                              │
│ Eksempel: Den 25. i hver måned                              │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Beregn automatisk fakturaperiode                             │
│                                                              │
│ 1. Find den aktuelle ISO-uge                                │
│ 2. Gå ANTAL_UGER_FORSINKELSE tilbage                        │
│ 3. Find den seneste uge, der må behandles                   │
│ 4. Medtag ANTAL_UGER_TILBAGE komplette ISO-uger             │
│                                                              │
│ Eksempel:                                                    │
│ ANTAL_UGER_FORSINKELSE = 6                                  │
│ ANTAL_UGER_TILBAGE = 60                                     │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Find alle ISO-uger i perioden                               │
│                                                              │
│ Referencer opbygges som:                                    │
│                                                              │
│ uge 26 - 2025                                               │
│ uge 27 - 2025                                               │
│ uge 28 - 2025                                               │
│ ...                                                          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Kontrollér ATS-køen                                         │
│                                                              │
│ Findes uge-referencen allerede som fx:                      │
│                                                              │
│ • NEW                                                        │
│ • IN_PROGRESS                                                │
│ • COMPLETED                                                  │
│ • FAILED                                                     │
│ • PENDING_USER_ACTION                                        │
└───────────────────────┬───────────────────┬──────────────────┘
                        │ JA                │ NEJ
                        ▼                   ▼
          ┌──────────────────────┐   ┌─────────────────────────┐
          │ Spring ugen over     │   │ Ugen føjes til listen   │
          │                      │   │ over manglende uger     │
          │ Ingen Prisme-kald    │   └────────────┬────────────┘
          └──────────────────────┘                │
                                                  ▼
┌──────────────────────────────────────────────────────────────┐
│ Hent først alle API-data for de manglende uger              │
│                                                              │
│ For hver uge hentes tre separate lister:                    │
│                                                              │
│ 1. Kreditorposteringer fra VendTrans                        │
│ 2. Oprindelige fakturaposter fra VendInvoiceInfo            │
│ 3. OIOUBL-dokumentreferencer fra DocuRef                    │
│                                                              │
│ Hvis et kald rammer 10.000 rækker:                          │
│ Intervallet opdeles automatisk i mindre datointervaller      │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Saml alle resultater i Python                               │
│                                                              │
│ Data fra alle hentede uger er nu tilgængelige samtidigt     │
│                                                              │
│ VendTrans-liste                                              │
│ VendInvoiceInfo-liste                                        │
│ DocuRef-liste                                                │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Match kreditorpostering med oprindelig faktura              │
│                                                              │
│ Matchnøgle:                                                  │
│                                                              │
│ • Fakturanummer                                              │
│ • Kreditorkonto                                              │
│ • Fakturadato                                                │
│ • Absolut fakturabeløb                                       │
└───────────────────────┬───────────────────┬──────────────────┘
                        │ MATCH             │ INTET MATCH
                        ▼                   ▼
          ┌──────────────────────┐   ┌─────────────────────────┐
          │ Fortsæt lokalt       │   │ Lav præcist fallback-   │
          │ uden nyt API-kald    │   │ opslag på fakturanummer │
          └───────────┬──────────┘   │ og kreditorkonto        │
                      │              └────────────┬────────────┘
                      └───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Find OIOUBL-dokumenter                                      │
│                                                              │
│ VendInvoiceInfo.RecIdLoc matches med DocuRef.RefRecId       │
└───────────────────────┬───────────────────┬──────────────────┘
                        │ FUND              │ IKKE FUNDET
                        ▼                   ▼
          ┌──────────────────────┐   ┌─────────────────────────┐
          │ Brug dokumenterne    │   │ Lav præcist opslag på   │
          │ fra Python-listen    │   │ RefTableId og RefRecId  │
          └───────────┬──────────┘   └────────────┬────────────┘
                      └───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Behandl antal OIOUBL-filer                                  │
└───────────────┬───────────────────┬──────────────────────────┘
                │ 0 filer           │ 1 eller flere filer
                ▼                   ▼
┌──────────────────────────┐  ┌────────────────────────────────┐
│ Ignorér posteringen      │  │ Hent filnavn og dokumentsti   │
│                          │  │ for hver OIOUBL-fil            │
│ Skriv årsag i loggen     │  │                                │
│ Tæl den som ignoreret    │  │ Alle OIOUBL-filer medtages    │
└──────────────────────────┘  └───────────────┬────────────────┘
                                              │
                                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Opret ét ATS-item pr. uge                                   │
│                                                              │
│ Item-reference:                                              │
│ uge 26 - 2025                                               │
│                                                              │
│ Hver dokumentrække indeholder kun:                          │
│                                                              │
│ • fakturanummer                                              │
│ • kreditorkonto                                              │
│ • filnavn                                                    │
│ • dokumentsti                                                │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ WORKER: Hent næste uge-item                                 │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Klargør lokal tempmappe                                    │
│                                                              │
│ Eksempel:                                                    │
│ <temp>/uge 26 - 2025                                        │
│                                                              │
│ Eksisterende mappe og lokal ZIP for samme uge slettes       │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Download alle OIOUBL-filer via SMB                          │
│                                                              │
│ Filnavnet fra Prisme anvendes lokalt                        │
│                                                              │
│ Dubletter navngives:                                         │
│                                                              │
│ faktura.xml                                                  │
│ faktura (1).xml                                              │
│ faktura (2).xml                                              │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Opret lokal ZIP-fil                                        │
│                                                              │
│ Eksempel:                                                    │
│ uge 26 - 2025.zip                                           │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Validér lokal ZIP                                           │
│                                                              │
│ • ZIP-filen findes                                           │
│ • ZIP-formatet er gyldigt                                    │
│ • Ingen filer er beskadigede                                 │
│ • Forventet antal filer findes i ZIP-filen                  │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Upload ZIP til SharePoint                                   │
│                                                              │
│ Site: Automatisering                                        │
│                                                              │
│ Dokumenter                                                  │
│ └── RPA - Processer                                         │
│     └── fakturaer-fra-prisme-til-ski                       │
│         └── uge 26 - 2025.zip                              │
│                                                              │
│ Store filer uploades via upload session i bidder             │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Validér SharePoint-filen                                    │
│                                                              │
│ • Filnavn matcher                                            │
│ • SharePoint item-id matcher                                 │
│ • Filstørrelse matcher den lokale ZIP                       │
└───────────────────────┬───────────────────┬──────────────────┘
                        │ OK                 │ FEJL
                        ▼                   ▼
┌──────────────────────────────┐  ┌────────────────────────────┐
│ Gem SharePoint-oplysninger  │  │ Item bliver ikke Completed │
│ på ATS-itemet               │  │                            │
│                              │  │ Uploadet SharePoint-fil    │
│ Registrér SharePoint-stage   │  │ forsøges slettet igen      │
└───────────────┬──────────────┘  │                            │
                │                 │ Lokale tempfiler beholdes  │
                │                 │ til fejlsøgning            │
                │                 └────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────┐
│ Ryd op lokalt efter valideret SharePoint-upload             │
│                                                              │
│ • Slet arbejdsmappen med XML-filer                          │
│ • Slet den lokale ZIP-fil                                   │
│ • SharePoint-filen bevares                                  │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Markér ATS-itemet Completed                                 │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Fortsæt med næste uge-item                                  │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ SLUT                                                         │
│                                                              │
│ Alle færdige uge-ZIP-filer ligger i SharePoint.              │
└──────────────────────────────────────────────────────────────┘