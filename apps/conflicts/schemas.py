from pydantic import BaseModel, ConfigDict, Field


class ConflictBridgeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    neutral_summary: str = Field(min_length=1, max_length=1600)
    partner_summaries: dict[str, str] = Field(default_factory=dict)
    common_ground: list[str] = Field(default_factory=list, max_length=6)
    next_steps: list[str] = Field(default_factory=list, max_length=6)
    safety_flags: list[str] = Field(default_factory=list, max_length=8)


CONFLICT_BRIDGE_JSON_SCHEMA = ConflictBridgeSchema.model_json_schema()
