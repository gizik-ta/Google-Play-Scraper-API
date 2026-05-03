from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

import requests
import sqlite3


app = Flask(__name__)

DATABASE_NAME = "database.db"

PLAY_STORE_URL = "https://play.google.com/store/apps/details"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MARKERS = {
    "ru": {
        "start": ["Описание"],
        "stop": ["Что нового", "Обновлено", "Последнее обновление"]
    },
    "en": {
        "start": ["About this app"],
        "stop": ["What's new", "Updated on"]
    }
}


def init_database():
    with sqlite3.connect(DATABASE_NAME) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS descriptions (
                package_name TEXT NOT NULL,
                language TEXT NOT NULL,
                description TEXT NOT NULL,
                PRIMARY KEY (package_name, language)
            )
        """)


def get_cached_description(package_name: str, language: str):
    with sqlite3.connect(DATABASE_NAME) as connection:
        cursor = connection.execute("""
            SELECT description
            FROM descriptions
            WHERE package_name = ? AND language = ?
        """, (package_name, language))

        row = cursor.fetchone()

    return row[0] if row else None


def save_description(package_name: str, language: str, description: str):
    with sqlite3.connect(DATABASE_NAME) as connection:
        connection.execute("""
            INSERT OR REPLACE INTO descriptions (
                package_name,
                language,
                description
            )
            VALUES (?, ?, ?)
        """, (package_name, language, description))


def fetch_page(package_name: str, language: str):
    response = requests.get(
        PLAY_STORE_URL,
        params={
            "id": package_name,
            "hl": language
        },
        headers=HEADERS,
        timeout=15
    )

    response.raise_for_status()

    return response.text


def extract_description(html: str, language: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    lines = soup.get_text(separator="\n").split("\n")

    language_markers = MARKERS.get(language, MARKERS["en"])

    start_markers = language_markers["start"]
    stop_markers = language_markers["stop"]

    description_lines = []

    is_description_started = False

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if any(line.startswith(marker) for marker in start_markers):
            is_description_started = True
            continue

        if any(marker in line for marker in stop_markers):
            break

        if "arrow_forward" in line:
            continue

        if is_description_started:
            description_lines.append(line)

    description = " ".join(description_lines).strip()

    return description or "Description not found"


def get_description(package_name: str, language: str):
    cached_description = get_cached_description(package_name, language)

    if cached_description:
        return {
            "description": cached_description,
            "cached": True
        }

    try:
        html = fetch_page(package_name, language)

        description = extract_description(html, language)

        save_description(package_name, language, description)

        return {
            "description": description,
            "cached": False
        }

    except requests.RequestException as error:
        return {
            "error": str(error)
        }


@app.route("/")
def index():
    package_ids = request.args.get("id")
    language = request.args.get("hl")

    if not package_ids:
        return jsonify({
            "error": "Missing query parameter: id"
        }), 400

    if not language:
        return jsonify({
            "error": "Missing query parameter: hl"
        }), 400

    packages = [
        package.strip()
        for package in package_ids.split(",")
        if package.strip()
    ]

    result = {
        package: get_description(package, language.lower())
        for package in packages
    }

    return jsonify({
        "result": result
    })


if __name__ == "__main__":
    init_database()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )