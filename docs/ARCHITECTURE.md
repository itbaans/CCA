# Architecture

## Component map

```mermaid
flowchart TB
    Caller((Caller)) -->|PSTN| Vapi[Vapi number and voice agent]
    Vapi -->|function tool calls| VapiAPI[Vapi webhook adapter]
    Vapi -->|end-of-call report| VapiAPI
    VapiAPI --> VapiService[Vapi service]
    VapiService --> Schemas[Pydantic validation]
    VapiService --> PatientService[Patient service]
    Staff((Staff user)) --> Dashboard[Light dashboard]
    Dashboard -->|JSON| PatientAPI[Patient REST API]
    PatientAPI --> Schemas
    PatientAPI --> PatientService
    PatientService --> DB[(SQLite patients)]
    VapiService --> Calls[(SQLite call sessions)]
```

Vapi handles the live conversation and the FastAPI application remains the validation and persistence boundary. Model-provided values are never written directly to the database.

## Responsibilities

| Component | Owns | Does not own |
|---|---|---|
| Vapi assistant | Speech, turn-taking, corrections, read-back, tool selection | Final validation or persistence |
| Vapi webhook adapter | Secret authentication and event routing | Patient business rules |
| Vapi service | Tool contract, idempotency, duplicate consent, transcript ingestion | HTTP presentation |
| Pydantic schemas | Normalization and demographic validation | Persistence |
| Patient service | Queries, create/update, and soft-delete | Voice behavior |
| SQLAlchemy models | Tables, types, indexes, constraints, and relations | Request validation |
| Dashboard | Staff search, create, edit, and delete UI | Business rules |
| FastAPI app | Composition, lifecycle, errors, and logging | Telephony transport |

## Registration sequence

```mermaid
sequenceDiagram
    actor C as Caller
    participant V as Vapi
    participant W as FastAPI webhook
    participant S as Patient service
    participant D as SQLite
    C->>V: Calls free U.S. number
    V->>C: Collects demographics naturally
    V->>W: check_existing_patient(phone)
    W->>D: Query active patient
    W-->>V: found plus name or not found
    V->>C: Offers optional fields and reads everything back
    C->>V: Explicit confirmation
    V->>W: save_patient_registration(all fields)
    W->>W: Validate and enforce confirmation
    W->>S: Create or approved update
    S->>D: Commit patient
    W->>D: Commit call ID for idempotency
    W-->>V: Success action and patient ID
    V-->>C: Confirmation and goodbye
    V->>W: End-of-call report and transcript
```

## Failure boundaries

```mermaid
flowchart LR
    Tool[Tool call] --> Auth{Secret valid?}
    Auth -->|no| Reject[401 reject]
    Auth -->|yes| Validate{Payload valid?}
    Validate -->|no| Reprompt[Tool error tells agent which field]
    Validate -->|yes| Confirm{confirmed true?}
    Confirm -->|no| Refuse[No write]
    Confirm -->|yes| Duplicate{Phone exists?}
    Duplicate -->|yes, no consent| Offer[Return duplicate instruction]
    Duplicate -->|no or approved| Commit{Database commit}
    Commit -->|success| Done[Return created or updated]
    Commit -->|failure| Rollback[Rollback and safe error]
```

The Vapi call ID is stored with the committed patient. If Vapi retries the save tool, the service returns the prior result rather than creating a duplicate. Incomplete calls may store transcripts but never create patient records.

## Directory guide

```text
app/
├── api/                 REST, dashboard, health, and Vapi adapters
├── services/            Vapi and patient business logic
├── static/              Light dashboard assets
├── templates/           Dashboard HTML
├── config.py            Environment-backed settings
├── database.py          Engine and session lifecycle
├── models.py            Persistent entities and constraints
├── schemas.py           API and domain validation
└── main.py              Application composition and errors
vapi/                    Assistant prompt and function-tool schemas
tests/                   API, persistence, dashboard, and Vapi tests
docs/                    Operator and developer documentation
```
