import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint("sex IN ('Male','Female','Other','Decline to Answer')", name="valid_sex"),
        CheckConstraint("length(state) = 2", name="state_length"),
        CheckConstraint("length(zip_code) IN (5, 10)", name="zip_length"),
        Index("ix_patients_lookup", "last_name", "date_of_birth", "phone_number"),
    )

    patient_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(254))
    address_line_1: Mapped[str] = mapped_column(String(200), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)
    insurance_provider: Mapped[str | None] = mapped_column(String(100))
    insurance_member_id: Mapped[str | None] = mapped_column(String(50))
    preferred_language: Mapped[str] = mapped_column(String(50), nullable=False, default="English")
    emergency_contact_name: Mapped[str | None] = mapped_column(String(101))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    calls: Mapped[list["CallSession"]] = relationship(back_populates="patient")


class CallSession(Base):
    __tablename__ = "call_sessions"

    call_sid: Mapped[str] = mapped_column(String(64), primary_key=True)
    caller_phone: Mapped[str | None] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="collecting")
    current_field: Mapped[str] = mapped_column(String(40), nullable=False, default="first_name")
    collected_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    transcript: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    retry_count: Mapped[int] = mapped_column(default=0)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.patient_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    patient: Mapped[Patient | None] = relationship(back_populates="calls")
