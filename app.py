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
    serve_parser = subparsers.add_parser("serve", help="Run the local web dashboard")
    serve_parser.add_argument("--port", type=int, default=None)
    serve_parser.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
