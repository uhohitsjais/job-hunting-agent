import argparse
import sys

from config import settings
from db.db import count_rows, init_db


def cmd_init(_args):
    init_db(settings.DATABASE_PATH)
    print(f"Initialized database at {settings.DATABASE_PATH}")


def cmd_status(_args):
    tables = [
        "jobs",
        "candidate_stories",
        "candidate_profile",
        "positioning_profiles",
        "model_runs",
        "job_evaluations",
        "applications",
        "application_answers",
    ]
    for table in tables:
        print(f"{table}: {count_rows(settings.DATABASE_PATH, table)}")


def cmd_fetch(_args):
    from jobs.fetch import fetch_all

    total = fetch_all()
    print(f"Fetched/updated {total} job postings")


def cmd_score(args):
    from scoring.evaluate import evaluate_all

    counts = evaluate_all(rescore=args.rescore)
    if not counts:
        print("No jobs to score (nothing with status='sourced' — try --rescore).")
        return
    for decision, n in sorted(counts.items()):
        print(f"{decision}: {n}")
    if counts.get("error"):
        print(
            "\nSome jobs failed to score — check model_runs.error_message for details "
            "(e.g. missing OPENAI_API_KEY/OPENAI_MODEL). They stayed 'sourced' and will "
            "retry on the next `python app.py score` run."
        )


def cmd_filter(_args):
    from db.db import get_pipeline_stats
    from scoring.evaluate import apply_title_filter

    apply_title_filter()
    stats = get_pipeline_stats(settings.DATABASE_PATH)
    print(f"Total sourced: {stats['total']}")
    print(f"Filtered: {stats['filtered']}")
    print(f"Eligible for scoring: {stats['eligible']}")


def cmd_career_brain(_args):
    from materials.career_brain import load_career_brain_context

    _, paths = load_career_brain_context()
    if not paths:
        print("No Career Brain documents found under career_brain/. See career_brain/README.md.")
        return
    print(f"{len(paths)} document(s) would be loaded at generation time:")
    for path in paths:
        print(" -", path)


def cmd_fill(args):
    from db.db import fetch_job_with_latest_evaluation, get_application, get_candidate_profile
    from fill.greenhouse_fill import fill_greenhouse_application

    job = fetch_job_with_latest_evaluation(settings.DATABASE_PATH, args.job_id)
    if job is None:
        print(f"No job with id {args.job_id}")
        return
    if job["source"] != "greenhouse":
        print(f"Only Greenhouse fill is supported right now (this job is on {job['source']}).")
        return

    profile = get_candidate_profile(settings.DATABASE_PATH)
    application = get_application(settings.DATABASE_PATH, args.job_id)

    print(f"Opening {job['url']} ...")
    result = fill_greenhouse_application(job["url"], profile, application, headless=False)

    print("\nFilled:")
    for item in result["filled"] or ["(nothing — check your candidate profile has contact info)"]:
        print(" -", item)
    print("\nLeft for you to complete manually:")
    for item in result["skipped"]:
        print(" -", item)

    input("\nBrowser is open for review. Press Enter here to close it (this will NOT submit anything)...")
    result["browser"].close()
    result["playwright"].stop()


def cmd_serve(args):
    from web.server import create_app

    app = create_app()
    app.run(port=args.port or settings.FLASK_PORT, debug=True)


def main():
    parser = argparse.ArgumentParser(prog="app.py", description="Job Hunting Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create/update the SQLite database").set_defaults(
        func=cmd_init
    )
    subparsers.add_parser("status", help="Print row counts for each table").set_defaults(
        func=cmd_status
    )
    subparsers.add_parser(
        "fetch", help="Fetch job postings from all configured companies"
    ).set_defaults(func=cmd_fetch)
    score_parser = subparsers.add_parser(
        "score", help="Evaluate sourced jobs against your candidate profile"
    )
    score_parser.add_argument(
        "--rescore", action="store_true", help="Re-evaluate all jobs, not just unscored ones"
    )
    score_parser.set_defaults(func=cmd_score)
    subparsers.add_parser(
        "filter", help="Preview/apply the deterministic title filter without scoring anything"
    ).set_defaults(func=cmd_filter)
    subparsers.add_parser(
        "career-brain", help="List which career_brain/ documents would be loaded at generation time"
    ).set_defaults(func=cmd_career_brain)
    fill_parser = subparsers.add_parser(
        "fill", help="Open a Greenhouse job's apply page and fill what it safely can"
    )
    fill_parser.add_argument("job_id", type=int)
    fill_parser.set_defaults(func=cmd_fill)
    serve_parser = subparsers.add_parser("serve", help="Run the local web dashboard")
    serve_parser.add_argument("--port", type=int, default=None)
    serve_parser.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
