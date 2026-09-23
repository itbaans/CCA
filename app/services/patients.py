from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Patient, utcnow
from app.schemas import PatientCreate, PatientUpdate


class PatientNotFoundError(Exception):
    pass


def list_patients(
    db: Session,
    *,
    last_name: str | None = None,
    date_of_birth: date | None = None,
    phone_number: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Patient], int]:
    filters = [Patient.deleted_at.is_(None)]
    if last_name:
        filters.append(func.lower(Patient.last_name) == last_name.lower())
    if date_of_birth:
        filters.append(Patient.date_of_birth == date_of_birth)
    if phone_number:
        filters.append(Patient.phone_number == phone_number)

    total = db.scalar(select(func.count()).select_from(Patient).where(*filters)) or 0
    patients = list(
        db.scalars(
            select(Patient)
            .where(*filters)
            .order_by(Patient.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return patients, total


def get_patient(db: Session, patient_id: str, *, include_deleted: bool = False) -> Patient:
    filters = [Patient.patient_id == patient_id]
    if not include_deleted:
        filters.append(Patient.deleted_at.is_(None))
    patient = db.scalar(select(Patient).where(*filters))
    if not patient:
        raise PatientNotFoundError(patient_id)
    return patient


def find_by_phone(db: Session, phone_number: str) -> Patient | None:
    return db.scalar(
        select(Patient)
        .where(Patient.phone_number == phone_number, Patient.deleted_at.is_(None))
        .order_by(Patient.updated_at.desc())
    )


def create_patient(db: Session, payload: PatientCreate) -> Patient:
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def update_patient(db: Session, patient_id: str, payload: PatientUpdate) -> Patient:
    patient = get_patient(db, patient_id)
    changes = payload.model_dump(exclude_unset=True)
    # Revalidate the resulting complete record so partial updates cannot null or
    # otherwise invalidate a required field before it reaches the database.
    current = {
        field: getattr(patient, field)
        for field in PatientCreate.model_fields
    }
    validated = PatientCreate.model_validate({**current, **changes})
    changes = {
        key: getattr(validated, key)
        for key in changes
    }
    for key, value in changes.items():
        setattr(patient, key, value)
    patient.updated_at = utcnow()
    db.commit()
    db.refresh(patient)
    return patient


def soft_delete_patient(db: Session, patient_id: str) -> Patient:
    patient = get_patient(db, patient_id)
    patient.deleted_at = utcnow()
    patient.updated_at = utcnow()
    db.commit()
    db.refresh(patient)
    return patient
