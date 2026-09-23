import re
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator, model_validator

from app.constants import US_STATES

NAME_PATTERN = re.compile(r"^[A-Za-z]+(?:[ '-][A-Za-z]+)*$")
PHONE_PATTERN = re.compile(r"^[2-9]\d{2}[2-9]\d{6}$")
ZIP_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")
MEMBER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 -]{0,49}$")


def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if not PHONE_PATTERN.fullmatch(digits):
        raise ValueError("must be a valid 10-digit U.S. phone number")
    return digits


class PatientFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: Annotated[str, Field(min_length=1, max_length=50)]
    last_name: Annotated[str, Field(min_length=1, max_length=50)]
    date_of_birth: date
    sex: Literal["Male", "Female", "Other", "Decline to Answer"]
    phone_number: str
    email: EmailStr | None = None
    address_line_1: Annotated[str, Field(min_length=1, max_length=200)]
    address_line_2: Annotated[str, Field(max_length=100)] | None = None
    city: Annotated[str, Field(min_length=1, max_length=100)]
    state: str
    zip_code: str
    insurance_provider: Annotated[str, Field(max_length=100)] | None = None
    insurance_member_id: Annotated[str, Field(max_length=50)] | None = None
    preferred_language: Annotated[str, Field(min_length=1, max_length=50)] = "English"
    emergency_contact_name: Annotated[str, Field(max_length=101)] | None = None
    emergency_contact_phone: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not NAME_PATTERN.fullmatch(value):
            raise ValueError("must contain only letters, spaces, hyphens, or apostrophes")
        return value.title()

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_dob(cls, value):
        if isinstance(value, str) and "/" in value:
            try:
                return datetime.strptime(value, "%m/%d/%Y").date()
            except ValueError as exc:
                raise ValueError("must be a valid date in MM/DD/YYYY format") from exc
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("must not be in the future")
        if value < date(1900, 1, 1):
            raise ValueError("must be on or after 01/01/1900")
        return value

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in US_STATES:
            raise ValueError("must be a valid 2-letter U.S. state abbreviation")
        return normalized

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, value: str) -> str:
        if not ZIP_PATTERN.fullmatch(value):
            raise ValueError("must be a 5-digit ZIP code or ZIP+4")
        return value

    @field_validator("insurance_member_id")
    @classmethod
    def validate_member_id(cls, value: str | None) -> str | None:
        if value and not MEMBER_ID_PATTERN.fullmatch(value):
            raise ValueError("must be alphanumeric and may include spaces or hyphens")
        return value

    @field_validator(
        "email", "address_line_2", "insurance_provider", "insurance_member_id",
        "emergency_contact_name", "emergency_contact_phone", mode="before"
    )
    @classmethod
    def empty_to_none(cls, value):
        return None if value == "" else value


class PatientCreate(PatientFields):
    pass


class PatientUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: Annotated[str, Field(min_length=1, max_length=50)] | None = None
    last_name: Annotated[str, Field(min_length=1, max_length=50)] | None = None
    date_of_birth: date | None = None
    sex: Literal["Male", "Female", "Other", "Decline to Answer"] | None = None
    phone_number: str | None = None
    email: EmailStr | None = None
    address_line_1: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    address_line_2: Annotated[str, Field(max_length=100)] | None = None
    city: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    state: str | None = None
    zip_code: str | None = None
    insurance_provider: Annotated[str, Field(max_length=100)] | None = None
    insurance_member_id: Annotated[str, Field(max_length=50)] | None = None
    preferred_language: Annotated[str, Field(min_length=1, max_length=50)] | None = None
    emergency_contact_name: Annotated[str, Field(max_length=101)] | None = None
    emergency_contact_phone: str | None = None

    @model_validator(mode="after")
    def required_fields_cannot_be_null(self):
        required = {
            "first_name", "last_name", "date_of_birth", "sex", "phone_number",
            "address_line_1", "city", "state", "zip_code", "preferred_language",
        }
        null_required = [
            field for field in required
            if field in self.model_fields_set and getattr(self, field) is None
        ]
        if null_required:
            raise ValueError(f"required fields cannot be null: {', '.join(sorted(null_required))}")
        return self

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not NAME_PATTERN.fullmatch(value):
            raise ValueError("must contain only letters, spaces, hyphens, or apostrophes")
        return value.title() if value else value

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_dob(cls, value):
        if isinstance(value, str) and "/" in value:
            try:
                return datetime.strptime(value, "%m/%d/%Y").date()
            except ValueError as exc:
                raise ValueError("must be a valid date in MM/DD/YYYY format") from exc
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, value: date | None) -> date | None:
        if value and (value > date.today() or value < date(1900, 1, 1)):
            raise ValueError("must be between 01/01/1900 and today")
        return value

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if normalized not in US_STATES:
            raise ValueError("must be a valid 2-letter U.S. state abbreviation")
        return normalized

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, value: str | None) -> str | None:
        if value is not None and not ZIP_PATTERN.fullmatch(value):
            raise ValueError("must be a 5-digit ZIP code or ZIP+4")
        return value

    @field_validator("insurance_member_id")
    @classmethod
    def validate_member_id(cls, value: str | None) -> str | None:
        if value and not MEMBER_ID_PATTERN.fullmatch(value):
            raise ValueError("must be alphanumeric and may include spaces or hyphens")
        return value


class PatientRead(PatientFields):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    @field_serializer("created_at", "updated_at", "deleted_at", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class PatientList(BaseModel):
    items: list[PatientRead]
    total: int
    limit: int
    offset: int


class Envelope(BaseModel):
    data: object | None
    error: object | None = None
