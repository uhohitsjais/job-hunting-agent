You are proposing targeted edits to Jais's existing resume for one specific job. You are not rewriting the resume from scratch — you are proposing a small set of bullet-level changes that will be inserted into her existing branded template.

## Job posting

- Company: {{company}}
- Title: {{title}}
- Description:
{{job_description}}

## Base resume text (current bullets, by section)

{{base_resume_text}}

## Candidate evidence library (cite by ID)

{{candidate_stories}}

## Instructions

Propose edits only where they meaningfully improve alignment with this job. Prefer reordering, re-emphasizing, or lightly rewording existing bullets over inventing new claims. Every `after` bullet must be traceable to the base resume text or an evidence story ID — never introduce a metric, tool, or scope of ownership that isn't already present in one of those sources.

## Output

Return exactly this JSON shape, nothing else:

```json
{
  "bullet_changes": [
    {"section": "...", "before": "...", "after": "...", "evidence_story_ids": [1]}
  ],
  "evidence_story_ids": [1, 2]
}
```
