from contextlib import asynccontextmanager
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import SessionLocal, engine, get_db
from app.fetcher import fetch_and_store

# ── Crea le tabelle al primo avvio ────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)

# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler()


def scheduled_fetch():
    """Viene chiamata dallo scheduler ogni 30 minuti."""
    db = SessionLocal()
    try:
        fetch_and_store(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: fetch immediato + job periodico
    scheduled_fetch()
    scheduler.add_job(scheduled_fetch, "interval", minutes=30, id="auto_fetch")
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown(wait=False)


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Naples Weather & Air Quality",
    description=(
        "Fetcha dati da **Open-Meteo Forecast** e **Open-Meteo Air Quality** "
        "ogni 30 minuti e li espone via REST.\n\n"
        "Nessuna API key richiesta."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # ← in produzione metti l'URL del tuo frontend
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", summary="Health check")
def root():
    return {"status": "running", "docs": "/docs", "openapi": "/openapi.json"}


@app.get(
    "/readings",
    response_model=List[schemas.ReadingOut],
    summary="Leggi i dati dal DB",
)
def get_readings(
    source: Optional[str] = Query(
        None,
        description="Filtra per sorgente: `forecast` oppure `air_quality`",
    ),
    skip:  int = Query(0,  ge=0,              description="Offset"),
    limit: int = Query(50, ge=1, le=500,      description="Numero massimo di record"),
    db: Session = Depends(get_db),
):
    """
    Restituisce le letture salvate nel DB, dalla più recente alla meno recente.

    - **source**: filtra per `forecast` o `air_quality` (opzionale)
    - **skip / limit**: paginazione
    """
    return crud.get_readings(db, source=source, skip=skip, limit=limit)


@app.post("/fetch", summary="Forza fetch manuale")
def trigger_fetch(db: Session = Depends(get_db)):
    """
    Trigera immediatamente un fetch delle due API esterne.
    Utile per test o aggiornamenti on-demand.
    """
    results = fetch_and_store(db)
    return {"status": "ok", "results": results}
