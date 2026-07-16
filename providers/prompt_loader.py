import hashlib
import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(filename: str) -> tuple[str, str]:
    """Returns (prompt_text, version_hash). Editing a prompt file changes the
    hash, which model_runs.prompt_version records for inspectability."""
    text = (PROMPTS_DIR / filename).read_text()
    version_hash = hashlib.sha256(text.encode()).hexdigest()[:12]
    return text, version_hash


def render_prompt(template: str, variables: dict) -> str:
    """Fills {{key}} placeholders. Intentionally not a templating engine —
    prompts stay plain Markdown, editable without touching Python."""

    def replace(match: re.Match) -> str:
        return str(variables.get(match.group(1).strip(), ""))

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", replace, template)
