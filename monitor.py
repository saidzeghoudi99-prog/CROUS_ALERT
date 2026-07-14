import html
import os
import sys
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


CROUS_URL = (
    "https://trouverunlogement.lescrous.fr/tools/47/search"
    "?bounds=2.4130316_48.6485333_2.4705092_48.6109217"
    "&locationName=%C3%89vry+%2891000%29"
)

RESIDENCES = [
    "logement",
    "Le Dragueur",
    "Flora Tristan",
    "Les Aunettes",
    "Marguerite Yourcenar",
]



def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    return " ".join(text.casefold().split())


def send_telegram(message: str) -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        raise RuntimeError(
            "Les secrets TELEGRAM_BOT_TOKEN et "
            "TELEGRAM_CHAT_ID sont absents."
        )

    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    response.raise_for_status()


def get_page_text() -> str:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        page = browser.new_page(
            locale="fr-FR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/149.0 Safari/537.36"
            ),
        )

        try:
            page.goto(
                CROUS_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            page.wait_for_timeout(10_000)

            page_text = page.locator("body").inner_text()

        except PlaywrightTimeoutError:
            page_text = page.locator("body").inner_text()

        finally:
            browser.close()

    return page_text


def main() -> None:
    checked_at = datetime.now(
        ZoneInfo("Europe/Paris")
    ).strftime("%d/%m/%Y à %H:%M:%S")

    try:
        page_text = get_page_text()
    except Exception as error:
        print(f"Erreur pendant l'ouverture de la page : {error}")
        sys.exit(1)

    normalized_page = normalize_text(page_text)

    detected_residences = [
        residence
        for residence in RESIDENCES
        if normalize_text(residence) in normalized_page
    ]

    print(f"Vérification effectuée le {checked_at}")
    print(f"Nombre de caractères analysés : {len(page_text)}")

    if not detected_residences:
        print("Aucune résidence recherchée détectée.")
        return

    residences_message = "\n".join(
        f"• <b>{html.escape(residence)}</b>"
        for residence in detected_residences
    )

    message = (
        "🚨 <b>Alerte logement CROUS Évry</b>\n\n"
        "Une résidence recherchée apparaît sur la page :\n\n"
        f"{residences_message}\n\n"
        f"Détection : {checked_at}\n\n"
        f'<a href="{html.escape(CROUS_URL)}">'
        "Ouvrir la page CROUS immédiatement</a>\n\n"
        "La détection ne garantit pas que la chambre sera encore "
        "disponible au moment de la demande."
    )

    send_telegram(message)
    print("Notification Telegram envoyée.")


if __name__ == "__main__":
    main()
