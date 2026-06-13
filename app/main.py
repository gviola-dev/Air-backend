import logging
import threading
from contextlib import asynccontextmanager
from typing import List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("arpac")

_scheduler: BackgroundScheduler | None = None
HISTORICAL_START = "03-2023"


def _run_seed() -> None:
    """Eseguito in background thread all'avvio: non blocca il server."""
    try:
        logger.info("=== SEED centraline ===")
        crud.seed_centraline()
        logger.info("=== SEED misurazioni storiche da %s ===", HISTORICAL_START)
        crud.seed_historical_misurazioni(HISTORICAL_START)
        logger.info("=== Seed completato ===")
    except Exception:
        logger.exception("Errore durante il seed iniziale")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    init_db()
    threading.Thread(target=_run_seed, daemon=True).start()
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        crud.refresh_latest,
        trigger=IntervalTrigger(hours=1),
        id="refresh_arpac_latest",
        replace_existing=True,
        next_run_time=None,  # prima esecuzione al prossimo tick, il seed copre il mese corrente
    )
    _scheduler.start()
    logger.info("Scheduler ARPAC avviato")
    yield
    _scheduler.shutdown(wait=False)


app = FastAPI(
    title="Air Quality ARPAC Campania",
    description=(
        "Dati qualità dell'aria ARPAC Campania — stazioni di monitoraggio e misurazioni "
        "validate. Aggiornamento automatico ogni ora."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/", summary="Health check")
def root():
    return {"status": "running", "docs": "/docs"}


@app.get(
    "/centraline",
    response_model=List[schemas.CentralinaOut],
    summary="Lista stazioni ARPAC",
)
def list_centraline(
    skip:  int = Query(0,   ge=0,         description="Offset"),
    limit: int = Query(100, ge=1, le=500, description="Numero massimo di stazioni"),
    db: Session = Depends(get_db),
):
    return crud.get_centraline(db, skip=skip, limit=limit)


@app.get(
    "/centraline/{centralina_id}/misurazioni",
    response_model=List[schemas.MisurazioneOut],
    summary="Serie temporale inquinanti per una stazione",
)
def get_misurazioni(
    centralina_id: int,
    skip:  int = Query(0,   ge=0,           description="Offset"),
    limit: int = Query(100, ge=1, le=1_000, description="Numero massimo di misurazioni"),
    db: Session = Depends(get_db),
):
    return crud.get_misurazioni(db, centralina_id=centralina_id, skip=skip, limit=limit)
