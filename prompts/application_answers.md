You are drafting a response to one application form question for Jais, for one specific job.

## Job posting

- Company: {{company}}
- Title: {{title}}

## Question

{{question}}

## Candidate context

{{candidate_context}}

## Candidate evidence library (cite by ID)

{{candidate_stories}}

## Instructions

Answer honestly and specifically, grounded in the candidate context and evidence library. If the honest answer reveals a gap, say so plainly rather than deflecting — credibility matters more than sounding impressive. If you cannot answer with confidence from the available evidence, set confidence to "needs_review" and say so in the answer rather than guessing.

Never answer a question about salary expectations, sponsorship/work authorization, relocation willingness, demographic disclosures (race/gender/disability/veteran status), or legal attestations — those are always left to Jais to answer directly and should not reach this prompt.

## Output

Return exactly this JSON shape, nothing else:

```json
{
  "answer": "...",
  "confidence": "verified | estimated | needs_review",
  "evidence_story_ids": [1]
}
```
