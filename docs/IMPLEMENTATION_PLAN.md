# Patto Backend Implementation Plan

## Document status

- Backend framework: Python and Django
- API framework: Django REST Framework
- Runtime: Docker
- Primary database: PostgreSQL
- Cache and task broker: Redis
- Background processing: Celery
- AI provider: OpenAI API
- Status: Implementation started with conservative MVP assumptions

## Implementation progress

### Completed on 2026-08-07

1. Bootstrapped the Django project under `config/`.
2. Split settings into `config.settings.base`, `local`, `test`, and `production`.
3. Added Docker runtime files: `Dockerfile`, `compose.yaml`, `.dockerignore`, and container start scripts.
4. Added PostgreSQL, Redis, API, Celery worker, and Celery Beat service definitions.
5. Added Django REST Framework, CORS, drf-spectacular, Celery, Redis, Psycopg, OpenAI, and testing dependencies.
6. Added a custom UUID-based `User` model before any production migrations.
7. Added `/api/v1/health/` and a `healthcheck` management command.
8. Added a Celery smoke task named `common.ping`.
9. Added `.env.example` and `.gitignore` so secrets are documented but not committed.
10. Added `docs/PRODUCT_RULES.md` with MVP assumptions and privacy rules.
11. Added shared request ID middleware.
12. Added a standard DRF API error envelope.
13. Added standard DRF pagination.
14. Added reusable audit event storage and service helper.
15. Added database-backed idempotency-key storage for sensitive future writes.
16. Added foundation tests for UUID users, request IDs, and audit event creation.

### Completed on 2026-08-08

1. Confirmed Step 4 as the next implementation step.
2. Switched OTP delivery to SMTP email.
3. Switched billing from Stripe to mobile In-App Purchase.
4. Removed the Stripe Python dependency and Stripe environment variables.
5. Added SMTP and IAP environment variables.
6. Added passwordless email OTP registration/login endpoints.
7. Added hashed OTP storage with expiry, attempt limits, and request throttling.
8. Added opaque hashed access and refresh token sessions.
9. Added refresh-token rotation and logout/session revocation.
10. Added bearer-token authentication for DRF.
11. Added authentication tests covering SMTP outbox, OTP hashing, OTP consumption, token refresh, and logout.

### Completed Step 5 on 2026-08-08

1. Added `UserProfile` with display name, pronouns, avatar, language, timezone, and onboarding completion timestamp.
2. Added automatic profile creation for every new user.
3. Added restricted profile admin tooling.
4. Added `GET /api/v1/me/` for authenticated profile retrieval.
5. Added `PATCH /api/v1/me/` for authenticated profile updates.
6. Added `POST /api/v1/me/avatar/` for validated avatar upload.
7. Added `DELETE /api/v1/me/avatar/` for avatar removal.
8. Added Pillow for image validation.
9. Updated the Docker image so media and static directories are writable by the non-root app user.
10. Added profile tests for auto-creation, private profile retrieval, profile updates, user language/timezone sync, and avatar validation.

### Completed Step 6 on 2026-08-08

1. Added the `apps.couples` Django app.
2. Added `Couple`, `CoupleMember`, and `PartnerInvitation` models.
3. Added couple statuses: `pending`, `active`, `archived`, and `dissolved`.
4. Added member statuses: `invited`, `active`, `left`, and `removed`.
5. Added partner roles: `partner_1` and `partner_2`.
6. Added database constraints for one active couple per user, one active role per couple, and one membership per user/couple pair.
7. Added hashed, expiring, single-use invitation tokens.
8. Added SMTP invitation email sending with configurable invitation URL template.
9. Added `POST /api/v1/couples/`.
10. Added `GET /api/v1/couples/current/`.
11. Added `POST /api/v1/couples/{couple_id}/invitations/`.
12. Added `POST /api/v1/couples/invitations/accept/`.
13. Added `POST /api/v1/couples/invitations/{invitation_id}/revoke/`.
14. Added admin tooling for couples, members, and invitations.
15. Added tests for couple creation, duplicate couple prevention, invitation hashing/email, accept-once behavior, third-user rejection, revoke/expiry handling, and cross-couple invite denial.

### Completed Step 7 on 2026-08-08

1. Added centralized couple authorization helpers in `apps.couples.permissions`.
2. Added `IsCoupleMember`.
3. Added `IsActiveCoupleMember`.
4. Added `IsPartnerOne`.
5. Added `HasActiveEntitlement`.
6. Added `CanCreatePartnerInvitation`.
7. Added `CanRevokePartnerInvitation`.
8. Added future-facing permission classes for shared content, private responses, pact approval, and Coach conversations.
9. Added a small `Entitlement` model that Step 8 can populate from In-App Purchase validation.
10. Refactored partner invitation endpoints to use object-level permission checks.
11. Added permission tests for outsiders, archived couples, partner roles, pending-couple invitation permissions, and entitlement windows.

### Completed Step 8 on 2026-08-08

1. Added the `apps.billing` Django app.
2. Added `IAPPurchaseAccount`, `Subscription`, and `SubscriptionEvent` models.
3. Added a development-mode IAP verifier that validates structured local JSON payloads without connecting to Apple or Google.
4. Added idempotent platform-event processing using unique `(platform, event_id)` storage.
5. Added normalized subscription state for active, expired, canceled, and revoked subscriptions.
6. Connected subscription state to couple entitlements for access control.
7. Added `POST /api/v1/billing/iap/development/verify/`.
8. Added `GET /api/v1/billing/entitlement/current/`.
9. Added admin tooling for IAP accounts, subscriptions, and subscription events.
10. Added tests for Partner 1 billing attachment, Partner 2 denial, duplicate-event idempotency, expiration handling, and current entitlement retrieval.

Production note: live Apple and Google verification is intentionally not connected yet. The service boundary is ready for production verifiers later.

### Completed Step 9 on 2026-08-08

1. Added the `apps.topics` Django app.
2. Added `Topic`, `TopicTranslation`, `Question`, `QuestionTranslation`, `QuestionOption`, and `QuestionOptionTranslation`.
3. Added stable keys and version fields so future answer records can remain linked to the exact historical question version.
4. Added admin tooling for topics, questions, translations, and options.
5. Added a data migration that seeds the 12 built-in prototype topics.
6. Added 12 versioned MVP questions per built-in topic.
7. Included the prototype's Children & Family Planning example question and options.
8. Added `GET /api/v1/topics/`.
9. Added `GET /api/v1/topics/{slug}/`.
10. Added language-aware catalog serialization with English fallback.
11. Ensured inactive questions remain in the database but are excluded from active catalog counts/details.
12. Added catalog tests for seed count, detail structure, language fallback, and inactive historical rows.

Product note: most seeded question copy is placeholder MVP copy because the prototype does not contain full final copy for all 144 built-in questions. Replace through versioned migrations/admin before launch.

### Completed Step 10 on 2026-08-08

1. Added `CoupleTopic`, `CustomQuestion`, and `CustomQuestionOption`.
2. Scoped custom topics to exactly one couple.
3. Allowed either active partner to create and manage custom topics.
4. Enforced a minimum of 3 custom questions.
5. Added custom question options and open-text prompts.
6. Added stable keys and version fields for custom topics and questions.
7. Added unlocked in-place edits for custom topics that have not started.
8. Added locked-topic edit behavior that creates a new version and deactivates the previous version.
9. Added soft delete/deactivation so custom topic rows and questions remain available for future answer history.
10. Added admin tooling for custom topics, questions, and options.
11. Added `GET /api/v1/custom-topics/`.
12. Added `POST /api/v1/custom-topics/`.
13. Added `GET /api/v1/custom-topics/{topic_id}/`.
14. Added `PUT /api/v1/custom-topics/{topic_id}/`.
15. Added `DELETE /api/v1/custom-topics/{topic_id}/`.
16. Added tests for creation, minimum question validation, partner visibility, cross-couple isolation, unlocked updates, locked versioning, and deactivation.

### Completed Step 11 on 2026-08-08

1. Added the `apps.responses` Django app.
2. Added `TopicSession`, `TopicResponse`, and `TopicMemberCompletion`.
3. Added built-in and custom topic session support.
4. Frozen topic stable key, topic version, and expected question count at session creation.
5. Stored question stable key and question version with every answer.
6. Added one-response-per-user-per-question-version database constraint.
7. Added one-completion-per-user-per-session database constraint.
8. Added transactional partial answer save.
9. Added transactional topic completion with all-answer validation.
10. Locked completed user answers against later edits.
11. Locked custom topics once a response session starts.
12. Released partner answers only after both active partners complete the same topic session.
13. Added `POST /api/v1/topic-sessions/`.
14. Added `GET /api/v1/topic-sessions/{session_id}/`.
15. Added `POST /api/v1/topic-sessions/{session_id}/answers/`.
16. Added `POST /api/v1/topic-sessions/{session_id}/complete/`.
17. Added admin tooling for sessions, responses, and completions.
18. Added tests for session creation, partial save, all-answer completion, locked edits, early privacy, post-completion release, retry-safe answer upserts, custom topic locking, and cross-couple denial.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python manage.py migrate --settings=config.settings.test --noinput
python -m compileall apps config
docker compose config
docker compose build api
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

### Completed Step 12 on 2026-08-08

1. Added `TopicAnalysisJob` as a development-safe placeholder queue record for future AI analysis.
2. Added `TopicSyncEvent` for durable in-app synchronization events.
3. Made partner-completion synchronization idempotent using database uniqueness.
4. Created `partner_completed_waiting` events for the partner who has not completed yet.
5. Created exactly one queued analysis job when both active partners complete the same topic session.
6. Created `analysis_queued` events for both active partners when analysis is queued.
7. Added `mark_analysis_job_succeeded` to record future `analysis_ready` events for both partners.
8. Added a `sync` payload to topic session detail and completion responses.
9. Added admin tooling for analysis jobs and sync events.
10. Added tests for waiting sync, one-analysis-job creation, retry/idempotency behavior, and analysis-ready events.

Product note: real push notifications and real OpenAI analysis are intentionally deferred to their later implementation steps. Step 12 records durable in-app sync events and queues a placeholder job so the workflow is testable now.

### Completed Step 13 on 2026-08-08

1. Added the `apps.ai` Django app.
2. Added `AIPromptVersion` for versioned prompt storage.
3. Added `AIAnalysisResult` for model, prompt version, provider response id, status, usage, output, refusal, and error storage.
4. Seeded `topic_analysis:v1` with a structured-output JSON schema.
5. Added Pydantic `TopicAnalysisSchema` validation.
6. Added an OpenAI Responses API client boundary using configurable model, timeout, retries, and `store` behavior.
7. Added `run_topic_analysis` service for topic analysis job processing.
8. Kept provider calls out of Django views and outside database row locks.
9. Added a Celery task named `ai.run_topic_analysis`.
10. Added optional `AI_AUTO_DISPATCH_ANALYSIS` for worker dispatch when an analysis job is queued.
11. Kept development mode safe by default: analysis jobs queue without live OpenAI calls unless dispatch is enabled or the service/task is invoked.
12. Distinguished successful output, provider/configuration failure, refusal, and invalid schema output.
13. Ensured invalid AI output is not stored as successful analysis output.
14. Added tests with a fake AI client so no OpenAI API key or network call is needed in automated tests.
15. Added AI environment variables to `.env.example` and Docker Compose.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_ai_analysis.py -p no:cacheprovider
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

### Completed Step 14 on 2026-08-08

1. Added `AISafetyEvent` for auditable AI safety decisions.
2. Added `apps.ai.policies` with deterministic local policy checks for:
   - abuse and coercion
   - self-harm
   - threats
   - sexual content
   - content involving minors
   - medical or legal advice
   - prompt injection attempts
3. Added safety event storage that records category, severity, route, detector, metadata, and content fingerprint without retaining raw private text.
4. Added input screening before the OpenAI/provider call.
5. Added output screening after Pydantic validation and before successful AI result storage.
6. Routed high-risk input to a restricted safety response without calling the provider.
7. Blocked unsafe AI-generated suggestions before they can become successful analysis output or future pact/challenge source data.
8. Allowed caution-level content, such as medical/legal topics, to continue while still recording auditable safety context.
9. Added `safety_blocked` AI result status.
10. Added admin tooling for safety events.
11. Added safety tests covering self-harm, abuse/coercion, threats, minors, caution-level legal content, and unsafe generated suggestions.

Product note: region-specific hotline/resource content is intentionally not generated by the model. Step 14 records the safety route and returns a restricted safety response that tells the app to use vetted external resource tables maintained outside prompts.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_ai_analysis.py -p no:cacheprovider
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

### Completed Step 15 on 2026-08-08

1. Added `AIFollowUpQuestion` for persisted per-user, per-topic-session follow-up questions.
2. Added a database constraint so each user gets at most one follow-up per topic session.
3. Added Pydantic `FollowUpQuestionSchema` with support for either a generated question or an intentional skip.
4. Seeded `follow_up_question:v1` with a privacy-scoped prompt.
5. Added OpenAI Responses API client support for follow-up structured output.
6. Added `generate_follow_up_question` service.
7. Ensured follow-up prompt input includes only:
   - current user's answers
   - current frozen topic key/version
   - current user's language
   - approved privacy/safety context
8. Ensured partner-private content is not included in follow-up prompt input.
9. Persisted generated follow-ups so refresh/retry does not regenerate a different question.
10. Added safety blocking for high-risk follow-up input and unsafe follow-up output.
11. Added invalid-output, refusal, provider-failure, and configuration-failure statuses for follow-ups.
12. Added `POST /api/v1/topic-sessions/{session_id}/follow-up/`.
13. Added admin tooling for follow-up records.
14. Added tests for privacy scoping, persistence/idempotency, invalid output, and safety-blocked input.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_ai_analysis.py -p no:cacheprovider
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

### Completed Step 16 on 2026-08-08

1. Added the `apps.analysis` Django app for product-facing analysis domain tables.
2. Added `AnalysisRun` with per-session versioning, status, topic snapshot, active-member snapshot, deterministic similarity score, and recoverable failure fields.
3. Added `TopicAnalysis` for summary, alignment score, confidence, common ground, differences, sensitive areas, and safety flags.
4. Added `AlignmentDimension` for deterministic and AI-interpreted alignment dimensions.
5. Added `ConversationStarter`.
6. Added `ProposedClause` as the bridge toward future pact proposal flows.
7. Added `materialize_topic_analysis` to convert only successful, safe AI output into domain tables.
8. Added deterministic selected-option similarity scoring.
9. Enforced that domain analysis can materialize only after both active partners complete and lock the topic session.
10. Added recoverable failed/safety-blocked analysis run creation.
11. Connected successful `run_topic_analysis` execution to automatic domain materialization.
12. Added rerun behavior where explicit reruns create new analysis versions.
13. Added `GET /api/v1/topic-sessions/{session_id}/analysis/` for latest materialized analysis retrieval.
14. Added admin tooling for analysis runs, topic analyses, dimensions, starters, and proposed clauses.
15. Added tests for successful materialization, versioned reruns, recoverable failed runs, locked-answer requirement, and cross-couple read isolation.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_topic_analysis_domain.py -p no:cacheprovider
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

### Completed Step 17 on 2026-08-08

1. Added the `apps.discussions` Django app.
2. Added `DiscussionThread`.
3. Added `DiscussionMessage`.
4. Added `MediationRequest`.
5. Added `MediationResponse`.
6. Scoped every thread, message, mediation request, and mediation response to a couple.
7. Allowed both active partners to create threads and post messages.
8. Added thread creation for topic sessions and analysis runs.
9. Added message storage with `sender_type` so user, AI, and system messages are clearly identified.
10. Escaped user message content and marked messages as `render_as=text`.
11. Added mediation request records with context message counts.
12. Added service helpers for mediation success and recoverable mediation failure.
13. Ensured mediation failures do not delete or alter user messages.
14. Added discussion APIs:
    - `GET /api/v1/discussion-threads/`
    - `POST /api/v1/discussion-threads/`
    - `GET /api/v1/discussion-threads/{thread_id}/`
    - `POST /api/v1/discussion-threads/{thread_id}/messages/`
    - `POST /api/v1/discussion-threads/{thread_id}/mediation-requests/`
15. Added admin tooling for discussions and mediation records.
16. Added tests for active partner participation, cross-couple denial, HTML-as-text rendering, mediation failure safety, and AI message labeling.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_discussions.py -p no:cacheprovider
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

### Completed Step 18 on 2026-08-08

1. Added the `apps.pacts` Django app.
2. Added `Pact`.
3. Added `PactVersion` with draft, proposed, live, and superseded states.
4. Added `PactSection`.
5. Added immutable `PactClause` snapshots for live versions.
6. Added editable `ClauseProposal`.
7. Added `ClauseApproval` with proposal revision tracking.
8. Added pact creation from manual clauses and future-compatible analysis proposed clauses.
9. Added proposal editing that increments revision and invalidates previous approvals.
10. Added per-partner proposal approval.
11. Added transaction-safe activation only after both active partners approve every current proposal revision.
12. Added live-version immutability; editing live pact content requires creating a new proposed version.
13. Added automatic superseding of older live versions.
14. Added conversion of analysis `ProposedClause` rows when they become live pact clauses.
15. Added pact APIs:
    - `GET /api/v1/pacts/`
    - `POST /api/v1/pacts/`
    - `GET /api/v1/pacts/{pact_id}/`
    - `POST /api/v1/pacts/{pact_id}/propose/`
    - `PATCH /api/v1/clause-proposals/{proposal_id}/`
    - `POST /api/v1/clause-proposals/{proposal_id}/approve/`
16. Added admin tooling for pacts, versions, sections, proposals, clauses, and approvals.
17. Added tests for one-partner activation denial, two-partner activation, edit approval invalidation, live immutability, idempotent approval, and cross-couple isolation.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_pacts.py -p no:cacheprovider
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

### Completed Step 19 on 2026-08-08

1. Added `PactDocument` for private immutable pact PDF snapshots.
2. Added `PactDocumentDownloadToken` for authenticated expiring download links.
3. Added a dependency-free MVP PDF renderer for live pact versions.
4. Generated a PDF automatically when a pact version becomes live.
5. Stored generated PDF files under private media storage paths.
6. Recorded PDF filename, byte size, generated timestamp, email timestamp, email attempts, and SHA-256 checksum.
7. Emailed both active partners when a pact becomes live using the configured SMTP backend.
8. Attached the generated PDF to pact activation emails.
9. Created per-user expiring download tokens for email links and API-generated links.
10. Added authenticated PDF download handling.
11. Denied expired token downloads.
12. Denied cross-couple or wrong-user downloads.
13. Made PDF generation idempotent per pact version.
14. Made email retries reuse the existing PDF and live pact version.
15. Added PDF environment settings:
    - `PACT_PDF_TOKEN_TTL_MINUTES`
    - `PACT_PDF_DOWNLOAD_URL_TEMPLATE`
16. Added PDF APIs:
    - `POST /api/v1/pacts/{pact_id}/versions/{version_id}/pdf-link/`
    - `GET /api/v1/pact-pdfs/{token}/download/`
17. Added admin tooling for pact documents and download tokens.
18. Added tests for PDF content, checksum, activation email, authenticated download, expiry, cross-couple denial, and email retry idempotency.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_pacts.py -p no:cacheprovider
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

### Completed Step 20 on 2026-08-08

1. Added the `apps.notifications` Django app.
2. Added `Device` for iOS, Android, and web device token registration.
3. Added device revocation.
4. Added `NotificationPreference` with category-level enable/disable support.
5. Added `Notification` as a durable in-app notification ledger.
6. Added `NotificationDelivery` as the provider-agnostic delivery-attempt ledger.
7. Added idempotent notification emission using unique per-user `event_key` values.
8. Created pending delivery rows for active devices.
9. Suppressed disabled categories without creating push delivery attempts.
10. Added notification APIs:
    - `GET /api/v1/devices/`
    - `POST /api/v1/devices/`
    - `POST /api/v1/devices/{device_id}/revoke/`
    - `GET /api/v1/notification-preferences/`
    - `PATCH /api/v1/notification-preferences/`
    - `GET /api/v1/notifications/`
    - `POST /api/v1/notifications/{notification_id}/read/`
11. Wired initial notification events:
    - partner invitation for existing invited users
    - partner joined
    - topic completed
    - analysis ready
    - pact approval required
    - pact activated
12. Added admin tooling for devices, preferences, notifications, and deliveries.
13. Added tests for disabled preferences, device revocation, retry idempotency, workflow event creation, and delivery rows.

Product note: APNs/FCM provider calls are intentionally not connected yet. Step 20 creates a reliable notification ledger and delivery queue that future provider workers can consume.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_notifications.py -p no:cacheprovider
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

### Completed Step 21 on 2026-08-08

1. Added the `apps.daily` Django app.
2. Added `DailyQuestion` for curated deterministic daily prompts.
3. Added `DailyAssignment` with one assignment per couple per local date.
4. Added `DailyAnswer` with one answer per user per assignment.
5. Added `DailyReveal` so partner answers reveal only after both active partners answer.
6. Added `CoupleStreak` with deterministic current/longest streak tracking.
7. Seeded seven MVP daily questions through a data migration.
8. Implemented timezone-aware local-date assignment using each user's configured timezone.
9. Implemented deterministic question rotation from the assignment local date and active catalog ordering.
10. Kept daily logic non-AI-generated by design.
11. Added daily APIs:
    - `GET /api/v1/daily/current/`
    - `GET /api/v1/daily/{assignment_id}/`
    - `POST /api/v1/daily/{assignment_id}/answers/`
12. Added admin tooling for daily questions, assignments, answers, reveals, and streaks.
13. Added tests for unique daily assignment creation, one answer per user, pre-reveal privacy, reveal after both answers, timezone boundaries, missed-day streak resets, consecutive streak increments, and cross-couple isolation.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_daily.py -p no:cacheprovider
```

### Completed Step 22 on 2026-08-08

1. Added the `apps.insights` Django app.
2. Added `MonthlyInsight` for one AI insight job/result per couple per month.
3. Added `MonthlyInsightInput` to snapshot exactly which revealed daily answers were used.
4. Stored input date range, prompt version, model, structured sections, safety flags, usage, token counts, status, and failure/refusal metadata.
5. Added `monthly_insight:v1` as a seeded prompt version with strict structured output.
6. Added deterministic month-window handling for first/last day of the target month.
7. Enforced that monthly insight jobs can run only after the target month closes.
8. Enforced a configurable minimum revealed-day threshold with `MONTHLY_INSIGHT_MIN_REVEALED_DAYS`.
9. Built prompt inputs only from revealed daily assignments whose `local_date` is inside the target month.
10. Added a Celery task named `insights.run_monthly_insight`.
11. Kept development mode safe by default with `AI_AUTO_DISPATCH_MONTHLY_INSIGHTS=false`.
12. Added monthly insight APIs:
    - `GET /api/v1/monthly-insights/`
    - `POST /api/v1/monthly-insights/`
13. Added admin tooling for monthly insights and input snapshots.
14. Added tests for successful AI metadata persistence, minimum-participation ineligibility, closed-month enforcement, API queueing, and the critical rule that a job cannot include answers outside its assigned month.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
python manage.py makemigrations --check --dry-run --settings=config.settings.test
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_monthly_insights.py -p no:cacheprovider
```

### Completed Step 23 on 2026-08-08

1. Added the `apps.challenges` Django app.
2. Added `Challenge` for curated, fallback, and AI-suggested challenge records.
3. Added `ChallengeAssignment` for assigning one challenge to a couple.
4. Added `ChallengeMemberCompletion` so each partner completes independently.
5. Added deterministic assignment completion behavior: the assignment becomes completed only after all active partners complete it.
6. Added `challenge_policy_v1` validation for AI-suggested challenges.
7. Rejected unsafe, coercive, controlling, or non-constructive challenge suggestions before assignment.
8. Added safe fallback challenge selection for AI generation failure or missing suggestions.
9. Seeded fallback and curated MVP challenges.
10. Added challenge APIs:
    - `GET /api/v1/challenges/`
    - `GET /api/v1/challenge-assignments/`
    - `POST /api/v1/challenge-assignments/`
    - `GET /api/v1/challenge-assignments/{assignment_id}/`
    - `POST /api/v1/challenge-assignments/{assignment_id}/complete/`
11. Added admin tooling for challenges, assignments, and member completions.
12. Added tests for independent partner completion, unsafe/coercive suggestion rejection, generation-failure fallback, safe AI suggestion assignment after policy validation, API assignment/completion, and cross-couple isolation.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
python manage.py makemigrations --check --dry-run --settings=config.settings.test
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_challenges.py -p no:cacheprovider
```

### Completed Step 24 on 2026-08-08

1. Added the `apps.coach` Django app.
2. Added `CoachConversation` with `individual`, `couple`, and legacy `conflict` scope support.
3. Added `CoachParticipant` so shared Coach conversations are explicitly participant-scoped.
4. Added `CoachMessage` with text rendering and explicit individual-message sharing flags.
5. Added `CoachRun` for provider response id, prompt version, model, authorized context ids, structured output, safety flags, usage, token counts, and failure/refusal metadata.
6. Seeded `coach:v1` as a strict structured-output prompt for individual user-to-AI Coach conversations.
7. Implemented individual conversation privacy: only the owner can read or run an individual Coach conversation.
8. Implemented shared conversation authorization: couple conversations require active couple membership.
9. Implemented authorized context building:
   - individual Coach uses only that owner's individual conversation messages
   - couple chat is partner-to-partner only and does not generate AI runs
   - individual Coach messages are excluded from shared contexts unless explicitly shared by the owner
10. Added explicit individual-message sharing through `share_individual_coach_message`.
11. Added OpenAI Responses API integration through the existing structured-response client boundary for individual Coach only.
12. Added safety screening for Coach inputs and outputs.
13. Added Coach APIs:
    - `GET /api/v1/coach/conversations/`
    - `POST /api/v1/coach/conversations/`
    - `GET /api/v1/coach/conversations/{conversation_id}/`
    - `POST /api/v1/coach/conversations/{conversation_id}/messages/`
    - `POST /api/v1/coach/conversations/{conversation_id}/run/`
    - `POST /api/v1/coach/messages/{message_id}/share/`
14. Added admin tooling for Coach conversations, participants, messages, and runs.
15. Added tests covering individual privacy, cross-partner denial, couple chat without AI, explicit sharing, fake-client individual Coach runs, persisted AI messages, API flow, and dev-safe missing-key failure.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
python manage.py makemigrations --check --dry-run --settings=config.settings.test
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_coach.py -p no:cacheprovider
```

### Completed Step 25 on 2026-08-08

1. Added the `apps.conflicts` Django app.
2. Added `ConflictThread` with collecting, locked, bridge-ready/discussion-open, and resolved workflow states.
3. Added `ConflictPerspective` with one private perspective per active partner per conflict.
4. Added `ConflictBridge` for neutral AI bridge output, prompt version, model, provider id, usage, safety flags, and failure metadata.
5. Added `ConflictMessage` for the shared discussion layer that opens only after a bridge is ready.
6. Added `ConflictMediation` for optional mediation requests.
7. Added `ConflictResolution` for explicit user-driven resolution with proposed pact changes stored as suggestions only.
8. Seeded `conflict_bridge:v1` as a strict structured-output prompt.
9. Implemented private perspective submission and locking.
10. Implemented automatic transition to `perspectives_locked` after both active partners lock their perspectives.
11. Implemented therapist-like conflict support through the existing OpenAI structured-response client boundary, while preserving the rule that Patto is not licensed therapy.
12. Added deterministic bridge policy validation that blocks blame/fault-assigning output.
13. Opened shared discussion by creating an AI `ConflictMessage` only after a successful neutral bridge.
14. Ensured conflict resolution never creates, edits, approves, or activates pact records automatically.
15. Added conflict APIs:
    - `GET /api/v1/conflicts/`
    - `POST /api/v1/conflicts/`
    - `GET /api/v1/conflicts/{thread_id}/`
    - `POST /api/v1/conflicts/{thread_id}/perspective/`
    - `POST /api/v1/conflicts/{thread_id}/bridge/`
    - `POST /api/v1/conflicts/{thread_id}/messages/`
    - `POST /api/v1/conflicts/{thread_id}/mediations/`
    - `POST /api/v1/conflicts/{thread_id}/resolve/`
16. Added admin tooling for conflict threads, perspectives, bridges, messages, mediations, and resolutions.
17. Added tests covering early private perspective visibility, locked-pair bridge generation, blame-policy blocking, discussion opening, mediation request, resolution, and the pact non-mutation rule.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
python manage.py makemigrations --check --dry-run --settings=config.settings.test
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_conflicts.py -p no:cacheprovider
```

### Completed Step 26 on 2026-08-08

1. Added the `apps.moments` Django app.
2. Added `Moment` for couple-scoped memories.
3. Added `MomentMedia` for private image files and thumbnails.
4. Added `MomentTopicLink` for linking moments to built-in or custom topics.
5. Added `MomentMediaDownloadToken` for authenticated expiring signed app download URLs.
6. Implemented image validation for PNG, JPEG, and WebP uploads.
7. Implemented metadata stripping by re-encoding uploaded images before storage.
8. Implemented thumbnail generation capped at 512x512.
9. Stored private media under couple/moment-scoped media paths.
10. Added checksum, size, dimensions, thumbnail dimensions, content type, and metadata-removal audit fields.
11. Added archive behavior via `archive_moments_for_couple`, matching the MVP rule that shared work is archived until final retention policy is approved.
12. Blocked new media uploads to archived moments or archived couples while still allowing historical moment detail retrieval for existing members.
13. Added moment APIs:
    - `GET /api/v1/moments/`
    - `POST /api/v1/moments/`
    - `GET /api/v1/moments/{moment_id}/`
    - `POST /api/v1/moments/{moment_id}/media/`
    - `POST /api/v1/moment-media/{media_id}/download-link/`
    - `GET /api/v1/moment-media/{token}/download/`
14. Added admin tooling for moments, media, topic links, and media download tokens.
15. Added tests for topic links, partner visibility, image metadata stripping, thumbnail generation, signed media download, token expiry, cross-couple denial, and archival behavior.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
python manage.py makemigrations --check --dry-run --settings=config.settings.test
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_moments.py -p no:cacheprovider
```

### Completed Step 27 on 2026-08-08

1. Added the `apps.profile_features` Django app.
2. Added referral tracking with `ReferralCode`, `Referral`, and `ReferralReward`.
3. Ensured referral rewards originate only from processed verified IAP subscription events.
4. Wired referral reward creation into development IAP processing after the `SubscriptionEvent` is marked processed.
5. Added support ticket intake with `SupportTicket` and `SupportTicketMessage`.
6. Added subscription management status/help surface without connecting to external app-store portals.
7. Added `SubscriptionManagementRequest` for restore/cancel/status help records.
8. Reused the existing notification preference API as the notification settings surface.
9. Added `DataExportRequest` intake/status records.
10. Added `AccountDeletionRequest` intake/status records with a scheduled processing timestamp.
11. Kept actual export/deletion execution deferred to Step 28.
12. Added profile-support APIs:
    - `GET /api/v1/referrals/code/`
    - `POST /api/v1/referrals/apply/`
    - `GET /api/v1/referrals/`
    - `GET /api/v1/support-tickets/`
    - `POST /api/v1/support-tickets/`
    - `POST /api/v1/support-tickets/{ticket_id}/messages/`
    - `GET /api/v1/subscription-management/`
    - `POST /api/v1/subscription-management/`
    - `GET /api/v1/data-export-requests/`
    - `POST /api/v1/data-export-requests/`
    - `GET /api/v1/account-deletion-requests/`
    - `POST /api/v1/account-deletion-requests/`
13. Added admin tooling for referrals, support tickets, subscription management requests, export requests, and deletion requests.
14. Added tests for referral reward provenance, user-scoped support tickets, subscription management surface, notification settings availability, and idempotent export/deletion request intake.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
python manage.py makemigrations --check --dry-run --settings=config.settings.test
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_profile_features.py -p no:cacheprovider
```

### Completed Step 28 on 2026-08-08

1. Expanded `DataExportRequest` from intake-only into a processed export record with JSON payload storage, byte size, SHA-256 checksum, completion timestamp, and failure reason.
2. Added `build_user_export_payload()` to include user-owned data and permitted shared couple data while excluding partner-private fields.
3. Added retry-safe export processing via `process_data_export_request()` and `process_data_export_request_task()`.
4. Expanded `AccountDeletionRequest` with execution timestamps for session revocation, billing updates, partner notification, processing, completion, failure reason, and couple action.
5. Added confirmation-email validation for account deletion requests as the current OTP-session equivalent of reauthentication.
6. Added session revocation for all active `AuthSession` records owned by the deleting user.
7. Added billing cleanup that marks active IAP subscriptions as canceled and syncs related entitlements.
8. Added partner notification category `account_deletion_requested`.
9. Added partner notification emission before the requesting member leaves the couple.
10. Added relationship disconnection behavior for account deletion.
11. Previous couple-scoped shared data is deleted during account deletion/disconnection instead of archived.
12. Added private-content anonymization for the deleting user’s topic answers, Daily answers, Coach messages, conflict messages, conflict perspectives, and support-ticket content.
13. Added user/profile anonymization without deleting the partner’s owned account data.
14. Added background-job-ready task entry points in `apps.profile_features.tasks`.
15. Added tests for confirmation-email validation, export processing, export idempotency, session revocation, billing cleanup, partner notification, shared-couple deletion, remaining-partner reconnection, and user anonymization.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
python manage.py makemigrations --check --dry-run --settings=config.settings.test
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_profile_features.py -p no:cacheprovider
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

Step 28 rule update on 2026-08-08:

1. Account deletion/disconnection now fully severs the previous couple connection.
2. The previous couple record is deleted so all couple-scoped shared history is removed instead of archived.
3. Partner notification is retained without a `couple` foreign key because the couple row is deleted.
4. The remaining partner is no longer blocked by the previous active membership and can create a new couple/invite a new partner using the same invitation URL flow.
5. Existing generated export payloads are cleared during deletion; users must export/download data before deletion is processed.
6. Added `AccountDeletionRequest.CoupleAction.DELETED`.
7. Updated tests to assert old couple data is gone and the remaining partner can reconnect.

### Completed Step 29 on 2026-08-08

1. Added common admin privacy helpers in `apps.common.admin`:
    - `SensitiveContentAdminMixin`
    - `ReadOnlyAdminMixin`
    - `has_sensitive_admin_access()`
    - `Sensitive Content Access` group gate
2. Registered audit/idempotency operational models in Django Admin.
3. Added audit logging for sensitive object detail views by privileged admin users.
4. Restricted private topic answers in `TopicResponseAdmin`.
5. Restricted Daily answer text in `DailyAnswerAdmin` and removed answer text from assignment inlines.
6. Restricted individual/couple Coach message bodies and metadata in `CoachMessageAdmin`.
7. Removed Coach message bodies from Coach conversation inlines.
8. Restricted conflict private perspectives, conflict messages, mediation prompts, and mediation responses.
9. Removed conflict private perspectives/messages from thread inlines.
10. Restricted discussion message bodies and mediation response content.
11. Restricted Moment body text and removed it from admin search.
12. Restricted AI analysis output, AI usage payloads, follow-up questions, and internal AI reasoning text.
13. Restricted data export payload visibility while keeping status/checksum/size operationally visible.
14. Added explicit admin tooling for deletion job status and execution timestamps.
15. Removed sensitive content from admin search fields where it could leak through query results.
16. Added admin privacy tests for:
    - default staff redaction
    - privileged sensitive access
    - sensitive admin view audit events
    - Coach body search exclusion
    - redacted Coach message detail fields

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
python manage.py makemigrations --check --dry-run --settings=config.settings.test
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_admin_privacy.py -p no:cacheprovider
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

### Completed Step 30 on 2026-08-08

1. Added production security settings:
    - secure cookies
    - HTTPS redirect
    - HSTS defaults
    - content-type nosniff
    - strict referrer policy
    - CSRF trusted origins from env
2. Added IAP provider secret settings so production checks can validate Apple/Google billing readiness.
3. Added `productioncheck`, a Patto-specific deployment readiness command that validates:
    - `DEBUG=False`
    - strong non-default secret key
    - production host policy
    - HTTPS-only CORS/CSRF origins
    - secure cookies and HSTS
    - PostgreSQL database engine
    - SMTP production backend
    - optional strict provider checks for OpenAI, SMTP, and IAP secrets
4. Added `docker/start-migrate.sh` for a separate migration/check deployment job.
5. Added a compose `migrate` service under the `ops` profile.
6. Updated `.env.example` with CSRF and HSTS deployment settings.
7. Added deployment-hardening tests for secure production settings, local-development failure cases, and strict provider-secret enforcement.
8. Added `docs/DEPLOYMENT.md` with runtime process shape, release sequence, smoke checks, rollback, backup, and monitoring checklist.
9. Added `docs/TEST_STRATEGY.md` with test layers, security regression priorities, and verification commands.
10. Verified the production readiness command directly inside Docker with production-style environment variables.

Validation completed:

```text
python manage.py check --settings=config.settings.test
python -m compileall apps config tests
python manage.py makemigrations --check --dry-run --settings=config.settings.test
docker compose build api
docker run --rm patto-backend:local python -m pytest tests/test_deployment_hardening.py -p no:cacheprovider
docker run --rm -e DJANGO_SETTINGS_MODULE=config.settings.production -e DJANGO_SECRET_KEY=prod-secret-key-that-is-long-enough-for-docker-check -e DJANGO_ALLOWED_HOSTS=api.patto.app -e DJANGO_CORS_ALLOWED_ORIGINS=https://app.patto.app -e DJANGO_CSRF_TRUSTED_ORIGINS=https://app.patto.app -e EMAIL_HOST=smtp.mailprovider.test -e EMAIL_HOST_USER=smtp-user -e EMAIL_HOST_PASSWORD=smtp-password -e OPENAI_API_KEY=test-openai-key -e IAP_APPLE_SHARED_SECRET=test-apple-secret patto-backend:local python manage.py productioncheck --strict-providers
docker run --rm patto-backend:local python -m pytest -p no:cacheprovider
```

This document converts the Patto HTML prototype into an ordered backend implementation roadmap. Complete the steps in sequence. A step is complete only when its acceptance checks pass.

## 1. Proposed production architecture

```text
Mobile/Web Client
        |
        v
Django REST API (Docker)
  - Authentication and permissions
  - Couple and partner management
  - Topics and private answers
  - Pact versioning
  - Coach and conflicts
  - Subscription entitlements
        |
        +-------- PostgreSQL
        +-------- Redis
        +-------- S3-compatible object storage
        |
        v
Celery Workers (Docker)
  - OpenAI generation
  - Topic analysis
  - Notifications
  - Email
  - PDF generation
  - Data export and deletion
        |
        v
External services
  - OpenAI
  - Apple/Google In-App Purchase validation
  - Transactional email provider
  - Push notification provider
```

Recommended supporting libraries:

- `django`
- `djangorestframework`
- `psycopg`
- `celery`
- `redis`
- `django-cors-headers`
- `drf-spectacular`
- `django-storages`
- `boto3`
- `openai`
- `pydantic`
- `pytest`
- `pytest-django`
- `factory-boy`

Pin exact versions in a lock file when implementation begins.

## 2. Docker requirements

Local development should use Docker Compose with these services:

```text
api          Django ASGI/WSGI application
worker       Celery worker
beat         Celery Beat scheduler
db           PostgreSQL
redis        Redis
```

Optional local services:

```text
mailpit      Local email capture
minio        Local S3-compatible storage
```

Docker requirements:

- Use a multi-stage `Dockerfile`.
- Run the application as a non-root user.
- Keep secrets outside images and source control.
- Add health checks for the API, PostgreSQL, and Redis.
- Use named volumes for local PostgreSQL and object-storage data.
- Keep development and production settings separate.
- Run migrations as an explicit deployment step.
- Do not run `makemigrations` automatically during container startup.
- Use `gunicorn` with an ASGI worker or another production-grade ASGI server.
- Set container memory and CPU limits in production.
- Ensure API and Celery containers use the exact same application image.

Expected files:

```text
Dockerfile
compose.yaml
.dockerignore
.env.example
docker/
  entrypoint.sh
  start-api.sh
  start-worker.sh
  start-beat.sh
```

## 3. Suggested Django project structure

```text
patto_backend/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   ├── test.py
│   │   └── production.py
│   ├── urls.py
│   ├── celery.py
│   └── asgi.py
├── apps/
│   ├── common/
│   ├── accounts/
│   ├── couples/
│   ├── billing/
│   ├── topics/
│   ├── analysis/
│   ├── discussions/
│   ├── pacts/
│   ├── ai/
│   ├── notifications/
│   ├── daily/
│   ├── challenges/
│   ├── coach/
│   ├── conflicts/
│   ├── moments/
│   └── support/
├── docs/
├── tests/
├── Dockerfile
├── compose.yaml
├── manage.py
└── .env.example
```

Expose versioned endpoints under `/api/v1/`.

## 4. Sequential implementation plan

### Step 0: Finalize product and privacy rules

Create `docs/PRODUCT_RULES.md` before implementing database models.

Define:

- Only two active partners are allowed in a couple space.
- Partner 1 owns the paid subscription.
- Partner 2 inherits access from Partner 1.
- Whether an account can belong to more than one couple.
- What happens after a breakup or partner removal.
- What happens when a subscription expires.
- Minimum user age and supported launch countries.
- How long every category of data is retained.
- Which data survives couple archival.

Core privacy rules:

- Individual answers remain private until both partners reach the defined release condition.
- Individual Coach conversations are never visible to the other partner.
- Couple Coach conversations are visible to both partners.
- Conflict perspectives remain private until both submit.
- A pact clause becomes live only after both approve the exact same version.
- AI suggestions never modify a live pact automatically.
- Patto must not describe itself as therapy, medical treatment, or legal advice.

Acceptance check: every authorization decision can be derived from the written rules without guessing.

### Step 1: Freeze the MVP scope

Recommended MVP:

1. Authentication
2. User profile and language
3. Couple creation and partner invitations
4. Subscription entitlement
5. Topic and question catalog
6. Private answers
7. Partner-completion synchronization
8. AI follow-up questions
9. Topic analysis
10. Partner discussion
11. Pact clause generation
12. Two-partner pact approval
13. PDF generation
14. Basic notifications

Recommended post-MVP:

- Daily questions and streaks
- Monthly AI insights
- Challenges
- Individual and Couple Coach
- Conflict mode
- Moments
- Referrals
- Support tickets

Acceptance check: one approved document identifies the first public release.

### Step 2: Bootstrap Django and Docker

Implement:

- Django project and modular apps
- Dockerfile and Docker Compose
- PostgreSQL and Redis connections
- Celery worker and Celery Beat
- Environment-specific settings
- CORS configuration
- Structured logging
- `/api/v1/health/` endpoint
- Test configuration

Acceptance checks:

- `docker compose up` starts the complete local stack.
- The API can read and write PostgreSQL.
- Celery processes a test task.
- Redis is reachable from API and workers.
- The health endpoint reports dependency status.
- No credentials are committed.

### Step 3: Build shared backend infrastructure

Implement:

- UUID primary keys for externally referenced objects
- `TimeStampedModel`
- Soft deletion only where business rules require it
- Standard API error format
- Pagination
- Request IDs
- Audit event service
- Idempotency-key support for important writes
- Shared permission classes
- Service-layer and transaction conventions
- UTC storage for all datetimes

Acceptance checks:

- Errors have one documented structure.
- Retried sensitive requests do not create duplicate data.
- Every request can be traced through logs.

### Step 4: Implement authentication

Create a custom `User` model before the first production migration.

Suggested fields:

- `id`
- `email`
- `email_verified_at`
- `is_active`
- `preferred_language`
- `timezone`
- `last_login_at`
- `created_at`
- `updated_at`

Implement:

- Registration
- Email verification OTP
- Login
- Token refresh and rotation
- Logout and token revocation
- Password reset if password login is enabled
- Apple identity-token validation
- Google identity-token validation
- Authentication rate limits

Store OTP hashes, never plaintext OTPs.

Acceptance checks:

- Expired and consumed OTPs fail.
- OTP attempts are throttled.
- Apple and Google credentials are validated server-side.
- Logout invalidates the correct session.

### Step 5: Implement profiles

Create `UserProfile`:

- `user`
- `display_name`
- `pronouns`
- `avatar`
- `preferred_language`
- `timezone`
- `onboarding_completed_at`

Initial endpoints:

```text
GET    /api/v1/me/
PATCH  /api/v1/me/
POST   /api/v1/me/avatar/
DELETE /api/v1/me/avatar/
```

Validate uploaded images, remove metadata, and generate resized versions.

Acceptance checks:

- Onboarding data persists.
- Invalid uploads are rejected.
- Private profile fields are never exposed to other users.

### Step 6: Implement couples and invitations

Models:

- `Couple`
- `CoupleMember`
- `PartnerInvitation`

Important statuses:

- Couple: `pending`, `active`, `archived`, `dissolved`
- Member: `invited`, `active`, `left`, `removed`
- Role: `partner_1`, `partner_2`

Use random, expiring, single-use invitation tokens. Store only token hashes.

Acceptance checks:

- A third user cannot join a two-person couple.
- Expired and revoked invitations fail.
- An invitation cannot be accepted twice.
- Cross-couple access is denied.

### Step 7: Centralize authorization

Create permissions such as:

- `IsCoupleMember`
- `IsActiveCoupleMember`
- `IsPartnerOne`
- `HasActiveEntitlement`
- `CanViewSharedContent`
- `CanViewPrivateResponse`
- `CanApprovePactVersion`
- `CanViewCoachConversation`

Acceptance check: permission tests cover both partners, unrelated users, archived couples, and expired subscriptions.

### Step 8: Implement subscription entitlements

Confirmed provider: mobile In-App Purchase.

Models:

- `IAPPurchaseAccount`
- `Subscription`
- `SubscriptionEvent`
- `Entitlement`

Requirements:

- Apple and Google purchase receipts/server notifications must be verified server-side.
- Store events before processing them.
- Processing must be idempotent.
- Platform subscription state is authoritative.
- Never trust a frontend payment-success message.
- Partner 2 inherits access while the couple and subscription are eligible.

Acceptance checks:

- Duplicate platform events do not duplicate state.
- Subscription cancellation and expiry update both partners correctly.
- Failed events can be replayed safely.

### Step 9: Implement topic and question catalogs

Models:

- `Topic`
- `TopicTranslation`
- `Question`
- `QuestionTranslation`
- `QuestionOption`
- `QuestionOptionTranslation`

Load the 12 built-in topics with a versioned data migration or fixture.

Acceptance checks:

- Catalog responses use the user's language.
- Historical answers remain linked to their original question version.
- Deactivating a question does not destroy existing answers.

### Step 10: Implement custom topics

Models:

- `CoupleTopic`
- `CustomQuestion`
- Custom question versions

Rules:

- Either partner may create a custom topic.
- Custom topics belong to exactly one couple.
- Enforce a minimum question count.
- Editing after answers begin creates a new version.

Acceptance checks:

- Custom topics cannot leak across couples.
- Both partners answer the same version.
- Started content is not silently rewritten.

### Step 11: Implement private responses

Models:

- `TopicSession`
- `Response`
- `TopicMemberCompletion`

Requirements:

- A user may always retrieve their own answers.
- Partner answers remain unavailable before the release condition.
- Database constraints prevent duplicate answers.
- Topic completion is transactional.
- Privacy is enforced by the API, not by hiding fields in the client.

Acceptance checks:

- Direct API calls cannot expose unreleased partner answers.
- Submission retries do not create duplicates.
- Partial completion cannot be mistaken for completed submission.

### Step 12: Implement partner synchronization

When a partner completes a topic:

1. Mark their completion.
2. Check the matching topic version for the other partner.
3. Notify the other partner if still waiting.
4. Lock both answer sets when both complete.
5. Create exactly one analysis job.
6. Notify both users when analysis finishes.

Use database locking or a Redis lock to prevent duplicate analysis jobs.

Acceptance check: simultaneous completion creates one and only one analysis run.

### Step 13: Build the OpenAI service layer

Do not call OpenAI directly from Django views.

Suggested structure:

```text
apps/ai/
├── client.py
├── schemas.py
├── prompts/
├── services/
├── tasks.py
├── policies.py
├── moderation.py
├── exceptions.py
└── tests/
```

Requirements:

- Use the OpenAI Responses API.
- Keep model identifiers configurable.
- Use Pydantic structured-output schemas.
- Use `store=False` for sensitive relationship content.
- Execute analysis and long-running generation in Celery.
- Set timeouts, bounded retries, and circuit breakers.
- Store prompt version, model, status, and usage with each result.
- Do not log raw private prompts or API keys.
- The OpenAI key must exist only in the server/worker environment or secret manager.

Acceptance checks:

- Invalid AI output cannot enter domain tables.
- Refusals are distinguished from provider failures.
- Tasks are retry-safe.
- No OpenAI secret is returned to the client.

Official references:

- [OpenAI Responses API](https://developers.openai.com/api/docs/guides/text)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)

### Step 14: Implement AI safety policies

Account for:

- Abuse and coercion
- Self-harm
- Threats
- Sexual content
- Content involving minors
- Medical or legal questions

Pipeline:

1. Moderate input.
2. Classify safety risk.
3. Route normal content to the requested AI task.
4. Route high-risk content to a restricted safety response.
5. Prevent unsafe content from becoming pact clauses or challenges.
6. Use vetted, region-specific safety resources maintained outside model prompts.

Acceptance checks:

- Safety fixtures cover self-harm, abuse, threats, and minors.
- Unsafe AI suggestions cannot modify domain data.
- Safety events are auditable without unnecessary private-text retention.

Official reference:

- [OpenAI Moderation](https://developers.openai.com/api/docs/guides/moderation)

### Step 15: Implement AI follow-up questions

Trigger according to the configured question interval.

Input must include only:

- Current user's relevant answers
- Current topic
- User language
- Approved safety context

Structured result:

- Follow-up question
- Internal reason
- Topic linkage
- Skip indicator

Acceptance checks:

- Partner-private content is never used.
- Output validates against its Pydantic schema.
- Generated follow-ups persist and are not regenerated on refresh.

### Step 16: Implement topic analysis

Models:

- `AnalysisRun`
- `TopicAnalysis`
- `AlignmentDimension`
- `ConversationStarter`
- `ProposedClause`

Structured result:

- Alignment score
- Confidence
- Common ground
- Differences
- Sensitive areas
- Conversation starters
- Proposed clauses
- Safety flags

Calculate deterministic similarities where possible, then use AI to interpret and explain them.

Acceptance checks:

- Analysis begins only after both answer sets are locked.
- Reruns create new analysis versions.
- Failed analysis produces a recoverable application state.
- Output references the correct topic and members.

### Step 17: Implement discussions

Models:

- `DiscussionThread`
- `DiscussionMessage`
- `MediationRequest`
- `MediationResponse`

Rules:

- Both active members can participate.
- AI mediation receives only authorized thread context.
- User content is rendered as text, not raw HTML.
- AI messages are clearly identified.

Acceptance checks:

- Cross-couple thread access is impossible.
- Mediation failures do not lose user messages.

### Step 18: Implement versioned pacts

Models:

- `Pact`
- `PactVersion`
- `PactSection`
- `PactClause`
- `ClauseProposal`
- `ClauseApproval`

State model:

```text
Proposed
  -> Partner 1 approved
  -> Partner 2 approved
  -> Live immutable version
```

Editing a live pact must create a proposal and then a new pact version.

Acceptance checks:

- One partner cannot activate a pact alone.
- Editing proposal text invalidates earlier approvals.
- Live versions are immutable and reproducible.
- Concurrent approval is transaction-safe.

### Step 19: Generate and email pact PDFs

When a pact becomes live:

1. Generate an immutable PDF.
2. Store it privately.
3. Record its checksum and pact version.
4. Email both partners.
5. Provide authenticated, expiring download URLs.

Acceptance checks:

- PDF content matches the live database version.
- Download URLs expire.
- Cross-couple downloads are denied.
- Email retries do not create new pact versions.

### Step 20: Implement notifications

Models:

- `Device`
- `NotificationPreference`
- `Notification`
- `NotificationDelivery`

Initial events:

- Partner invitation
- Partner joined
- Topic completed
- Analysis ready
- Pact approval required
- Pact activated

Later events:

- Daily question
- Daily reveal
- Conflict perspective ready
- Monthly insight
- Challenge status

Acceptance checks:

- Disabled notification categories are respected.
- Device tokens can be revoked.
- Celery retries do not duplicate notifications.

### Step 21: Implement Daily questions

Models:

- `DailyQuestion`
- `DailyAssignment`
- `DailyAnswer`
- `DailyReveal`
- `CoupleStreak`

Streak and reveal logic must be deterministic, not AI-generated.

Acceptance checks:

- One answer per user per assignment.
- Answers remain private before reveal.
- Timezone boundaries and missed days are tested.

### Step 22: Implement monthly insights

Use a Celery job after the month closes and the minimum participation threshold is met.

Store:

- Input date range
- Prompt version
- Model
- Structured sections
- Safety flags
- Usage

Acceptance check: a job cannot include answers outside its assigned month.

### Step 23: Implement challenges

Models:

- `Challenge`
- `ChallengeAssignment`
- `ChallengeMemberCompletion`

Validate AI suggestions against an allowed challenge policy. Maintain curated fallback challenges.

Acceptance checks:

- Completion is independent for each partner.
- Unsafe or coercive challenges are rejected.
- Generation failure uses a safe fallback.

### Step 24: Implement AI Coach

Conversation scopes:

- `individual`: user-to-AI Coach
- `couple`: partner-to-partner chat, no AI run
- `conflict`: handled by Conflict Mode as AI-assisted therapist-like support

Models:

- `CoachConversation`
- `CoachParticipant`
- `CoachMessage`
- `CoachRun`

Critical rule: individual Coach content never enters partner insights, shared analysis, Couple chat, pact generation, or conflict mediation unless the user explicitly shares it.

Acceptance checks:

- Privacy tests cover every conversation scope.
- Only individual Coach and Conflict Mode send authorized context to OpenAI.
- Couple chat never generates an AI message.
- Disconnects and retries do not duplicate messages.

### Step 25: Implement conflict mode

Models:

- `ConflictThread`
- `ConflictPerspective`
- `ConflictBridge`
- `ConflictMessage`
- `ConflictMediation`
- `ConflictResolution`

Workflow:

1. Create conflict.
2. Both partners submit privately.
3. Lock both perspectives.
4. Generate therapist-like AI conflict support / neutral bridge.
5. Open shared discussion.
6. Allow optional mediation.
7. Resolve by explicit user action.
8. Send proposed pact changes through normal pact approval.

Acceptance checks:

- Private perspectives cannot be retrieved early.
- AI conflict support avoids assigning blame and does not claim to be licensed therapy.
- Resolution never edits a pact automatically.

### Step 26: Implement Moments

Models:

- `Moment`
- `MomentMedia`
- `MomentTopicLink`

Add image validation, metadata removal, thumbnail generation, private storage, and signed URLs.

Acceptance check: couple archival behavior matches the approved product rules.

### Step 27: Implement supporting profile features

Implement:

- Referral tracking
- Support tickets
- Notification settings
- Subscription management
- Data export request
- Account deletion request

Referral rewards must originate from verified billing events.

### Step 28: Implement export and deletion

Export should include all user-owned and permitted shared data.

Deletion workflow:

1. Reauthenticate.
2. Create a deletion request.
3. Revoke sessions.
4. Update billing.
5. Notify the partner.
6. Notify the partner without retaining a foreign-key link to the deleted couple.
7. Delete previous couple-scoped shared data so the remaining partner can connect with a new partner.
8. Delete or anonymize remaining account-owned private data in a background job.
9. Record completion without retaining deleted private content.

Acceptance checks:

- Deletion is retryable.
- One partner's deletion does not accidentally delete the other partner's owned data.
- Provider data handling matches the published privacy policy.

### Step 29: Build restricted Django Admin tools

Admin should manage:

- Topics and translations
- Prompt versions
- AI failures
- Safety flags
- Support tickets
- Failed billing events
- Failed notifications
- Deletion jobs

Private answers and Coach messages should not be casually visible to administrators. Use restricted, audited access where support access is necessary.

### Step 30: Testing, security, and deployment

Required tests:

- Model and constraint tests
- Serializer tests
- Permission tests
- API integration tests
- Celery task tests
- In-App Purchase receipt and server-notification tests
- OpenAI mocked-response tests
- AI schema tests
- AI safety evaluations
- Race-condition tests
- End-to-end two-user tests

Highest-priority security cases:

- Cross-couple object access
- Early partner-answer disclosure
- Individual Coach disclosure
- Conflict-perspective disclosure
- Pact approval races
- Invitation reuse
- Webhook replay
- Prompt injection
- XSS in messages and clauses
- Account deletion boundaries

Deployment requirements:

- Build one immutable production Docker image.
- Run migrations as a separate deployment job.
- Run API, worker, and scheduler from the same image.
- Store secrets in the deployment platform's secret manager.
- Add database backups and restore testing.
- Add error tracking and operational alerts.
- Add OpenAI and platform billing monitoring alerts.
- Add centralized structured logs.
- Document rollback procedures.

Do not use real relationship data in automated tests.

## 5. Milestones

### Milestone 1: Foundation

Steps 0-7.

Outcome: Dockerized backend with secure accounts, profiles, couples, invitations, and authorization.

### Milestone 2: Paid core experience

Steps 8-12.

Outcome: subscriptions, topic catalog, private responses, and partner synchronization.

### Milestone 3: AI analysis and pact

Steps 13-19.

Outcome: safe AI integration, follow-ups, analysis, discussions, two-party pact approval, and PDFs.

### Milestone 4: Engagement

Steps 20-23.

Outcome: notifications, Daily questions, monthly insights, and challenges.

### Milestone 5: Coaching and conflict

Steps 24-25.

Outcome: privacy-separated Coach modes and conflict mediation.

### Milestone 6: Supporting features and production

Steps 26-30.

Outcome: Moments, support features, referrals, deletion/export, administration, testing, and production deployment.

## 6. Decisions still required

Answer these before finalizing database models and API contracts:

1. Which frontend will consume the API: native iOS/Swift, Flutter, React Native, or web?
2. Should development target the recommended MVP first or every prototype feature before launch?
3. Which countries will launch first, and will Patto be restricted to users aged 18 or older?
4. Which authentication methods are required besides SMTP email OTP: password, Apple, and/or Google?
5. In-App Purchase is confirmed for billing; confirm target platforms: Apple, Google, or both.
6. Which Docker hosting platform will be used?
7. Does the first release require WebSockets, or are push notifications plus API refresh sufficient?
8. What initial user volume and monthly OpenAI budget should the system support?

## 7. Required planning documents before feature implementation

After the decisions above are answered, prepare:

1. `docs/PRODUCT_RULES.md`
2. `docs/ERD.md`
3. `docs/API_CONTRACT.md`
4. `docs/PRIVACY_MATRIX.md`
5. `docs/AI_DESIGN.md`
6. `docs/DEPLOYMENT.md`
7. `docs/TEST_STRATEGY.md`

The ERD, privacy matrix, and API contract should be approved before implementing topic responses, analysis, pacts, Coach, or conflicts.
