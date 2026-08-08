import hashlib
from dataclasses import dataclass
from enum import StrEnum

from apps.ai.models import AISafetyEvent


class SafetyCategory(StrEnum):
    ABUSE_COERCION = "abuse_coercion"
    SELF_HARM = "self_harm"
    THREAT = "threat"
    SEXUAL_CONTENT = "sexual_content"
    MINORS = "minors"
    MEDICAL_LEGAL = "medical_legal"
    PROMPT_INJECTION = "prompt_injection"


class SafetySeverity(StrEnum):
    SAFE = "safe"
    CAUTION = "caution"
    HIGH = "high"
    BLOCKED = "blocked"


class SafetyRoute(StrEnum):
    NORMAL = "normal"
    RESTRICTED_SAFETY = "restricted_safety"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class SafetyFinding:
    category: SafetyCategory
    severity: SafetySeverity
    route: SafetyRoute
    matched_policy: str


@dataclass(frozen=True)
class SafetyDecision:
    findings: tuple[SafetyFinding, ...]
    content_fingerprint: str

    @property
    def route(self) -> SafetyRoute:
        if any(finding.route == SafetyRoute.BLOCKED for finding in self.findings):
            return SafetyRoute.BLOCKED
        if any(finding.route == SafetyRoute.RESTRICTED_SAFETY for finding in self.findings):
            return SafetyRoute.RESTRICTED_SAFETY
        return SafetyRoute.NORMAL

    @property
    def highest_severity(self) -> SafetySeverity:
        order = {
            SafetySeverity.SAFE: 0,
            SafetySeverity.CAUTION: 1,
            SafetySeverity.HIGH: 2,
            SafetySeverity.BLOCKED: 3,
        }
        return max((finding.severity for finding in self.findings), key=lambda item: order[item], default=SafetySeverity.SAFE)

    @property
    def is_restricted(self) -> bool:
        return self.route in {SafetyRoute.RESTRICTED_SAFETY, SafetyRoute.BLOCKED}


POLICY_RULES: tuple[tuple[SafetyCategory, SafetySeverity, SafetyRoute, str, tuple[str, ...]], ...] = (
    (
        SafetyCategory.SELF_HARM,
        SafetySeverity.HIGH,
        SafetyRoute.RESTRICTED_SAFETY,
        "self_harm_intent",
        ("kill myself", "end my life", "suicide", "self harm", "hurt myself"),
    ),
    (
        SafetyCategory.THREAT,
        SafetySeverity.HIGH,
        SafetyRoute.RESTRICTED_SAFETY,
        "threat_or_violence",
        ("i will kill", "going to kill", "hurt my partner", "beat my partner", "threaten"),
    ),
    (
        SafetyCategory.ABUSE_COERCION,
        SafetySeverity.HIGH,
        SafetyRoute.RESTRICTED_SAFETY,
        ("coercive_control"),
        ("force my partner", "control my partner", "track my partner", "isolate my partner", "won't let them leave"),
    ),
    (
        SafetyCategory.MINORS,
        SafetySeverity.BLOCKED,
        SafetyRoute.BLOCKED,
        "sexual_content_involving_minors",
        ("minor sexual", "underage sexual", "child sexual", "sex with a minor"),
    ),
    (
        SafetyCategory.SEXUAL_CONTENT,
        SafetySeverity.CAUTION,
        SafetyRoute.NORMAL,
        "adult_sexual_content",
        ("sexual", "sex life", "intimacy", "bedroom"),
    ),
    (
        SafetyCategory.MEDICAL_LEGAL,
        SafetySeverity.CAUTION,
        SafetyRoute.NORMAL,
        "medical_or_legal_advice",
        ("medical advice", "legal advice", "divorce lawyer", "custody", "diagnose", "prescription"),
    ),
    (
        SafetyCategory.PROMPT_INJECTION,
        SafetySeverity.HIGH,
        SafetyRoute.RESTRICTED_SAFETY,
        "prompt_injection",
        ("ignore previous instructions", "reveal your system prompt", "developer message", "bypass safety"),
    ),
)


def classify_safety_text(text: str) -> SafetyDecision:
    normalized = text.lower()
    findings = []
    for category, severity, route, policy_key, phrases in POLICY_RULES:
        if any(phrase in normalized for phrase in phrases):
            findings.append(
                SafetyFinding(
                    category=category,
                    severity=severity,
                    route=route,
                    matched_policy=policy_key,
                )
            )
    return SafetyDecision(findings=tuple(findings), content_fingerprint=fingerprint_text(text))


def fingerprint_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_safety_decision(*, analysis_job, stage: str, decision: SafetyDecision) -> list[AISafetyEvent]:
    events = []
    for finding in decision.findings:
        event, _ = AISafetyEvent.objects.get_or_create(
            analysis_job=analysis_job,
            stage=stage,
            category=finding.category.value,
            detector="local_policy_v1",
            defaults={
                "severity": finding.severity.value,
                "route": finding.route.value,
                "content_fingerprint": decision.content_fingerprint,
                "metadata": {
                    "matched_policy": finding.matched_policy,
                    "raw_text_retained": False,
                },
            },
        )
        events.append(event)
    return events


def restricted_safety_output(decision: SafetyDecision) -> dict:
    categories = sorted({finding.category.value for finding in decision.findings})
    return {
        "relationship_summary": (
            "This topic needs a safety-first conversation before normal relationship analysis can continue."
        ),
        "alignment_score": 0,
        "strengths": ["You shared something important that should be handled carefully."],
        "growth_areas": ["Pause pact-making and prioritize immediate safety, consent, and appropriate support."],
        "conversation_starters": [
            "What support would help everyone stay safe right now?",
            "Is there a trusted person or local professional resource you can contact today?",
        ],
        "suggested_pact_items": [],
        "safety_notes": [
            "High-risk content was detected, so normal AI analysis was restricted.",
            f"Detected safety categories: {', '.join(categories)}.",
            "Use vetted, region-specific safety resources from the app rather than model-generated hotline details.",
        ],
    }
