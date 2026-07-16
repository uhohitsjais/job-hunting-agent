from __future__ import annotations

import json
import os

from .base import (
    AIProvider,
    ApplicationAnswerResult,
    CoverLetterResult,
    ModelCallMetadata,
    ProfileExtractionResult,
    RecommendationResult,
    ResumeSummaryResult,
    ResumeTailoringResult,
)
from .prompt_loader import load_prompt, render_prompt

RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "decision": {"type": "string", "enum": ["priority", "apply", "stretch", "archive"]},
        "reasons_to_apply": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "disqualifiers": {"type": "array", "items": {"type": "string"}},
        "positioning_strategy": {"type": "string"},
        "evidence_story_ids": {"type": "array", "items": {"type": "integer"}},
    },
    "required": [
        "score",
        "decision",
        "reasons_to_apply",
        "gaps",
        "disqualifiers",
        "positioning_strategy",
        "evidence_story_ids",
    ],
    "additionalProperties": False,
}

PROFILE_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "target_titles": {"type": "array", "items": {"type": "string"}},
        "preferred_industries": {"type": "array", "items": {"type": "string"}},
        "excluded_industries": {"type": "array", "items": {"type": "string"}},
        "preferred_locations": {"type": "array", "items": {"type": "string"}},
        "remote_preference": {"type": ["string", "null"]},
        "min_salary": {"type": ["integer", "null"]},
        "preferred_salary": {"type": ["integer", "null"]},
        "strongest_skills": {"type": "array", "items": {"type": "string"}},
        "known_gaps": {"type": "array", "items": {"type": "string"}},
        "preferred_company_size": {"type": "array", "items": {"type": "string"}},
        "years_experience": {"type": ["integer", "null"]},
        "stretch_willingness": {"type": ["string", "null"]},
    },
    "required": [
        "target_titles",
        "preferred_industries",
        "excluded_industries",
        "preferred_locations",
        "remote_preference",
        "min_salary",
        "preferred_salary",
        "strongest_skills",
        "known_gaps",
        "preferred_company_size",
        "years_experience",
        "stretch_willingness",
    ],
    "additionalProperties": False,
}

RESUME_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "evidence_story_ids": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["summary", "evidence_story_ids"],
    "additionalProperties": False,
}

COVER_LETTER_SCHEMA = {
    "type": "object",
    "properties": {
        "body": {"type": "string"},
        "evidence_story_ids": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["body", "evidence_story_ids"],
    "additionalProperties": False,
}


def _format_list(values: list[str] | None) -> str:
    return ", ".join(values) if values else "none specified"


def _format_salary_range(salary_min: int | None, salary_max: int | None) -> str:
    if salary_min and salary_max:
        return f"${salary_min:,}-${salary_max:,}"
    if salary_max:
        return f"up to ${salary_max:,}"
    if salary_min:
        return f"${salary_min:,}+"
    return "not specified"


def _format_stories(stories: list[dict]) -> str:
    if not stories:
        return "No approved candidate stories yet — do not fabricate evidence; note gaps honestly instead."
    lines = []
    for story in stories:
        lines.append(
            f"- [{story['id']}] {story['title']}: {story.get('situation', '')} "
            f"Actions: {story.get('actions', '')} Result: {story.get('result', '')}"
        )
    return "\n".join(lines)


class OpenAIProvider(AIProvider):
    """AIProvider implementation using the OpenAI Responses API with
    structured JSON schema output. tailor_resume and
    answer_application_question remain stubs until M8/M9 need them."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.environ.get("OPENAI_MODEL", "")
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is not set. Add it to .env (see .env.example)."
                )
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def _call_structured(
        self,
        prompt_file: str,
        variables: dict,
        schema: dict,
        schema_name: str,
        input_context: dict,
    ) -> tuple[dict, ModelCallMetadata]:
        if not self.model_name:
            raise RuntimeError(
                "OPENAI_MODEL is not set. Add it to .env (see .env.example)."
            )
        prompt_text, prompt_version = load_prompt(prompt_file)
        rendered_prompt = render_prompt(prompt_text, variables)

        response = self.client.responses.create(
            model=self.model_name,
            input=rendered_prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        raw_output = response.output_text
        data = json.loads(raw_output)
        metadata = ModelCallMetadata(
            prompt_file=prompt_file,
            prompt_version=prompt_version,
            model_name=self.model_name,
            raw_output=raw_output,
            input_context=input_context,
        )
        return data, metadata

    def recommend_job(
        self, job, profile, candidate_context, stories, deterministic_flags
    ) -> tuple[RecommendationResult, ModelCallMetadata]:
        variables = {
            "company": job.get("company", ""),
            "title": job.get("title", ""),
            "location": job.get("location") or "unspecified",
            "remote_type": job.get("remote_type") or "unknown",
            "salary_range": _format_salary_range(job.get("salary_min"), job.get("salary_max")),
            "job_description": job.get("description", ""),
            "deterministic_flags": "\n".join(deterministic_flags) if deterministic_flags else "None",
            "target_titles": _format_list(profile.get("target_titles")),
            "preferred_industries": _format_list(profile.get("preferred_industries")),
            "excluded_industries": _format_list(profile.get("excluded_industries")),
            "preferred_locations": _format_list(profile.get("preferred_locations")),
            "remote_preference": profile.get("remote_preference") or "not specified",
            "min_salary": f"${profile['min_salary']:,}" if profile.get("min_salary") else "not specified",
            "preferred_salary": f"${profile['preferred_salary']:,}" if profile.get("preferred_salary") else "not specified",
            "strongest_skills": _format_list(profile.get("strongest_skills")),
            "known_gaps": _format_list(profile.get("known_gaps")),
            "preferred_company_size": _format_list(profile.get("preferred_company_size")),
            "years_experience": profile.get("years_experience") or "not specified",
            "stretch_willingness": profile.get("stretch_willingness") or "not specified",
            "candidate_context": candidate_context,
            "candidate_stories": _format_stories(stories),
        }
        data, metadata = self._call_structured(
            "recommendation.md",
            variables,
            RECOMMENDATION_SCHEMA,
            "job_recommendation",
            {"job_id": job.get("id"), "deterministic_flags": deterministic_flags},
        )
        result = RecommendationResult(
            score=data["score"],
            decision=data["decision"],
            reasons_to_apply=data["reasons_to_apply"],
            gaps=data["gaps"],
            disqualifiers=data["disqualifiers"],
            positioning_strategy=data["positioning_strategy"],
            evidence_story_ids=data.get("evidence_story_ids", []),
        )
        return result, metadata

    def extract_candidate_profile(
        self, linkedin_text, resume_text
    ) -> tuple[ProfileExtractionResult, ModelCallMetadata]:
        variables = {
            "linkedin_text": linkedin_text or "(not provided)",
            "resume_text": resume_text or "(not provided)",
        }
        data, metadata = self._call_structured(
            "profile_extraction.md",
            variables,
            PROFILE_EXTRACTION_SCHEMA,
            "profile_extraction",
            {"linkedin_text_length": len(linkedin_text or ""), "resume_text_length": len(resume_text or "")},
        )
        result = ProfileExtractionResult(**data)
        return result, metadata

    def generate_resume_summary(
        self, job, candidate_context, stories
    ) -> tuple[ResumeSummaryResult, ModelCallMetadata]:
        variables = {
            "company": job.get("company", ""),
            "title": job.get("title", ""),
            "job_description": job.get("description", ""),
            "candidate_context": candidate_context,
            "candidate_stories": _format_stories(stories),
        }
        data, metadata = self._call_structured(
            "resume_summary.md",
            variables,
            RESUME_SUMMARY_SCHEMA,
            "resume_summary",
            {"job_id": job.get("id")},
        )
        result = ResumeSummaryResult(
            summary=data["summary"], evidence_story_ids=data.get("evidence_story_ids", [])
        )
        return result, metadata

    def tailor_resume(self, job, base_resume_text, stories) -> ResumeTailoringResult:
        raise NotImplementedError("Deferred — bullet-level tailoring needs a base resume broken into sections")

    def generate_cover_letter(
        self, job, candidate_context, stories
    ) -> tuple[CoverLetterResult, ModelCallMetadata]:
        variables = {
            "company": job.get("company", ""),
            "title": job.get("title", ""),
            "job_description": job.get("description", ""),
            "candidate_context": candidate_context,
            "candidate_stories": _format_stories(stories),
        }
        data, metadata = self._call_structured(
            "cover_letter.md",
            variables,
            COVER_LETTER_SCHEMA,
            "cover_letter",
            {"job_id": job.get("id")},
        )
        result = CoverLetterResult(
            body=data["body"], evidence_story_ids=data.get("evidence_story_ids", [])
        )
        return result, metadata

    def answer_application_question(
        self, job, question, candidate_context, stories
    ) -> ApplicationAnswerResult:
        raise NotImplementedError("Wired up when M9-equivalent review queue needs it")
