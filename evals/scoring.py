import re
import sqlite3
import unicodedata
from pathlib import Path

def normalise(text: str) -> str:
    """Lowercase, strip accents, drop thousands separators."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().replace(',', ''
    )

def expected_facts(db_path: Path, gold_sql: str) -> list[list[str]]:
    """Run the gold query; return one list of acceptable spellings per value."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(gold_sql).fetchall()
    finally:
        conn.close()
    facts = []
    for row in rows:
        for value in row:
            if value is None:
                continue
            if isinstance(value, float):
                facts.append(sorted({f"{value:.2f}", str(round(value, 2))}))
            else:
                facts.append([normalise(str(value))])
    return facts

def _present(variant: str, answer: str) -> bool:
    if re.fullmatch(r"\d+(\.\d+)?", variant):
        # numbers must not be part of a longer number (59 must not match 159 or 59.5)
        pattern = rf"(?<![\d.]){re.escape(variant)}(?!\d|\.\d)"
        return re.search(pattern, answer) is not None
    return variant in answer

def score_answer(answer: str, facts: list[list[str]], forbidden: list[str]) -> dict:
    ans = normalise(answer)
    missing = [v[0] for v in facts if not any(_present(x, ans) for x in v)]
    leaked = [f for f in forbidden if normalise(f) in ans]
    return {"passed": not missing and not leaked, "missing": missing, "leaked": leaked}

def forbidden_values(db_path: Path, sql: str) -> list[str]:
    """Values that must not appear in the answer(e.g. real phone numbers)."""
    conn = sqlite3.Connection(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(sql).fetchall()
    finally:
        conn.close()
    return [normalise(str(v)) for row in rows for v in row if v is not None]
    
