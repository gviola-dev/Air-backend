from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ReadingOut(BaseModel):
    id:           int
    source:       str
    temperature:  Optional[float] = None
    windspeed:    Optional[float] = None
    weathercode:  Optional[int]   = None
    pm10:         Optional[float] = None
    european_aqi: Optional[int]   = None
    latitude:     float
    longitude:    float
    fetched_at:   datetime

    class Config:
        from_attributes = True
