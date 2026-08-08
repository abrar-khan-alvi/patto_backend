from dataclasses import dataclass, field

from apps.ai.policies import SafetyRoute, classify_safety_text


COERCIVE_TERMS = {
    "force",
    "make them",
    "punish",
    "punishment",
    "silent treatment",
    "withhold affection",
    "track their phone",
    "spy",
    "control",
    "ultimatum",
    "threaten",
    "humiliate",
}

REQUIRED_BENIGN_TERMS = {
    "ask",
    "share",
    "listen",
    "appreciate",
    "plan",
    "check",
    "thank",
    "support",
    "together",
    "kind",
    "gentle",
}


@dataclass(frozen=True)
class ChallengePolicyDecision:
    allowed: bool
    flags: list[str] = field(default_factory=list)
    reason: str = ""
    policy_version: str = "challenge_policy_v1"


def validate_challenge_policy(*, title: str, description: str, instructions: str = "") -> ChallengePolicyDecision:
    content = " ".join([title, description, instructions]).lower()
    flags = []
    safety_decision = classify_safety_text(content)
    if safety_decision.route in {SafetyRoute.RESTRICTED_SAFETY, SafetyRoute.BLOCKED}:
        flags.append(f"safety:{safety_decision.category.value}")
        return ChallengePolicyDecision(False, flags, "Challenge was blocked by AI safety policy.")

    matched_coercive_terms = sorted(term for term in COERCIVE_TERMS if term in content)
    if matched_coercive_terms:
        flags.extend([f"coercive:{term}" for term in matched_coercive_terms])
        return ChallengePolicyDecision(False, flags, "Challenge contains coercive or controlling language.")

    if len(description.strip()) < 20:
        flags.append("too_short")
        return ChallengePolicyDecision(False, flags, "Challenge description is too short to validate safely.")

    if not any(term in content for term in REQUIRED_BENIGN_TERMS):
        flags.append("not_constructive")
        return ChallengePolicyDecision(False, flags, "Challenge does not clearly describe a constructive relationship action.")

    return ChallengePolicyDecision(True, flags, "")
