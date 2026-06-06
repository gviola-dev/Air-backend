# Naples Weather & Air Quality — FastAPI + PostgreSQL su Railway

Demo funzionante che fetcha dati da **due API pubbliche Open-Meteo** (nessuna API key)
e li espone via REST.

## API sorgenti

| Sorgente | URL | Dati |
|---|---|---|
| `forecast` | api.open-meteo.com | temperatura, windspeed, weathercode |
| `air_quality` | air-quality-api.open-meteo.com | PM10, European AQI |

Coordinate fisse: **Napoli** (lat=40.85, lon=14.27)

---

## Avvio in locale

### Senza PostgreSQL (usa SQLite automaticamente)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Apri http://localhost:8000/docs

### Con PostgreSQL locale

```bash
cp .env.example .env
# modifica DATABASE_URL in .env
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## Deploy su Railway

1. Pusha il progetto su GitHub
2. Su [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Seleziona il repo
4. Clicca **+ Add Service** → **PostgreSQL** (Railway inietta `DATABASE_URL` in automatico)
5. Railway rileva il `Procfile` e avvia l'app

Al primo avvio:
- le tabelle vengono create automaticamente
- viene fatto subito un fetch delle due API
- uno scheduler esegue il fetch ogni 30 minuti

---

## Endpoints

| Metodo | Path | Descrizione |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/readings` | Legge i dati dal DB |
| `GET` | `/readings?source=forecast` | Solo dati meteo |
| `GET` | `/readings?source=air_quality` | Solo qualità dell'aria |
| `GET` | `/readings?skip=0&limit=20` | Paginazione |
| `POST` | `/fetch` | Forza fetch manuale |
| `GET` | `/docs` | Swagger UI |

---

## Chiamata dal frontend

```javascript
// Ultimi 20 dati meteo
const res = await fetch("https://your-app.up.railway.app/readings?source=forecast&limit=20");
const data = await res.json();

// Struttura risposta:
// [
//   {
//     "id": 1,
//     "source": "forecast",
//     "temperature": 24.5,
//     "windspeed": 12.3,
//     "weathercode": 1,
//     "pm10": null,
//     "european_aqi": null,
//     "latitude": 40.85,
//     "longitude": 14.27,
//     "fetched_at": "2024-06-05T10:30:00"
//   }
// ]
```
