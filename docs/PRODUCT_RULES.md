# Patto Product Rules

## Status

These rules are implementation assumptions for the first backend build. Review them before building paid user-facing flows.

## MVP Assumptions

1. The first release targets a mobile or web client using a versioned JSON API.
2. The first release ships the recommended MVP from `docs/IMPLEMENTATION_PLAN.md`.
3. Patto is restricted to users aged 18 or older.
4. Mobile In-App Purchase is the billing default. The backend validates platform purchase receipts/server notifications and stores normalized entitlements.
5. Push notifications plus API refresh are enough for the first release; WebSockets are deferred.
6. Docker Compose is the local runtime, with one shared image for API, worker, and beat.
7. Email OTP is delivered through SMTP.

## Couple Rules

1. A couple space can have at most two active partners.
2. Partner 1 owns the paid subscription.
3. Partner 2 inherits access from Partner 1 while the couple is active and the entitlement is valid.
4. An account can belong to only one active couple at a time during MVP.
5. Account deletion or partner disconnection fully severs the couple connection.
6. After disconnection, the remaining partner can create a new couple and invite a new partner using the normal invitation URL flow.

## Privacy Rules

1. Individual topic answers stay private until both partners complete the same topic version.
2. Individual Coach conversations are user-to-AI and are never visible to the other partner.
3. Couple conversations are partner-to-partner chat only; no AI response is generated in Couple chat.
4. Conflict mode is AI-assisted, therapist-like conflict support, but Patto must not claim to provide licensed therapy.
5. Conflict perspectives stay private until both partners submit.
6. AI suggestions never edit live pact content automatically.
7. A pact clause becomes live only after both partners approve the exact same version.
8. Patto must not present itself as licensed therapy, medical treatment, legal advice, or emergency support.

## Data Retention

Users must export their data before account deletion or partner disconnection. Once deletion/disconnection is processed, the previous couple's shared data is deleted rather than archived.
