from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.database import Base


class Reading(Base):
    __tablename__ = "readings"

    id           = Column(Integer, primary_key=True, index=True)
    source       = Column(String, index=True)    # "forecast" | "air_quality"
    temperature  = Column(Float,   nullable=True) # °C  (solo forecast)
    windspeed    = Column(Float,   nullable=True) # km/h (solo forecast)
    weathercode  = Column(Integer, nullable=True) # WMO code (solo forecast)
    pm10         = Column(Float,   nullable=True) # µg/m³ (solo air_quality)
    european_aqi = Column(Integer, nullable=True) # indice EU (solo air_quality)
    latitude     = Column(Float,   nullable=False)
    longitude    = Column(Float,   nullable=False)
    fetched_at   = Column(DateTime, default=datetime.utcnow)
