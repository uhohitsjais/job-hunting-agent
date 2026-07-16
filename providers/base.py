from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RecommendationResult:
    score: int  # 0-100
    decision: str  # priority | apply | stretch | archive — never "rejected", every job stays visible
    reasons_to_apply: list[str]
    gaps: list[str]
    disqualifiers: list[str]
    positioning_strategy: str
    evidence_story_ids: list[int] = field(default_factory=list)


@dataclass
class ProfileExtractionResult:
    """What extract_candidate_profile returns — mirrors the structured
    fields in candidate_profile. Fields LinkedIn/resume text can't speak to
    (excluded_industries, preferred_salary, remote_preference, stretch
    willingness, company size preference) are expected to come back empty;
    the user fills those in on the review screen before saving."""

    target_titles: list[str] = field(default_factory=list)
    preferred_industries: list[str] = field(default_factory=list)
    excluded_industries: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    remote_preference: str | None = None
    min_salary: int | None = None
    preferred_salary: int | None = None
    strongest_skills: list[str] = field(default_factory=list)
    known_gaps: list[str] = field(default_factory=list)
    preferred_company_size: list[str] = field(default_factory=list)
    years_experience: int | None = None
    stretch_willingness: str | None = None


@dataclass
class ModelCallMetadata:
    """What model_runs needs for inspectability, returned alongside every
    structured result so callers never have to re-derive it."""

    prompt_file: str
    prompt_version: str
    model_name: str
    raw_output: str
    input_context: dict


@dataclass
class ResumeSummaryResult:
    summary: str
    evidence_story_ids: list[int] = field(default_factory=list)


@dataclass
class ResumeTailoringResult:
    bullet_changes: list[dict]  # [{section, before, after}]
    evidence_story_ids: list[int] = field(default_factory=list)


@dataclass
class CoverLetterResult:
    body: str
    evidence_story_ids: list[int] = field(default_factory=list)


@dataclass
class ApplicationAnswerResult:
    answer: str
    confidence: str  # verified | estimated | needs_review
    evidence_story_ids: list[int] = field(default_factory=list)


class AIProvider(ABC):
    """Every model call in this app goes through one of these methods.
    No other module should call an LLM API directly."""

    @abstractmethod
    def recommend_job(
        self,
        job: dict,
        profile: dict,
        candidate_context: str,
        stories: list[dict],
        deterministic_flags: list[str],
    ) -> tuple[RecommendationResult, ModelCallMetadata]:
        """`job` passed deterministic rules already (see scoring/rules.py) —
        this method only has to answer judgment questions: should Jais spend
        time on this, strongest selling points, biggest gaps, positioning,
        is it a worthwhile stretch. `deterministic_flags` are non-fatal notes
        the rule engine raised (e.g. location mismatch) for the model to
        weigh, not hard disqualifiers (those short-circuit before this is
        ever called). `candidate_context` is the narrative source (LinkedIn +
        resume today, see scoring/context.py) — `profile` is only the
        structured search-preference fields."""

    @abstractmethod
    def extract_candidate_profile(
        self, linkedin_text: str, resume_text: str
    ) -> tuple[ProfileExtractionResult, ModelCallMetadata]:
        """Best-effort structured extraction from pasted LinkedIn/resume
        text. Always presented to the user for review before saving —
        never written to candidate_profile directly."""

    @abstractmethod
    def generate_resume_summary(
        self, job: dict, candidate_context: str, stories: list[dict]
    ) -> tuple[ResumeSummaryResult, ModelCallMetadata]: ...

    @abstractmethod
    def tailor_resume(
        self, job: dict, base_resume_text: str, stories: list[dict]
    ) -> ResumeTailoringResult:
        """Deferred beyond the MVP — needs a base resume broken into
        sections/bullets to propose diffs against, which in turn needs a
        branded DOCX template (M8). generate_resume_summary covers the
        weekend end-to-end path in the meantime."""

    @abstractmethod
    def generate_cover_letter(
        self, job: dict, candidate_context: str, stories: list[dict]
    ) -> tuple[CoverLetterResult, ModelCallMetadata]: ...

    @abstractmethod
    def answer_application_question(
        self, job: dict, question: str, candidate_context: str, stories: list[dict]
    ) -> ApplicationAnswerResult: ...
