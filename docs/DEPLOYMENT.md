# Patto deployment runbook

## Runtime shape

Build one immutable Docker image and run these process types from it:

- API: `/app/docker/start-api.sh`
- Worker: `/app/docker/start-worker.sh`
- Scheduler: `/app/docker/start-beat.sh`
- Migration/check job: `/app/docker/start-migrate.sh`

Do not run migrations from API startup. Run the migration/check job once per release before shifting traffic.

## Required production environment

Use `DJANGO_SETTINGS_MODULE=config.settings.production`.

Required secrets/config:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- PostgreSQL credentials
- Redis/Celery URLs
- SMTP credentials
- `OPENAI_API_KEY`
- Apple and/or Google IAP provider credentials

Run:

```bash
python manage.py check --deploy
python manage.py productioncheck --strict-providers
```

## Release sequence

1. Build and tag the image with the commit SHA.
2. Push the image to the registry.
3. Run database backup.
4. Run the migration/check job from the new image.
5. Start/update workers and scheduler.
6. Deploy API.
7. Run smoke checks:
   - `GET /api/v1/health/`
   - OTP request using SMTP sandbox/approved test address
   - authenticated profile request
   - admin login
8. Monitor logs, errors, OpenAI usage, queue depth, and billing-event failures.

## Rollback

1. Stop traffic to the new API image.
2. Redeploy the previous known-good image.
3. Keep workers on the same image as the API.
4. If migrations are not backward-compatible, restore the pre-release database backup.
5. Document the incident and add a regression test before retrying.

## Backups and retention

- Run automated PostgreSQL backups at least daily.
- Test restore into a non-production environment before launch and after major schema changes.
- Treat media/private export storage as sensitive data.
- Never use real relationship data in automated tests or local demos.

## Monitoring checklist

- API 5xx rate
- API latency
- Celery queue depth
- Worker failures
- Failed notification deliveries
- Failed billing events
- OpenAI request failures and spend
- Account deletion failures
- Admin sensitive-content audit events
