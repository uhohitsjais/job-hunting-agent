You are extracting a structured candidate profile from pasted LinkedIn profile text and (optionally) resume text. This is a best-effort first draft — Jais will review and edit every field before anything is saved, so it is fine (expected, even) to leave a field empty rather than guess.

Only extract what the source text actually supports:

- `target_titles`: infer from his most recent 1-2 job titles and career trajectory — what titles is he plausibly targeting next. Do not invent aspirational titles with no basis in his history.
- `strongest_skills`: skills genuinely evidenced by his experience section, not a generic skills list.
- `years_experience`: compute from the earliest professional role's start date to now, if dates are present.
- `preferred_locations`: only if the text explicitly states a location preference or "open to" section — do not assume his current city is his only preference.
- `known_gaps`: only flag something as a gap if the text gives a specific reason to (e.g. an explicit statement, or a role requiring a tool/skill never mentioned anywhere in his history) — do not speculate broadly.

These fields are almost never stated in a LinkedIn profile or resume — leave them empty/null unless the text explicitly says otherwise. Do not guess:
- `preferred_industries`, `excluded_industries` — these are personal preferences, not inferable from work history alone.
- `remote_preference`, `preferred_company_size`, `stretch_willingness` — personal preferences.
- `min_salary`, `preferred_salary` — never stated in a LinkedIn profile or resume.

## LinkedIn profile text

{{linkedin_text}}

## Resume text

{{resume_text}}

## Output

Return exactly this JSON shape, nothing else:

```json
{
  "target_titles": ["..."],
  "preferred_industries": [],
  "excluded_industries": [],
  "preferred_locations": ["..."],
  "remote_preference": null,
  "min_salary": null,
  "preferred_salary": null,
  "strongest_skills": ["..."],
  "known_gaps": [],
  "preferred_company_size": [],
  "years_experience": 0,
  "stretch_willingness": null
}
```
