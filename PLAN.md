# Billhound — MVP Implementation Blueprint

> **Sniffing out subscriptions you forgot about.**

---

## Brand Identity

| Element | Value |
|---------|-------|
| **Name** | Billhound |
| **Tagline** | "Sniffing out subscriptions you forgot about." |
| **Bot Handle** | @BillhoundBot |
| **Personality** | Loyal, vigilant, proactive — a trusted hound that never stops watching your wallet |
| **Tone** | Friendly but sharp. Casual enough for Telegram, serious enough for financial trust. |
| **Color Direction** | Deep navy (#1A2B4A) + amber/gold (#F5A623) — trust meets alertness |
| **Package Name** | `billhound` |

---

## Project Context

**What Billhound does:** Connects to Gmail/Outlook via OAuth, scans emails and bank/card PDF statements, builds a living subscription ledger, detects renewals/price hikes/redundant services/unconverted trials, and executes cancellations on user approval — all through Telegram.

**Who it's for:** Retail consumers (starting in Malaysia) who lose money through subscription bleed — forgotten trials, duplicate services, unnoticed price increases.

**Ecosystem position:** Billhound introduces shared email parsing and trust/privacy infrastructure reused by the subsequent Personal Finance Intelligence Agent.

**Primary market:** Malaysia (MYR currency, Malaysian banks like Maybank, CIMB, RHB)

---

## 1. Production Directory Structure

```
billhound/
├── pyproject.toml                    # PEP 621 project metadata + all dependencies
├── alembic.ini                       # Alembic migration config
├── .env.template                     # Environment variable template (never committed with values)
├── .gitignore
├── Makefile                          # make migrate, make test, make lint, make run
├── docker-compose.yml                # PostgreSQL 16 + Redis (for job scheduling)
│
├── src/
│   ├── __init__.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py               # pydantic-settings: typed config from env vars
│   │   ├── logging_config.py         # structlog: dev console / prod JSON
│   │   └── constants.py              # App-wide enums, default values, thresholds
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── engine.py                 # Async SQLAlchemy engine + session factory
│   │   ├── base.py                   # DeclarativeBase, TimestampMixin, UUIDPrimaryKeyMixin
│   │   ├── models/
│   │   │   ├── __init__.py           # Re-exports all models for Alembic discovery
│   │   │   ├── user.py               # User — telegram_id, timezone, preferences
│   │   │   ├── subscription.py       # Subscription ledger — the core entity
│   │   │   ├── oauth_token.py        # Encrypted OAuth credentials
│   │   │   ├── password_pattern.py   # AES-256 encrypted PDF password patterns
│   │   │   ├── cancellation_log.py   # Cancellation attempts + results + savings
│   │   │   └── audit_log.py          # Immutable compliance trail
│   │   └── repositories/
│   │       ├── __init__.py
│   │       ├── base.py               # Generic async CRUD repository
│   │       ├── user_repo.py          # + get_by_telegram_id()
│   │       ├── subscription_repo.py  # + get_active_by_user(), get_renewals_within()
│   │       ├── oauth_token_repo.py   # + get_by_provider()
│   │       ├── password_pattern_repo.py
│   │       ├── cancellation_log_repo.py  # + get_monthly_savings()
│   │       └── audit_log_repo.py     # Read-only: no update/delete exposed
│   │
│   ├── migrations/
│   │   ├── env.py                    # Alembic async migration environment
│   │   ├── script.py.mako            # Migration file template
│   │   └── versions/                 # Auto-generated migration files
│   │
│   ├── trust/                        # ── STANDALONE REUSABLE MODULE ──
│   │   ├── __init__.py               # Exports PrivacyManager as public API
│   │   ├── encryption.py             # AES-256-GCM encrypt/decrypt utility
│   │   ├── audit.py                  # Append-only audit log writer
│   │   ├── privacy_manager.py        # Facade: orchestrates export + deletion
│   │   ├── data_export.py            # /mydata: serialize all user data as JSON
│   │   ├── account_deletion.py       # /deleteaccount: revoke tokens, purge, receipt
│   │   ├── oauth_scope_display.py    # Human-readable OAuth scope descriptions
│   │   └── consent.py                # OAuth consent tracking + grant history
│   │
│   ├── email_ingestion/              # ── Phase 2 ──
│   │   ├── __init__.py
│   │   ├── oauth/
│   │   │   ├── __init__.py
│   │   │   ├── gmail.py              # Gmail OAuth 2.0 flow + token refresh
│   │   │   ├── outlook.py            # Microsoft OAuth flow + token refresh
│   │   │   └── router.py             # OAuth callback HTTP server (aiohttp)
│   │   ├── fetcher.py                # Async email fetcher (Gmail API / MS Graph)
│   │   ├── parser.py                 # Email body/header parser — IN-MEMORY ONLY
│   │   ├── filters.py                # Subscription keyword/sender pattern matching
│   │   └── scheduler.py              # Periodic inbox scan scheduler
│   │
│   ├── pdf/                          # ── Phase 2 ──
│   │   ├── __init__.py
│   │   ├── extractor.py              # PDF text extraction via pdfplumber
│   │   ├── decryptor.py              # Password pattern resolution + PDF unlock
│   │   └── statement_parser.py       # Bank statement → structured transaction data
│   │
│   ├── llm/                          # ── Phase 2 ──
│   │   ├── __init__.py
│   │   ├── base.py                   # Abstract LLM interface (model-agnostic)
│   │   ├── openai_provider.py        # OpenAI implementation
│   │   ├── anthropic_provider.py     # Anthropic implementation
│   │   ├── prompts.py                # Prompt templates for subscription extraction
│   │   └── extraction_pipeline.py    # Orchestrator: raw text → structured sub data
│   │
│   ├── telegram/                     # ── Phase 3 ──
│   │   ├── __init__.py
│   │   ├── bot.py                    # Bot application bootstrap + lifecycle
│   │   ├── middleware.py             # Rate limiting, user auto-registration, audit
│   │   ├── keyboards.py             # Inline keyboard builders
│   │   ├── formatters.py            # Message formatting (alerts, reports, ledger)
│   │   └── handlers/
│   │       ├── __init__.py
│   │       ├── start.py              # /start, /help — onboarding flow
│   │       ├── oauth_connect.py      # /connect gmail, /connect outlook
│   │       ├── subscriptions.py      # /subscriptions — view/add/remove ledger
│   │       ├── cancel.py             # cancel <service> — initiate cancellation
│   │       ├── trust_commands.py     # /mydata, /deleteaccount
│   │       ├── settings.py           # /settings — password patterns, preferences
│   │       └── callbacks.py          # Inline keyboard callback dispatcher
│   │
│   ├── automation/                   # ── Phase 4 ──
│   │   ├── __init__.py
│   │   ├── browser.py                # Playwright browser manager (lifecycle, pools)
│   │   ├── base_flow.py              # Abstract cancellation flow interface
│   │   ├── screenshot.py             # Screenshot capture + cloud/local storage
│   │   ├── fallback.py               # Direct cancellation link + instructions
│   │   └── flows/
│   │       ├── __init__.py
│   │       ├── registry.py           # Service name → flow class mapping
│   │       ├── netflix.py
│   │       ├── spotify.py
│   │       ├── adobe.py
│   │       └── ...                   # Top 20 services (list TBD with client)
│   │
│   ├── services/                     # ── Business Logic Layer ──
│   │   ├── __init__.py
│   │   ├── subscription_service.py   # Detect, categorize, deduplicate, alert logic
│   │   ├── renewal_monitor.py        # Periodic renewal check + Telegram alert dispatch
│   │   ├── savings_tracker.py        # Monthly savings calculation + report generation
│   │   └── merchant_db.py            # Merchant → category mapping database
│   │
│   └── main.py                       # Application entrypoint: wire + start
│
└── tests/
    ├── __init__.py
    ├── conftest.py                   # Shared fixtures: async DB, mock bot, factories
    ├── factories.py                  # Factory Boy model factories
    ├── unit/
    │   ├── __init__.py
    │   ├── test_encryption.py
    │   ├── test_trust_module.py
    │   ├── test_email_parser.py
    │   ├── test_pdf_extractor.py
    │   ├── test_llm_pipeline.py
    │   └── test_subscription_service.py
    ├── integration/
    │   ├── __init__.py
    │   ├── test_db_repositories.py
    │   ├── test_oauth_flow.py
    │   ├── test_email_ingestion.py
    │   ├── test_telegram_handlers.py
    │   └── test_cancellation_flows.py
    └── e2e/
        ├── __init__.py
        └── test_full_pipeline.py
```

---

## 2. Chronological MVP Roadmap

### Phase 1: Foundation — Scaffolding + Database + Trust Module
**Goal:** Runnable project skeleton. Database migrates. Encryption works. Trust module fully functional. Tests pass.

**Deliverables:**
- Project config: pyproject.toml, docker-compose.yml, .env.template, Makefile, .gitignore
- `src/config/` — pydantic-settings, structlog logging, constants/enums
- `src/db/` — Async SQLAlchemy engine, DeclarativeBase + mixins, all 6 models, all 7 repositories
- `src/migrations/` — Alembic async env + initial schema migration
- `src/trust/` — Full standalone module: AES-256-GCM encryption, audit writer, data export, account deletion, OAuth scope display, privacy manager facade, consent tracker
- `src/main.py` — Minimal entrypoint (config + DB init)
- `tests/` — conftest, factories, unit tests for encryption + trust

**Terminal setup:**
```bash
cd "C:\Users\ruben\Desktop\Virtuals Notion Request"
mkdir billhound && cd billhound
python -m venv .venv && source .venv/Scripts/activate
pip install "sqlalchemy[asyncio]>=2.0" "asyncpg>=0.30" "alembic>=1.14" \
  "pydantic>=2.10" "pydantic-settings>=2.7" "cryptography>=44.0" \
  "structlog>=24.4" "python-dotenv>=1.0"
pip install "pytest>=8.3" "pytest-asyncio>=0.24" "factory-boy>=3.3" \
  "ruff>=0.8" "mypy>=1.13" "coverage>=7.6"
docker-compose up -d
alembic revision --autogenerate -m "001_initial_schema"
alembic upgrade head
pytest tests/ -v
```

---

### Phase 2: Intelligence — Email OAuth + PDF + LLM Pipeline
**Goal:** Connect email accounts. Scan inboxes. Extract subscription data from emails and PDF statements. Populate the ledger automatically.

**Deliverables:**
- `src/email_ingestion/oauth/` — Gmail OAuth 2.0 + Outlook OAuth flows + aiohttp callback server
- `src/email_ingestion/` — Async email fetcher, in-memory parser, subscription keyword filters, periodic scheduler
- `src/pdf/` — pdfplumber extraction, AES-256 password decryption, bank statement parser
- `src/llm/` — Abstract LLM interface, OpenAI + Anthropic providers, prompt templates, extraction pipeline
- `src/services/subscription_service.py` — Detection, categorization, deduplication logic
- `src/services/merchant_db.py` — Merchant-to-category mapping
- Tests: email parser, PDF extractor, LLM pipeline, OAuth flow

---

### Phase 3: Interface — Telegram Bot + Alerts + Reports
**Goal:** Full Telegram interaction. Users onboard, view ledger, receive proactive alerts, manage subscriptions.

**Deliverables:**
- `src/telegram/bot.py` — Bot bootstrap with python-telegram-bot
- `src/telegram/handlers/` — All 7 handler modules (/start, /connect, /subscriptions, /cancel, /mydata, /deleteaccount, /settings)
- `src/telegram/` — Inline keyboards, message formatters (renewal alerts, savings reports), middleware (rate limiting, auto-registration, audit logging)
- `src/services/renewal_monitor.py` — Periodic scan, 7-day/3-day/1-day alert dispatch
- `src/services/savings_tracker.py` — Monthly savings calculation + Telegram report
- Tests: handler tests, middleware tests

---

### Phase 4: Automation — Playwright Cancellation Flows
**Goal:** Automated cancellation execution for top services. Screenshot evidence. Fallback instructions for unsupported services.

**Deliverables:**
- `src/automation/browser.py` — Playwright browser lifecycle + context pool management
- `src/automation/base_flow.py` — Abstract CancellationFlow interface
- `src/automation/flows/` — Pre-built flows for top 10-20 services + registry
- `src/automation/screenshot.py` — Capture + storage (local or S3)
- `src/automation/fallback.py` — Direct cancellation link generation + instruction templates
- Dockerfile for production deployment (Railway/Render)
- Tests: cancellation flow tests, E2E pipeline test

---

## 3. Database Schema

### users
| Column | Type | Constraint |
|--------|------|------------|
| id | UUID | PK, default uuid4 |
| telegram_id | BIGINT | UNIQUE, indexed |
| telegram_username | VARCHAR(255) | nullable |
| display_name | VARCHAR(255) | nullable |
| is_active | BOOLEAN | default true |
| timezone | VARCHAR(50) | default "Asia/Kuala_Lumpur" |
| created_at | TIMESTAMPTZ | server default now() |
| updated_at | TIMESTAMPTZ | auto-update on change |

### subscriptions
| Column | Type | Constraint |
|--------|------|------------|
| id | UUID | PK |
| user_id | UUID | FK users.id CASCADE |
| service_name | VARCHAR(255) | NOT NULL |
| category | VARCHAR(100) | nullable (streaming, SaaS, fitness, etc.) |
| amount | NUMERIC(12,2) | NOT NULL |
| currency | VARCHAR(3) | default "MYR" |
| billing_cycle | ENUM | weekly / monthly / quarterly / semi_annual / annual / unknown |
| next_renewal_date | DATE | nullable |
| trial_end_date | DATE | nullable |
| status | ENUM | active / trial / cancelled / expired / paused / pending_confirmation |
| confidence_score | NUMERIC(3,2) | default 1.00 (range 0.00–1.00) |
| source_email_subject | TEXT | nullable — metadata only, raw email never stored |
| is_manually_added | BOOLEAN | default false |
| last_price | NUMERIC(12,2) | nullable — enables price hike detection |
| price_change_detected_at | TIMESTAMPTZ | nullable |
| cancellation_url | TEXT | nullable |
| created_at / updated_at | TIMESTAMPTZ | standard timestamps |

### oauth_tokens
| Column | Type | Constraint |
|--------|------|------------|
| id | UUID | PK |
| user_id | UUID | FK users.id CASCADE |
| provider | VARCHAR(20) | "gmail" or "outlook" |
| access_token_encrypted | TEXT | AES-256-GCM encrypted |
| refresh_token_encrypted | TEXT | AES-256-GCM encrypted |
| token_expiry | TIMESTAMPTZ | NOT NULL |
| scopes_granted | TEXT | comma-separated scope list |
| email_address | VARCHAR(320) | NOT NULL |
| created_at / updated_at | TIMESTAMPTZ | |

### password_patterns
| Column | Type | Constraint |
|--------|------|------------|
| id | UUID | PK |
| user_id | UUID | FK users.id CASCADE |
| bank_name | VARCHAR(255) | e.g. "Maybank", "CIMB" |
| pattern_description | TEXT | plaintext (e.g. "last 4 digits of IC") |
| password_encrypted | TEXT | AES-256-GCM encrypted resolved value |
| sender_email_pattern | VARCHAR(320) | e.g. "statement@maybank.com" |
| created_at / updated_at | TIMESTAMPTZ | |

### cancellation_logs
| Column | Type | Constraint |
|--------|------|------------|
| id | UUID | PK |
| user_id | UUID | FK users.id CASCADE |
| subscription_id | UUID | FK subscriptions.id SET NULL |
| service_name | VARCHAR(255) | NOT NULL |
| status | ENUM | initiated / in_progress / success / failed / manual_required |
| method | VARCHAR(50) | "automated" or "manual_link" |
| screenshot_path | TEXT | nullable |
| error_message | TEXT | nullable |
| confirmed_saving_amount | NUMERIC(12,2) | nullable |
| confirmed_saving_currency | VARCHAR(3) | nullable |
| completed_at | TIMESTAMPTZ | nullable |
| created_at / updated_at | TIMESTAMPTZ | |

### audit_log (APPEND-ONLY — no update, no delete)
| Column | Type | Constraint |
|--------|------|------------|
| id | UUID | PK |
| user_id | UUID | FK users.id SET NULL |
| action | VARCHAR(100) | indexed (oauth_granted, account_deleted, etc.) |
| entity_type | VARCHAR(50) | nullable |
| entity_id | VARCHAR(36) | nullable |
| details | JSONB | nullable |
| ip_address | VARCHAR(45) | nullable |
| created_at | TIMESTAMPTZ | indexed — NO updated_at column |

---

## 4. Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Language** | Python 3.12+ | Async ecosystem, LLM library support |
| **Interaction** | Telegram Bot API (python-telegram-bot) | Primary channel; WhatsApp/Discord as future pipeline |
| **Database** | PostgreSQL 16 + asyncpg | JSONB for audit details, robust ENUM support |
| **ORM** | SQLAlchemy 2.0 (async) | Type-safe, mature, async-native |
| **Migrations** | Alembic | Standard for SQLAlchemy, async support |
| **Config** | pydantic-settings | Typed env vars, validation, .env support |
| **Logging** | structlog | Structured JSON in prod, colored console in dev |
| **Encryption** | cryptography (AES-256-GCM) | Authenticated encryption with tamper detection |
| **Email** | Gmail OAuth 2.0 + Outlook OAuth | Read-only scope, scoped to subscription patterns |
| **PDF** | pdfplumber | Superior table extraction vs PyPDF2 |
| **LLM** | Model-agnostic (OpenAI / Anthropic) | Abstract interface, swap providers freely |
| **Automation** | Playwright | Headless browser cancellation flows |
| **Deployment** | Railway or Render | Simple container hosting, PostgreSQL add-on |
| **Testing** | pytest + pytest-asyncio + Factory Boy | Async-native, model factories |
| **Linting** | ruff + mypy | Fast linting + strict type checking |

---

## 5. Architecture Principles

1. **AES-256-GCM encryption** — Authenticated encryption with 12-byte random nonce prepended to ciphertext. Tamper detection built-in. Used for OAuth tokens and PDF passwords.

2. **Repository pattern** — Every model gets a typed async repository. Isolates DB access from business logic. Enables trivial mocking in tests.

3. **Trust module is standalone** — `src/trust/` imports ONLY from `src/db/` and `src/config/`. Zero dependency on telegram, email, or automation packages. Extractable as a shared library for the Personal Finance Intelligence Agent.

4. **Audit log is append-only** — No `updated_at` column. No update/delete methods. `AuditWriter` exposes only `log()`. Compliance-ready.

5. **Raw email content never persisted** — Processed in-memory, discarded after extraction. Only `source_email_subject` stored on Subscription for traceability.

6. **OAuth tokens encrypted at rest** — Decrypted only at the moment of API call execution, never held in decrypted form beyond the call scope.

7. **Confidence scoring** — Every detected subscription gets a 0.00–1.00 score. Below configurable threshold (default 0.70) → `PENDING_CONFIRMATION` status → user verification prompt.

8. **Cancellation registry pattern** — `flows/registry.py` maps service names to flow classes. Adding a new service = one Python file + one registry entry. No other code changes.

9. **Local-first processing** — All data processing happens server-side. No raw data leaves the processing pipeline. Only structured, extracted data is persisted.

---

## 6. MVP Success Criteria (from PRD)

- [ ] Gmail and Outlook OAuth connect with read-only scoped access
- [ ] All active subscriptions detected within 48 hours of email connection
- [ ] Password-protected PDFs unlocked using stored patterns
- [ ] Renewal alerts delivered minimum 7 days before charge date
- [ ] Price hike detected and flagged within 24 hours of notification email
- [ ] Cancellation executed for minimum 10 of top 20 services
- [ ] `/mydata` returns all stored user data correctly
- [ ] `/deleteaccount` revokes OAuth, deletes all data, confirms via email
- [ ] Monthly savings report delivered in Telegram
- [ ] Confirmed savings tracked and reported

---

## 7. Error Handling Strategy

| Scenario | User-facing Response |
|----------|---------------------|
| OAuth connection fails | "Couldn't connect your email — try again or check permissions." |
| PDF password incorrect | "I couldn't unlock your [Bank] statement — reply with the correct password format." |
| Cancellation automation fails | "Couldn't cancel automatically — here's the direct cancellation link: [url]" |
| Low-confidence subscription | "I think this might be a subscription — can you confirm? [details]" |
| Email scan finds nothing | "No subscriptions detected yet. I'll keep watching and alert you when I find something." |
| Rate limit hit | "You're moving fast! Please wait a moment before trying again." |

---

## 8. Out of Scope (MVP)

- Negotiation with service providers for better rates
- B2B/corporate subscription management
- WhatsApp and Discord channels (pipeline for post-MVP)
- Price negotiation scripts
- Corporate plan detection
- Multi-language support (English-first for MVP)

---

## 9. Phase Roadmap Summary

| Phase | Focus | Key Outcome |
|-------|-------|-------------|
| **Phase 1** | Foundation | DB + Trust module + encryption + tests pass |
| **Phase 2** | Intelligence | Email connected, subscriptions detected, ledger populated |
| **Phase 3** | Interface | Full Telegram bot live, alerts flowing, ledger viewable |
| **Phase 4** | Automation | Cancellations executing, screenshots captured, savings tracked |

---

## 10. API Keys Required

| Key | Purpose | Phase |
|-----|---------|-------|
| Telegram Bot Token | @BillhoundBot interaction | Phase 3 |
| Gmail OAuth Client ID + Secret | Email connection (read-only) | Phase 2 |
| Outlook OAuth Client ID + Secret | Email connection (read-only) | Phase 2 |
| LLM API Key (OpenAI or Anthropic) | Subscription pattern extraction | Phase 2 |
