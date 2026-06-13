import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.fetcher import (
    fetch_centraline_csv,
    fetch_month_records,
    get_latest_resource_id,
    get_validated_resource_map,
    month_labels_from,
    normalize_month_records,
)
from app.models import CentralineArpac, Misurazione

logger = logging.getLogger("arpac")


# ── Helpers DB (chiamati da seed/refresh, non dagli endpoint HTTP) ────────────

def _load_centraline_map(session: Session) -> Dict[str, int]:
    rows = session.execute(
        select(CentralineArpac.codice_arpac, CentralineArpac.id)
    ).all()
    return {r.codice_arpac: r.id for r in rows}


def _latest_timestamp_per_centralina(session: Session) -> Dict[int, datetime]:
    rows = session.execute(
        select(
            Misurazione.centralina_id,
            func.max(Misurazione.timestamp).label("max_ts"),
        ).group_by(Misurazione.centralina_id)
    ).all()
    return {r.centralina_id: r.max_ts for r in rows}


def _bulk_insert_misurazioni(
    session: Session,
    rows: List[Dict[str, Any]],
    batch_size: int = 5_000,
) -> int:
    if not rows:
        return 0
    for i in range(0, len(rows), batch_size):
        stmt = pg_insert(Misurazione).values(rows[i : i + batch_size])
        session.execute(stmt.on_conflict_do_nothing(
            index_elements=["centralina_id", "timestamp"]
        ))
    return len(rows)


# ── Seed e refresh (eseguiti in background thread, usano SessionLocal) ────────

def seed_centraline() -> int:
    """
    Importa/aggiorna l'anagrafica delle stazioni ARPAC (upsert su codice_arpac).
    Sicuro da rieseguire.
    """
    df = fetch_centraline_csv()
    rows = df.to_dict(orient="records")

    with SessionLocal() as session:
        stmt = pg_insert(CentralineArpac).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["codice_arpac"],
            set_={
                "codice_nazionale": stmt.excluded.codice_nazionale,
                "provincia":        stmt.excluded.provincia,
                "indirizzo":        stmt.excluded.indirizzo,
                "tipo":             stmt.excluded.tipo,
                "latitudine":       stmt.excluded.latitudine,
                "longitudine":      stmt.excluded.longitudine,
            },
        )
        session.execute(stmt)
        session.commit()

    logger.info("seed_centraline: %d stazioni importate/aggiornate", len(rows))
    return len(rows)


def seed_historical_misurazioni(start: str = "03-2023") -> None:
    """
    Importa tutte le misurazioni validate da `start` al mese corrente.
    Sicuro da rieseguire (ON CONFLICT DO NOTHING).
    Richiede che seed_centraline() sia già stato eseguito.

    Parameters
    ----------
    start : str
        Formato "MM-YYYY". Default "03-2023" = primo mese disponibile ARPAC.
    """
    resource_map = get_validated_resource_map()
    labels = month_labels_from(start)
    logger.info("seed_historical: %d mesi da importare (%s -> oggi)", len(labels), start)

    with SessionLocal() as session:
        centraline_map = _load_centraline_map(session)
        if not centraline_map:
            raise RuntimeError("Nessuna centralina nel DB. Eseguire seed_centraline() prima.")
        logger.info("seed_historical: %d centraline nel DB", len(centraline_map))

        for label in labels:
            resource_id = resource_map.get(label)
            if resource_id is None:
                logger.warning("seed_historical: dataset non trovato: %s", label)
                continue
            logger.info("seed_historical: scaricando %s ...", label)
            raw  = fetch_month_records(resource_id)
            rows = normalize_month_records(raw, centraline_map)
            inserted = _bulk_insert_misurazioni(session, rows)
            session.commit()
            logger.info("seed_historical: %s -> %d record processati", label, inserted)


def refresh_latest() -> Dict[str, Any]:
    """
    Job orario: scarica il dataset mensile più recente e aggiunge solo le
    misurazioni successive all'ultimo timestamp già salvato per ogni centralina.
    """
    resource_id = get_latest_resource_id()
    if resource_id is None:
        logger.error("refresh_latest: nessun dataset recente disponibile")
        return {"inserted": 0, "resource_id": None}

    with SessionLocal() as session:
        centraline_map = _load_centraline_map(session)
        latest_ts_map  = _latest_timestamp_per_centralina(session)

        raw_records = fetch_month_records(resource_id)
        all_rows    = normalize_month_records(raw_records, centraline_map)

        # Epoch con timezone locale come sentinella per centraline senza dati
        _EPOCH = datetime.min.replace(tzinfo=datetime.now().astimezone().tzinfo)
        new_rows = [
            row for row in all_rows
            if row["timestamp"] > latest_ts_map.get(row["centralina_id"], _EPOCH)
        ]

        inserted = _bulk_insert_misurazioni(session, new_rows)
        session.commit()

    logger.info(
        "refresh_latest: %d nuove misurazioni inserite (resource: %s)",
        inserted, resource_id,
    )
    return {"inserted": inserted, "resource_id": resource_id}


# ── Query per gli endpoint HTTP ───────────────────────────────────────────────

def get_centraline(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[CentralineArpac]:
    return db.query(CentralineArpac).offset(skip).limit(limit).all()


def get_misurazioni(
    db: Session,
    centralina_id: int,
    skip: int = 0,
    limit: int = 100,
) -> List[Misurazione]:
    return (
        db.query(Misurazione)
        .filter(Misurazione.centralina_id == centralina_id)
        .order_by(Misurazione.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
