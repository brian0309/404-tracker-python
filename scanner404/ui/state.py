def default_counts() -> dict[str, int]:
    return {"Pending": 0, "200": 0, "404": 0, "ERR": 0}


def summary_text(counts: dict[str, int]) -> str:
    processed = counts["200"] + counts["404"] + counts["ERR"]
    found = processed + counts["Pending"]
    return (
        "Found: "
        f"{found} | Processed: {processed} | Pending: {counts['Pending']}"
        f" | 200: {counts['200']} | 404: {counts['404']} | ERR: {counts['ERR']}"
    )


def has_retryable_errors(all_rows: dict[str, tuple[str, str]]) -> bool:
    return any(status in ("404", "ERR") for _, status in all_rows.values())
