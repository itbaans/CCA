# Data model

```mermaid
erDiagram
    PATIENTS ||--o{ CALL_SESSIONS : linked_after_confirmation
    PATIENTS {
      string patient_id PK "UUID"
      string first_name
      string last_name
      date date_of_birth
      string sex "constrained enum"
      string phone_number "indexed, 10 digits"
      string email "nullable"
      string address_line_1
      string address_line_2 "nullable"
      string city
      string state "2 letters"
      string zip_code "ZIP or ZIP+4"
      string insurance_provider "nullable"
      string insurance_member_id "nullable"
      string preferred_language
      string emergency_contact_name "nullable"
      string emergency_contact_phone "nullable"
      datetime created_at "UTC"
      datetime updated_at "UTC"
      datetime deleted_at "nullable soft-delete"
    }
    CALL_SESSIONS {
      string call_sid PK "Vapi call id"
      string caller_phone
      string status
      string current_field
      json collected_data
      json transcript
      int retry_count
      string patient_id FK "nullable"
      datetime created_at
      datetime updated_at
    }
```

`patients` is the canonical demographic record. `call_sessions` is a durable workflow record: it separates unconfirmed speech data from registered patient data and enables idempotent Vapi tool calls.

Application validation provides detailed field errors. Database constraints remain a second line of defense for sex values, state length, ZIP length, required columns, primary keys, and the call-to-patient foreign key. The composite lookup index covers assessment filters; phone also has its own index for duplicate detection.

Soft-deleted patients remain in storage for audit/recovery but are excluded from all public patient reads and duplicate matching.

