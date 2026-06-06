from sqlalchemy.orm import Session
from app.models import Reading
from typing import Optional


def save_reading(db: Session, source: str, latitude: float, longitude: float, **kwargs):
    record = Reading(source=source, latitude=latitude, longitude=longitude, **kwargs)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_readings(
    db: Session,
    source: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    query = db.query(Reading)
    if source:
        query = query.filter(Reading.source == source)
    return query.order_by(Reading.fetched_at.desc()).offset(skip).limit(limit).all()
