# Code Review (English)

This document summarizes a thorough review of the project codebase, including
key risks, recommendations, and per‑area scores.

## Findings (ordered by severity)

### High

1) **Hardcoded Keycloak client secret**
- File: `src/ui/auth.py`
- Problem: `KEYCLOAK_CLIENT_SECRET` has a default value in code.
- Risk: Secret leakage and compromised Keycloak client.
- Fix: Remove the default, require env var, and fail fast if missing.

2) **JWT verification uses untrusted audience**
- File: `src/ui/auth.py`
- Problem: `aud` is taken from an unverified token, issuer is not enforced.
- Risk: Accepting tokens from other clients/realms.
- Fix: Verify `issuer`, and enforce `audience=KEYCLOAK_CLIENT_ID`.

3) **Open CORS policy**
- File: `src/app/main.py`
- Problem: `allow_origins=["*"]` for API.
- Risk: Abuse from any origin in production.
- Fix: Restrict to known domains; add auth where possible.

### Medium

4) **Flaky time‑based tests**
- Files: `tests/test_dbcrud.py`, `tests/conftest.py`, `src/app/dbcrud.py`
- Problem: Tests compare against `datetime.now()` while fixtures are static.
- Risk: Non‑deterministic failures.
- Fix: Use a time freezer (`freezegun`) or shift fixtures to `now()`.

5) **Unsafe SQL insertion in ETL**
- File: `utils/data_loader.py`
- Problem: SQL built with f‑strings and per‑row commits.
- Risk: SQL injection and slow bulk imports.
- Fix: Parameterized inserts, `executemany`, or `COPY`.

6) **Logger handlers added on every import**
- Files: `src/app/base_logger.py`, `src/ui/utils/base_logger.py`
- Problem: Re‑adding handlers causes duplicate logs.
- Fix: Guard with `if not logger.handlers`.

### Low

7) **Import hacks and fallback loaders**
- Files: `src/ui/pages/*`, `src/ui/utils/data_loader.py`
- Problem: `sys.path` hacks and manual importlib fallbacks.
- Risk: Fragile runtime behavior, harder testing.
- Fix: Convert to a proper package layout, use relative imports.

8) **Absolute paths in utility scripts**
- File: `utils/config.py`
- Problem: Hardcoded user path.
- Risk: Breaks on other machines/CI.
- Fix: Resolve from project root or env.

## Recommendations

### Security
- Enforce strict JWT validation (`aud`, `iss`, `exp`).
- Remove secrets from code and require env vars.
- Lock down CORS in production.

### Backend/API
- Replace `create_all()` on startup with Alembic migrations.
- Add rate limiting (API gateway or FastAPI middleware).
- Consolidate DB configuration to a single helper.

### Data/ETL
- Use bulk insert with parameterized queries.
- Add basic input validation and error handling for ingestion scripts.

### UI
- Remove `sys.path` hacks and fallback imports.
- Centralize data‑loading into one utility module.

### Testing
- Freeze time in tests.
- Add coverage for forecasting and anomaly detection.

## Scores (0–10)

- **Backend API (FastAPI): 6.5/10** — solid structure, needs auth + migrations.
- **DB/CRUD: 6/10** — functional, but batch and time handling are weak.
- **Forecasting/ML: 6/10** — good features, light on tests.
- **UI (Streamlit): 5.5/10** — powerful but fragile import flow.
- **Auth/Security: 3/10** — exposed secrets and weak token checks.
- **Tests: 7/10** — good CRUD/API coverage, flaky time logic.
- **DevOps/Docker: 5.5/10** — usable, but healthchecks and config cleanup needed.
- **ETL/Utils: 4.5/10** — helpful scripts, but unsafe SQL and paths.
- **Docs: 7/10** — good structure and coverage.

## Suggested Fix Plan

### Phase 1 — Security and exposure (highest priority)
1) Remove secrets from code, require env‑vars only.
2) Enforce JWT validation (`aud`, `iss`, `exp`) and enable PKCE if needed.
3) Restrict CORS to known domains and add auth to API endpoints.

### Phase 2 — Reliability and correctness
4) Fix flaky tests with time freezing (e.g., `freezegun`) or dynamic fixtures.
5) Replace `create_all()` with Alembic migrations.
6) Consolidate DB config to a single helper (one source of truth).

### Phase 3 — Data ingestion and performance
7) Replace f‑string SQL with parameterized bulk inserts.
8) Add input validation + error handling for ETL scripts.

### Phase 4 — Maintainability
9) Remove `sys.path` hacks and fallback import logic in UI.
10) Package UI/app into proper modules with explicit imports.

## Patch References (this review session)

- Logger handler guards and stable log path:
  - `src/app/base_logger.py`
  - `src/ui/utils/base_logger.py`
- Portable config script:
  - `utils/config.py`
- DB helper for shared session/engine:
  - `src/app/db_helper.py`
- Usage scripts updated to use helper:
  - `src/app/dbcrud_usage.py`
  - `src/app/fact_crud_usage.py`
  - `src/app/prophet_forecast_usage.py`
