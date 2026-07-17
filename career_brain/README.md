# Career Brain

The long-term source of truth about Jais as a candidate — not a resume. This is markdown files on disk; there is no database, no embeddings, no vector search. `materials/career_brain.py` reads every `.md` file under the four folders below (recursively, so subfolders for your own organization are fine) fresh at generation time — drop a new file in, it's included on the next generation, no restart needed.

This file itself lives outside the four loaded folders, so it's never sent to the model as candidate content.

## Folders

- **`profile/`** — who Jais is as a candidate: career narrative, leadership style, decision-making style, communication style, product philosophy. Always loaded.
- **`preferences/`** — writing/tone preferences, how she wants to be positioned, things to always/never say. Always loaded.
- **`stories/`** — career stories, major initiatives, interview stories, specific accomplishments with situation/actions/result shape. Loaded in full for V0.1 (small folder, no retrieval needed yet).
- **`evidence/`** — performance reviews, recommendations, metrics, project artifacts — the receipts behind the stories. Loaded in full for V0.1.

## What generation does with this

Every application-materials generation (resume summary, cover letter):
1. Reads every `.md` file in all four folders above.
2. Appends them to the existing LinkedIn/resume context (that context isn't replaced — Career Brain layers on top of it, so generation quality never regresses even while this folder is still mostly empty).
3. Shows you exactly which document paths were loaded, on the job detail page and in the terminal.
4. Saves that exact list alongside the generated materials, so any past resume/cover letter is reproducible — you can always see what fed it.

## Adding content

Just drop a `.md` file in the right folder. No registration, no config, no restart. Organize with subfolders however you like (e.g. `stories/leadership/`, `evidence/2025-performance-review.md`) — the loader recurses.
