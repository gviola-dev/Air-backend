from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CentralinaOut(BaseModel):
    id:               int
    codice_nazionale: Optional[str]   = None
    codice_arpac:     str
    provincia:        Optional[str]   = None
    indirizzo:        Optional[str]   = None
    tipo:             Optional[str]   = None
    latitudine:       Optional[float] = None
    longitudine:      Optional[float] = None

    class Config:
        from_attributes = True


class MisurazioneOut(BaseModel):
    id:            int
    centralina_id: int
    timestamp:     datetime
    pm10:          Optional[float] = None
    pm25:          Optional[float] = None
    no2:           Optional[float] = None
    co:            Optional[float] = None
    o3:            Optional[float] = None
    so2:           Optional[float] = None

    class Config:
        from_attributes = True
