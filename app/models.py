from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class CentralineArpac(Base):
    __tablename__ = "centraline_arpac"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    codice_nazionale = Column(String, nullable=True, index=True)
    codice_arpac     = Column(String, nullable=False, unique=True, index=True)
    provincia        = Column(String, nullable=True)
    indirizzo        = Column(String, nullable=True)
    tipo             = Column(String, nullable=True)
    latitudine       = Column(Float, nullable=True)
    longitudine      = Column(Float, nullable=True)

    misurazioni = relationship(
        "Misurazione", back_populates="centralina", cascade="all, delete-orphan"
    )


class Misurazione(Base):
    __tablename__ = "misurazioni"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    centralina_id = Column(
        Integer, ForeignKey("centraline_arpac.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    pm10      = Column(Float, nullable=True)
    pm25      = Column(Float, nullable=True)
    no2       = Column(Float, nullable=True)
    co        = Column(Float, nullable=True)
    o3        = Column(Float, nullable=True)
    so2       = Column(Float, nullable=True)

    centralina = relationship("CentralineArpac", back_populates="misurazioni")

    __table_args__ = (
        UniqueConstraint(
            "centralina_id", "timestamp",
            name="uq_misurazioni_centralina_timestamp",
        ),
    )
