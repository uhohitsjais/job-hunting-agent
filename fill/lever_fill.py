from __future__ import annotations

from playwright.sync_api import sync_playwright

# Same rule as fill/greenhouse_fill.py: never auto-filled, by design.
ALWAYS_MANUAL = [
    "Resume (always manual — no branded DOCX template built yet)",
    "Work authorization / sponsorship questions (always manual, by design)",
    "Demographic / EEOC questions — gender, race, veteran, disability, etc. (always manual, by design)",
]


def fill_lever_application(
    job_url: str, profile: dict, application: dict | None, headless: bool = False
) -> dict:
    """Lever job posting pages have no form on them — the application lives
    at <job_url>/apply. Fields there use stable `name` attributes (verified
    across multiple Rover postings): name, email, phone, urls[LinkedIn].
    Never clicks Submit."""
    filled: list[str] = []
    skipped: list[str] = list(ALWAYS_MANUAL)

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=headless)
    page = browser.new_page()

    apply_url = job_url.rstrip("/")
    if not apply_url.endswith("/apply"):
        apply_url += "/apply"
    page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1000)

    def try_fill(name_attr: str, value, label: str):
        if not value:
            skipped.append(f"{label} (no value in your candidate profile)")
            return
        try:
            locator = page.locator(f'[name="{name_attr}"]')
            if locator.count() == 0:
                skipped.append(f"{label} (field not present on this form)")
                return
            locator.first.fill(str(value))
            filled.append(label)
        except Exception as exc:
            skipped.append(f"{label} (error: {exc})")

    full_name = f"{profile.get('first_name') or ''} {profile.get('last_name') or ''}".strip()
    try_fill("name", full_name, "Full name")
    try_fill("email", profile.get("email"), "Email")
    try_fill("phone", profile.get("phone"), "Phone")
    try_fill("urls[LinkedIn]", profile.get("linkedin_url"), "LinkedIn URL")

    # Lever's standard form has no cover letter field at all (confirmed on
    # Rover) — not every company enables one, so this is a soft note, not
    # a hard fact for every Lever posting.
    skipped.append(
        "Cover letter (no cover letter field found on this form — attach manually if the posting calls for one)"
    )

    return {"filled": filled, "skipped": skipped, "browser": browser, "playwright": playwright, "page": page}
