from __future__ import annotations

from playwright.sync_api import sync_playwright

# Same rule as fill/greenhouse_fill.py: never auto-filled, by design.
ALWAYS_MANUAL = [
    "Resume (always manual — no branded DOCX template built yet)",
    "Work authorization / sponsorship questions (always manual, by design)",
    "Demographic / EEOC questions — gender, race, veteran, disability, etc. (always manual, by design)",
]


def fill_ashby_application(
    job_url: str, profile: dict, application: dict | None, headless: bool = False
) -> dict:
    """Ashby job posting pages have no form on them — the application lives
    at <job_url>/application. Confirmed stable across companies (BetterUp,
    Thumbtack): _systemfield_name, _systemfield_email are fixed IDs; phone
    and LinkedIn are per-posting UUID field IDs, matched by label text
    instead. Never clicks Submit."""
    filled: list[str] = []
    skipped: list[str] = list(ALWAYS_MANUAL)

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=headless)
    page = browser.new_page()

    application_url = job_url.rstrip("/")
    if not application_url.endswith("/application"):
        application_url += "/application"
    page.goto(application_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)  # Ashby's form renders client-side after load

    def try_fill_selector(selector: str, value, label: str):
        if not value:
            skipped.append(f"{label} (no value in your candidate profile)")
            return
        try:
            locator = page.locator(selector)
            if locator.count() == 0:
                skipped.append(f"{label} (field not present on this form)")
                return
            locator.first.fill(str(value))
            filled.append(label)
        except Exception as exc:
            skipped.append(f"{label} (error: {exc})")

    def try_fill_by_label(text: str, value, label: str):
        if not value:
            skipped.append(f"{label} (no value in your candidate profile)")
            return
        try:
            label_loc = page.locator("label").filter(has_text=text)
            if label_loc.count() == 0:
                skipped.append(f"{label} (question not on this form)")
                return
            input_id = label_loc.first.get_attribute("for")
            # Ashby's per-posting field IDs are UUIDs that often start with
            # a digit, which is invalid as a raw CSS #id selector — use an
            # attribute selector instead, which has no such restriction.
            field = page.locator(f'[id="{input_id}"]') if input_id else None
            if field is not None and field.count() > 0:
                field.first.fill(str(value))
                filled.append(label)
            else:
                skipped.append(f"{label} (couldn't resolve the field id)")
        except Exception as exc:
            skipped.append(f"{label} (error: {exc})")

    full_name = f"{profile.get('first_name') or ''} {profile.get('last_name') or ''}".strip()
    try_fill_selector("#_systemfield_name", full_name, "Full name")
    try_fill_selector("#_systemfield_email", profile.get("email"), "Email")
    try_fill_by_label("Phone", profile.get("phone"), "Phone")
    try_fill_by_label("LinkedIn", profile.get("linkedin_url"), "LinkedIn")

    # Ashby's cover letter question is a file-upload widget with no
    # "enter manually" text alternative (unlike Greenhouse) — always manual.
    skipped.append(
        "Cover letter (Ashby only accepts a file upload here, no text option — attach manually)"
    )

    return {"filled": filled, "skipped": skipped, "browser": browser, "playwright": playwright, "page": page}
