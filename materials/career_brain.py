from __future__ import annotations

import hashlib
from pathlib import Path

# Repo-root career_brain/ — sibling of this materials/ package, not inside it.
CAREER_BRAIN_DIR = Path(__file__).resolve().parent.parent / "career_brain"

# profile/ and preferences/ are always loaded, full stop. stories/ and
# evidence/ are loaded in full for V0.1 (small folder count — no retrieval
# needed) but are the folders most likely to eventually need
# filtering/retrieval once this grows large, per the README.
FOLDERS = ["profile", "preferences", "stories", "evidence"]


def _read_folder(base_dir: Path, folder_name: str) -> list[dict]:
    """Every .md file under base_dir/folder_name, recursive, sorted for
    deterministic order. A missing folder — or a missing career_brain/
    entirely — just means an empty list, never an error. A single
    unreadable file is skipped, not fatal to the rest."""
    folder = base_dir / folder_name
    if not folder.is_dir():
        return []
    docs = []
    for path in sorted(folder.rglob("*.md")):
        if not path.is_file():
            continue
        try:
            content = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        docs.append({"path": str(path.relative_to(base_dir.parent)), "content": content})
    return docs


def load_career_brain_context(base_dir: Path | None = None) -> tuple[str, list[str]]:
    """Reads every .md file under career_brain/{profile,preferences,stories,evidence}/
    fresh from disk. Returns (combined_text, loaded_paths). Combined_text is
    "" and loaded_paths is [] if nothing exists yet — callers should treat
    that as "no Career Brain content available," not an error."""
    base_dir = base_dir or CAREER_BRAIN_DIR
    all_docs = []
    for folder_name in FOLDERS:
        all_docs.extend(_read_folder(base_dir, folder_name))

    if not all_docs:
        return "", []

    parts = [f"### {doc['path']}\n\n{doc['content']}" for doc in all_docs]
    combined = "\n\n---\n\n".join(parts)
    loaded_paths = [doc["path"] for doc in all_docs]
    return combined, loaded_paths


def hash_career_brain_context(career_brain_text: str) -> str:
    """Short content hash of the Career Brain text actually used in one
    generation/evaluation — logged alongside the file list so a later,
    edited version of the same files is distinguishable from what was
    actually used at the time (reproducibility, not just a file listing)."""
    if not career_brain_text:
        return ""
    return hashlib.sha256(career_brain_text.encode()).hexdigest()[:12]
