def is_leadership_role(role: str) -> bool:
    normalized = role.lower()
    return any(
        token in normalized
        for token in ("manager", "director", "head of", "head", "lead")
    )
