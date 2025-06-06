# serper_tokens.py
from playwright.async_api import async_playwright

async def get_serper_credits(email: str, password: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("https://serper.dev/login")
        await page.fill("input[name=email]", email)
        await page.fill("input[name=password]", password)
        await page.click("button[type=submit]")

        await page.wait_for_url("**/dashboard")
        await page.wait_for_load_state("networkidle")

        credit_text_element = page.locator("text=Credits last 30 days").first
        credits_h2 = credit_text_element.locator("xpath=following-sibling::h2").first
        credits_value = await credits_h2.text_content()

        await browser.close()
        return credits_value.strip()
