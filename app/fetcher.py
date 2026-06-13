"""
Logica di fetch e parsing dati ARPAC Campania.
Nessun accesso al DB — tutte le funzioni sono pure rispetto allo stato.
"""
import logging
import re
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import httpx
import pandas as pd

logger = logging.getLogger("arpac")

ARPAC_VALIDATED_PACKAGE_URL = (
    "https://dati.arpacampania.it/api/3/action/package_show"
    "?id=dati-rqa-giornalieri-validati"
)
ARPAC_DATASTORE_URL = "https://dati.arpacampania.it/api/3/action/datastore_search"
ARPAC_METADATA_CSV_URL = (
    "https://dati.arpacampania.it/dataset/96eba21b-4191-4985-9205-e3b1800ad42a"
    "/resource/28bce378-02fe-4ff0-bc09-f598378389e6"
    "/download/metadati-stazioni-rqa-1.csv"
)

# Pattern latitudine Campania (40.x o 41.x)
LAT_PATTERN = re.compile(r"^4[01]\.\d+$")

# campo "Inquinante" CKAN -> colonna in misurazioni
# "Stazione" nei dataset CKAN e' il Codice Arpac (es. IT0898A), non il codice numerico
POLLUTANT_MAP: Dict[str, str] = {
    "PM10":  "pm10",
    "PM2.5": "pm25",
    "PM25":  "pm25",
    "NO2":   "no2",
    "NOX":   "no2",
    "CO":    "co",
    "O3":    "o3",
    "SO2":   "so2",
}


def fetch_centraline_csv() -> pd.DataFrame:
    """
    Scarica e parsa il CSV dei metadati delle stazioni ARPAC.

    Il CSV ha virgole non quotate nel campo indirizzo, quindi il parsing
    individua la colonna latitudine per ricostruire i campi correttamente.

    Returns
    -------
    pd.DataFrame
        Colonne: codice_nazionale, codice_arpac, provincia, indirizzo,
        tipo, latitudine, longitudine.
    """
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        r = client.get(ARPAC_METADATA_CSV_URL)
        r.raise_for_status()

    df_raw = pd.read_csv(
        StringIO(r.text), header=None, encoding_errors="replace", skiprows=1
    )
    righe_corrette = []

    for _, row in df_raw.iterrows():
        cells = [str(v).strip() if pd.notna(v) else "" for v in row.tolist()]

        # Il CSV ha 7 colonne fisse prima dell'indirizzo (include "Zona" non documentata):
        # [0]Rete [1]Zona [2]Nome [3]Cod.Europeo [4]Cod.Nazionale [5]Cod.Arpac [6]Provincia
        # L'indirizzo parte da cells[7] ed è spezzato da virgole non quotate.
        lat_idx = next(
            (i for i in range(8, 25) if LAT_PATTERN.match(cells[i])),
            None,
        )
        if lat_idx is None:
            continue

        codice_europeo   = cells[3]
        codice_nazionale = cells[4]   # numerico, es. 1506370
        codice_arpac     = cells[5]   # IT-format, es. IT2219A — chiave usata da CKAN "Stazione"
        provincia        = cells[6]   # es. "Napoli"
        tipo             = cells[lat_idx - 1]
        indirizzo        = ", ".join(p for p in cells[7 : lat_idx - 1] if p)
        lat              = cells[lat_idx]
        lon              = cells[lat_idx + 1] if lat_idx + 1 < len(cells) else ""

        righe_corrette.append([
            codice_europeo, codice_nazionale, codice_arpac,
            provincia, indirizzo, tipo, lat, lon,
        ])

    if not righe_corrette:
        raise ValueError("Nessuna stazione valida trovata nel CSV ARPAC")

    df = pd.DataFrame(
        righe_corrette,
        columns=[
            "codice_europeo", "codice_nazionale", "codice_arpac",
            "provincia", "indirizzo", "tipo", "latitudine", "longitudine",
        ],
    )
    df = df[df["tipo"] != "MOBILE"].copy()
    # Escludi stazioni STIR e simili senza codice ARPAC valido (codice_arpac = "nd")
    # — non hanno un identificatore univoco e non compaiono nei dataset CKAN
    df = df[~df["codice_arpac"].isin(["nd", ""])].copy()
    df = df.drop_duplicates(subset=["codice_arpac"]).copy()
    df["latitudine"]  = pd.to_numeric(df["latitudine"],  errors="coerce")
    df["longitudine"] = pd.to_numeric(df["longitudine"], errors="coerce")
    df = df.dropna(subset=["latitudine", "longitudine"]).reset_index(drop=True)

    return df[[
        "codice_nazionale", "codice_arpac", "provincia",
        "indirizzo", "tipo", "latitudine", "longitudine",
    ]]


def get_validated_resource_map() -> Dict[str, str]:
    """Recupera {label -> resource_id} per tutti i dataset mensili validati ARPAC."""
    with httpx.Client(timeout=20) as client:
        r = client.get(ARPAC_VALIDATED_PACKAGE_URL)
        r.raise_for_status()
    return {res["name"]: res["id"] for res in r.json()["result"]["resources"]}


def month_labels_from(start: str) -> List[str]:
    """
    Genera etichette mensili da start al mese corrente incluso.

    Parameters
    ----------
    start : str
        Formato "MM-YYYY", es. "03-2023".
    """
    m, y = int(start[:2]), int(start[3:])
    now = datetime.now()
    labels: List[str] = []
    while (y, m) <= (now.year, now.month):
        labels.append(f"Dati RQA Orari Validati {m:02d}-{y}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return labels


def fetch_month_records(resource_id: str, page_size: int = 10_000) -> List[Dict[str, Any]]:
    """
    Scarica tutti i record di un dataset mensile CKAN con paginazione automatica.

    Parameters
    ----------
    resource_id : str
        ID risorsa CKAN del mese.
    page_size : int
        Record per pagina (massimo stabile dell'API CKAN).
    """
    all_records: List[Dict[str, Any]] = []
    offset = 0

    with httpx.Client(timeout=60) as client:
        while True:
            resp = client.get(
                ARPAC_DATASTORE_URL,
                params={"resource_id": resource_id, "limit": page_size, "offset": offset},
            )
            resp.raise_for_status()
            result = resp.json()["result"]
            records = result.get("records", [])
            all_records.extend(records)
            offset += len(records)
            if not records or offset >= result.get("total", 0):
                break

    return all_records


def parse_data_ora(s: str) -> Optional[datetime]:
    """Parsa il timestamp ARPAC validato (es. '01-06-2026 00:00:00 +01:00')."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%d-%m-%Y %H:%M:%S %z")
    except ValueError:
        return None


def parse_float(value: Any) -> Optional[float]:
    if value is None or str(value).strip() in ("", "n.d.", "N/A", "-"):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return None


def normalize_month_records(
    raw_records: List[Dict[str, Any]],
    centraline_map: Dict[str, int],
) -> List[Dict[str, Any]]:
    """
    Normalizza i record CKAN raggruppando per (centralina, timestamp).

    Ogni riga CKAN rappresenta un singolo inquinante; questa funzione aggrega
    in una riga unica per (centralina, timestamp) con tutti i valori.
    """
    grouped: Dict[Tuple[int, datetime], Dict[str, Any]] = {}

    for rec in raw_records:
        codice_arpac  = str(rec.get("Stazione", "")).strip()
        centralina_id = centraline_map.get(codice_arpac)
        if centralina_id is None:
            continue

        timestamp = parse_data_ora(str(rec.get("Data_ora", "")))
        if timestamp is None:
            continue

        key = (centralina_id, timestamp)
        if key not in grouped:
            grouped[key] = {
                "centralina_id": centralina_id,
                "timestamp": timestamp,
                "pm10": None, "pm25": None,
                "no2":  None, "co":   None,
                "o3":   None, "so2":  None,
            }

        campo = POLLUTANT_MAP.get(str(rec.get("Inquinante", "")).strip().upper())
        if campo:
            grouped[key][campo] = parse_float(rec.get("Valore"))

    return list(grouped.values())


def get_latest_resource_id() -> Optional[str]:
    """
    Restituisce il resource_id del dataset mensile più recente disponibile.
    Scorre a ritroso fino a 3 mesi se il mese corrente non è ancora pubblicato.
    """
    resource_map = get_validated_resource_map()
    now = datetime.now()
    m, y = now.month, now.year

    for _ in range(3):
        label = f"Dati RQA Orari Validati {m:02d}-{y}"
        if label in resource_map:
            logger.info("refresh_latest: dataset selezionato: %s", label)
            return resource_map[label]
        m -= 1
        if m == 0:
            m, y = 12, y - 1

    return None
