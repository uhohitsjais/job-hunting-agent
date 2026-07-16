from __future__ import annotations

from playwright.sync_api import sync_playwright

# Fields that are always left for manual completion, by design. Never
# auto-filled: résumé (needs an actual file — no branded DOCX exists yet),
# and anything requiring legal/personal judgment (work authorization,
# sponsorship, demographic/EEOC questions). See prompts/application_answers.md
# for the same rule applied to generated text answers.
ALWAYS_MANUAL = [
    "Resume (always manual — no branded DOCX template built yet)",
    "Work authorization / sponsorship questions (always manual, by design)",
    "Demographic / EEOC questions — gender, race, veteran, disability, etc. (always manual, by design)",
]


def fill_greenhouse_application(
    job_url: str, profile: dict, application: dict | None, headless: bool = False
) -> dict:
    """Launches a real browser on the job's Greenhouse apply page and fills
    what it safely can. Never clicks Submit. Returns the live
    browser/page/playwright handles so the caller decides when to close."""
    filled: list[str] = []
    skipped: list[str] = list(ALWAYS_MANUAL)

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=headless)
    page = browser.new_page()
    page.goto(job_url, wait_until="networkidle", timeout=30000)

    def try_fill(selector: str, value, label: str):
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

    try_fill("#first_name", profile.get("first_name"), "First name")
    try_fill("#last_name", profile.get("last_name"), "Last name")
    try_fill("#email", profile.get("email"), "Email")
    try_fill("#phone", profile.get("phone"), "Phone")

    # LinkedIn Profile is a per-posting custom question with no stable ID —
    # match by its exact label text instead.
    if profile.get("linkedin_url"):
        try:
            label = page.locator("label", has_text="LinkedIn Profile")
            if label.count() > 0:
                input_id = label.first.get_attribute("for")
                if input_id and page.locator(f"#{input_id}").count() > 0:
                    page.locator(f"#{input_id}").first.fill(profile["linkedin_url"])
                    filled.append("LinkedIn Profile")
                else:
                    skipped.append("LinkedIn Profile (couldn't resolve the field id)")
            else:
                skipped.append("LinkedIn Profile (question not on this form)")
        except Exception as exc:
            skipped.append(f"LinkedIn Profile (error: {exc})")
    else:
        skipped.append("LinkedIn Profile (no value in your candidate profile)")

    # Cover letter: Greenhouse's upload widget offers an "Enter manually"
    # text option next to the file dropzone — try that before giving up.
    cover_letter_body = (application or {}).get("cover_letter_body")
    if cover_letter_body:
        try:
            cover_field = page.locator("#cover_letter")
            if cover_field.count() > 0:
                container = cover_field.locator(
                    "xpath=ancestor::div[contains(@class,'field')][1]"
                )
                enter_manually = container.locator("text=Enter manually")
                if enter_manually.count() > 0:
                    enter_manually.first.click()
                    textarea = container.locator("textarea")
                    if textarea.count() > 0:
                        textarea.first.fill(cover_letter_body)
                        filled.append("Cover letter (pasted as text)")
                    else:
                        skipped.append("Cover letter ('Enter manually' didn't reveal a text box — attach manually)")
                else:
                    skipped.append("Cover letter (no 'Enter manually' option on this form — attach the file manually)")
            else:
                skipped.append("Cover letter (this form doesn't have a cover letter field)")
        except Exception as exc:
            skipped.append(f"Cover letter (error: {exc})")
    else:
        skipped.append("Cover letter (no draft generated yet — use the job detail page)")

    return {"filled": filled, "skipped": skipped, "browser": browser, "playwright": playwright, "page": page}
