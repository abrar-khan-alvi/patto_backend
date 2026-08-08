BLAME_PHRASES = (
    "is at fault",
    "was at fault",
    "to blame",
    "blame ",
    "fault lies",
    "clearly wrong",
    "the problem is your partner",
)


def bridge_avoids_blame(*, neutral_summary: str, partner_summaries: dict | None = None, next_steps: list | None = None) -> bool:
    content = " ".join(
        [
            neutral_summary,
            " ".join(str(value) for value in (partner_summaries or {}).values()),
            " ".join(str(value) for value in (next_steps or [])),
        ]
    ).lower()
    return not any(phrase in content for phrase in BLAME_PHRASES)
