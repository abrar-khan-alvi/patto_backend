# Patto test strategy

## Test layers

- Model/constraint tests for database integrity.
- Serializer and API tests for validation and response shape.
- Permission tests for cross-couple and partner-role boundaries.
- Mocked OpenAI tests for AI analysis, Coach, conflict support, and monthly insight workflows.
- In-App Purchase development verifier tests for entitlement state transitions.
- Admin privacy tests for redaction and sensitive-access audit events.
- Deployment hardening tests for production readiness settings.

## Highest-priority security regressions

Keep these covered before release:

- Cross-couple object access.
- Early partner-answer disclosure.
- Individual Coach privacy disclosure.
- Couple chat accidentally invoking AI.
- Conflict-perspective disclosure before lock/reveal rules.
- Pact approval races.
- Invitation reuse.
- Webhook replay/idempotency.
- Prompt injection routing.
- XSS-sensitive text fields.
- Account deletion boundaries.
- Admin sensitive-content exposure.

## Required verification commands

Local syntax/settings checks:

```bash
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
python manage.py makemigrations --check --dry-run --settings=config.settings.test
```

Docker regression:

```bash
docker compose build api
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

Production readiness:

```bash
python manage.py check --deploy --settings=config.settings.production
python manage.py productioncheck --strict-providers --settings=config.settings.production
```
