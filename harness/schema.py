"""
Fixed JSON schema the judge must return. Keeping this in one place means the
harness never depends on regex-parsing free text — if the model doesn't
return valid JSON matching this shape, the item is marked as a parse failure
and reported, not silently dropped.
"""

CRITERIA = ["accuracy", "relevance", "clarity", "completeness", "safety"]

JUDGE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "properties": {c: {"type": "integer", "minimum": 1, "maximum": 5} for c in CRITERIA},
            "required": CRITERIA,
        },
        "overall": {"type": "integer", "minimum": 1, "maximum": 5},
        "reason": {"type": "string"},
        "unsafe": {"type": "boolean"},
    },
    "required": ["scores", "overall", "reason", "unsafe"],
}


class SchemaError(ValueError):
    pass


def validate_judge_output(obj: dict) -> dict:
    """Raises SchemaError with a specific message on any mismatch; otherwise
    returns a normalized dict (ints coerced, extra keys dropped)."""
    if not isinstance(obj, dict):
        raise SchemaError("top-level output is not a JSON object")

    if "scores" not in obj or not isinstance(obj["scores"], dict):
        raise SchemaError("missing or invalid 'scores' object")

    scores = {}
    for c in CRITERIA:
        if c not in obj["scores"]:
            raise SchemaError(f"missing criterion '{c}' in scores")
        try:
            v = int(obj["scores"][c])
        except (TypeError, ValueError):
            raise SchemaError(f"criterion '{c}' is not an integer")
        if not (1 <= v <= 5):
            raise SchemaError(f"criterion '{c}'={v} out of range 1-5")
        scores[c] = v

    if "overall" not in obj:
        raise SchemaError("missing 'overall'")
    try:
        overall = int(obj["overall"])
    except (TypeError, ValueError):
        raise SchemaError("'overall' is not an integer")
    if not (1 <= overall <= 5):
        raise SchemaError(f"'overall'={overall} out of range 1-5")

    reason = str(obj.get("reason", "")).strip()
    if not reason:
        raise SchemaError("missing 'reason'")

    unsafe = bool(obj.get("unsafe", False))

    return {"scores": scores, "overall": overall, "reason": reason, "unsafe": unsafe}
