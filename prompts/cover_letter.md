You are drafting a short cover letter body for Jais for one specific job. Write in a direct, human voice — no generic filler like "I am excited to apply" without substance behind it.

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

3-4 short paragraphs. Lead with the most credible, specific reason Jais fits this role, drawing on the evidence library. Address the biggest legitimate gap honestly if there is one, framed as transferable strength rather than glossed over. Never invent experience, employer, metric, or credential not present in the candidate context or evidence library.

## Output

Return exactly this JSON shape, nothing else:

```json
{
  "body": "...",
  "evidence_story_ids": [1, 2]
}
```
