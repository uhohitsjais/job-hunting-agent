You are writing a resume summary/headline for Jais, tailored to one specific job. This is a short paragraph (2-4 sentences), not a full resume.

## Job posting

- Company: {{company}}
- Title: {{title}}
- Description:
{{job_description}}

## Candidate context

{{candidate_context}}

## Candidate evidence library (cite by ID)

{{candidate_stories}}

## Instructions

Write a summary that positions Jais credibly for this specific role, emphasizing the strongest genuine overlaps between her background and the job. If the role is a stretch, lean on transferable experience rather than exaggerating direct experience. Never state a qualification, metric, or title that isn't backed by the candidate context or evidence library.

## Output

Return exactly this JSON shape, nothing else:

```json
{
  "summary": "...",
  "evidence_story_ids": [1, 2]
}
```
