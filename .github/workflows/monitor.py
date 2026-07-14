import html
import os
import sys
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


CROUS_URL = (
    "https://trouverunlogement.lescrous.fr/tools/47/search"
    "?bounds=2.4130316_48.6485333_2.4705092_48.6109217"
    "&locationName=%C3%89vry+%2891000%29"
)

RESIDENCES = [
    "Le Dragueur",
    "Flora Tristan",
    "Les Aunettes",
    "Marguerite Yourcenar",
]

REQUEST_TIMEOUT = 30


def normalize_text(value: str) -> str:
    """
    Uniformise les accents, les majuscules et les espaces afin de rendre
    la recherche plus fiable.
    """
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    return " ".join(value.casefold().split())


def send_telegram(message: str) -> None:
    """Envoie une notification Telegram."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        raise RuntimeError(
            "Les secrets TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID "
            "doivent être configurés dans GitHub."
        )

    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    response = requests.post(
        telegram_url,
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()


def download_page() -> str:
    """Télécharge la page de recherche CROUS."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0 Safari/537.36"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }

    response = requests.get(
        CROUS_URL,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    return response.text


def main() -> None:
    checked_at = datetime.now(ZoneInfo("Europe/Paris")).strftime(
        "%d/%m/%Y à %H:%M:%S"
    )

    try:
        page_html = download_page()
    except requests.RequestException as error:
        print(f"Erreur lors du téléchargement de la page : {error}")
        sys.exit(1)

    soup = BeautifulSoup(page_html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    normalized_page = normalize_text(page_text)

    detected_residences = [
        residence
        for residence in RESIDENCES
        if normalize_text(residence) in normalized_page
    ]

    print(f"Vérification effectuée le {checked_at}.")
    print(f"Nombre de caractères analysés : {len(page_text)}")

    if not detected_residences:
        print("Aucune des quatre résidences n’a été détectée.")
        return

    residences_text = "\n".join(
        f"• <b>{html.escape(residence)}</b>"
        for residence in detected_residences
    )

    message = (
        "🚨 <b>Logement CROUS potentiellement disponible</b>\n\n"
        "Une résidence recherchée apparaît sur la page d’Évry :\n"
        f"{residences_text}\n\n"
        f"Vérification : {checked_at}\n\n"
        f'<a href="{html.escape(CROUS_URL)}">'
        "Ouvrir immédiatement la recherche CROUS</a>\n\n"
        "⚠️ La présence du nom sur la page ne garantit pas que le logement "
        "sera encore disponible au moment de la demande."
    )

    send_telegram(message)
    print("Notification Telegram envoyée.")


if __name__ == "__main__":
    main()
