from playwright.sync_api import sync_playwright
import time

def get_serper_credits(email: str, password: str) -> str:
    """
    Récupère le nombre de crédits restants sur Serper.dev.
    """
    # Initialiser Playwright et lancer le navigateur
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Aller à la page de login
        page.goto("https://serper.dev/login")
        page.fill("input[name=email]", email)
        page.fill("input[name=password]", password)
        page.click("button[type=submit]")

        # Attendre d’être redirigé vers le dashboard
        page.wait_for_url("**/dashboard")
        # Attendre que la page soit complètement chargée
        page.wait_for_load_state("networkidle")

        # Localiser le bloc de crédits en s'appuyant sur le texte "Credits last 30 days"
        credit_text_element = page.locator("text=Credits last 30 days").first
        credits_h2 = credit_text_element.locator("xpath=following-sibling::h2").first
        credits_value = credits_h2.text_content()
        
        browser.close()
        
        return credits_value
