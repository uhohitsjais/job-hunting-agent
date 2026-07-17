import json

from flask import Flask, redirect, render_template, request, url_for

from config import settings
from db.db import (
    DECISION_GROUPS,
    fetch_approved_candidate_stories,
    fetch_job_with_latest_evaluation,
    fetch_jobs_with_latest_evaluation,
    get_application,
    get_candidate_profile,
    get_connection,
    get_pipeline_stats,
    group_jobs_by_decision,
    insert_model_run,
    update_candidate_profile,
    upsert_application,
)
from scoring.context import build_candidate_context
from web.presentation import build_recommendation_view, compute_confidence

ARRAY_FIELDS = [
    "target_titles",
    "excluded_titles",
    "preferred_industries",
    "excluded_industries",
    "preferred_locations",
    "strongest_skills",
    "known_gaps",
    "preferred_company_size",
]
INT_FIELDS = ["min_salary", "preferred_salary", "years_experience"]
TEXT_FIELDS = [
    "remote_preference",
    "stretch_willingness",
    "first_name",
    "last_name",
    "email",
    "phone",
    "linkedin_url",
]

GROUP_LABELS = {
    "priority": "Priority",
    "apply": "Apply",
    "stretch": "Stretch",
    "archive": "Archive",
    "unscored": "Not yet scored",
    "filtered_title": "Filtered (Title)",
}


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def dashboard():
        jobs = fetch_jobs_with_latest_evaluation(settings.DATABASE_PATH)
        for job in jobs:
            job["confidence"] = compute_confidence(job) if job.get("decision") else None
        grouped = group_jobs_by_decision(jobs)
        sections = [
            (GROUP_LABELS[key], grouped[key]) for key in DECISION_GROUPS if grouped[key]
        ]
        stats = get_pipeline_stats(settings.DATABASE_PATH)
        just_ran = request.args.get("filter_ran") == "1"
        return render_template(
            "dashboard.html",
            sections=sections,
            has_jobs=bool(jobs),
            stats=stats,
            just_ran_filter=just_ran,
        )

    @app.post("/filter")
    def run_filter():
        from scoring.evaluate import apply_title_filter

        apply_title_filter()
        return redirect(url_for("dashboard", filter_ran="1"))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/jobs/<int:job_id>")
    def job_detail(job_id):
        job = fetch_job_with_latest_evaluation(settings.DATABASE_PATH, job_id)
        if job is None:
            return "Job not found", 404
        application = get_application(settings.DATABASE_PATH, job_id)
        rec = build_recommendation_view(job)
        return render_template("job_detail.html", job=job, application=application, rec=rec)

    @app.post("/jobs/<int:job_id>/materials")
    def generate_materials(job_id):
        job = fetch_job_with_latest_evaluation(settings.DATABASE_PATH, job_id)
        if job is None:
            return "Job not found", 404

        from providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        profile = get_candidate_profile(settings.DATABASE_PATH)
        stories = fetch_approved_candidate_stories(settings.DATABASE_PATH)
        candidate_context = build_candidate_context(profile)

        conn = get_connection(settings.DATABASE_PATH)
        try:
            summary_result, summary_meta = provider.generate_resume_summary(
                job, candidate_context, stories
            )
            insert_model_run(
                conn,
                task_type="generate_resume_summary",
                job_id=job_id,
                prompt_file=summary_meta.prompt_file,
                prompt_version=summary_meta.prompt_version,
                model_name=summary_meta.model_name,
                input_context=json.dumps(summary_meta.input_context),
                raw_output=summary_meta.raw_output,
                parsed_output=json.dumps({"summary": summary_result.summary}),
                success=1,
                error_message=None,
            )

            letter_result, letter_meta = provider.generate_cover_letter(
                job, candidate_context, stories
            )
            insert_model_run(
                conn,
                task_type="generate_cover_letter",
                job_id=job_id,
                prompt_file=letter_meta.prompt_file,
                prompt_version=letter_meta.prompt_version,
                model_name=letter_meta.model_name,
                input_context=json.dumps(letter_meta.input_context),
                raw_output=letter_meta.raw_output,
                parsed_output=json.dumps({"body": letter_result.body}),
                success=1,
                error_message=None,
            )
            conn.commit()
        except Exception as exc:
            insert_model_run(
                conn,
                task_type="generate_materials",
                job_id=job_id,
                prompt_file="resume_summary.md/cover_letter.md",
                prompt_version="unknown",
                model_name=getattr(provider, "model_name", "unknown"),
                input_context=None,
                raw_output=None,
                parsed_output=None,
                success=0,
                error_message=str(exc),
            )
            conn.commit()
            return redirect(url_for("job_detail", job_id=job_id, error="materials_failed"))
        finally:
            conn.close()

        upsert_application(
            settings.DATABASE_PATH,
            job_id,
            resume_summary=summary_result.summary,
            cover_letter_body=letter_result.body,
            status="draft",
        )
        return redirect(url_for("job_detail", job_id=job_id))

    @app.post("/jobs/<int:job_id>/materials/save")
    def save_materials(job_id):
        upsert_application(
            settings.DATABASE_PATH,
            job_id,
            resume_summary=request.form.get("resume_summary", ""),
            cover_letter_body=request.form.get("cover_letter_body", ""),
        )
        return redirect(url_for("job_detail", job_id=job_id))

    @app.get("/profile")
    def profile_form():
        profile = get_candidate_profile(settings.DATABASE_PATH)
        return render_template(
            "profile.html", profile=profile, saved=request.args.get("saved"), imported=False
        )

    @app.post("/profile")
    def profile_save():
        values = {}
        for field in ARRAY_FIELDS:
            raw = request.form.get(field, "")
            values[field] = [item.strip() for item in raw.split(",") if item.strip()]
        for field in INT_FIELDS:
            raw = request.form.get(field, "").strip()
            values[field] = int(raw) if raw else None
        for field in TEXT_FIELDS:
            raw = request.form.get(field, "").strip()
            values[field] = raw or None
        update_candidate_profile(settings.DATABASE_PATH, values)
        return redirect(url_for("profile_form", saved="1"))

    @app.get("/profile/import")
    def import_form():
        return render_template("import.html")

    @app.post("/profile/import")
    def import_extract():
        linkedin_text = request.form.get("linkedin_text", "").strip()
        resume_text = request.form.get("resume_text", "").strip()

        update_candidate_profile(
            settings.DATABASE_PATH,
            {"linkedin_text": linkedin_text or None, "resume_text": resume_text or None},
        )

        from providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        conn = get_connection(settings.DATABASE_PATH)
        try:
            result, metadata = provider.extract_candidate_profile(linkedin_text, resume_text)
            insert_model_run(
                conn,
                task_type="extract_candidate_profile",
                job_id=None,
                prompt_file=metadata.prompt_file,
                prompt_version=metadata.prompt_version,
                model_name=metadata.model_name,
                input_context=json.dumps(metadata.input_context),
                raw_output=metadata.raw_output,
                parsed_output=json.dumps(result.__dict__),
                success=1,
                error_message=None,
            )
            conn.commit()
        except Exception as exc:
            insert_model_run(
                conn,
                task_type="extract_candidate_profile",
                job_id=None,
                prompt_file="profile_extraction.md",
                prompt_version="unknown",
                model_name=getattr(provider, "model_name", "unknown"),
                input_context=None,
                raw_output=None,
                parsed_output=None,
                success=0,
                error_message=str(exc),
            )
            conn.commit()
            return render_template("import.html", error=str(exc))
        finally:
            conn.close()

        # Merge: extracted values as a preview overlay on top of the persisted
        # profile. Nothing structured is saved until the user hits Save below.
        profile = get_candidate_profile(settings.DATABASE_PATH)
        extracted = result.__dict__
        for key, value in extracted.items():
            if value:
                profile[key] = value
        return render_template("profile.html", profile=profile, saved=None, imported=True)

    return app
