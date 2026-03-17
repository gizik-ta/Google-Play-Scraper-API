from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import json
import os

app = Flask(__name__)

JSON_FILE = "data.json"

@app.route("/")
def get_description():
    package_name = request.args.get("id", "com.kursx.smartbook")
    lang = request.args.get("hl", "ru").lower()

    with open(JSON_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)
        if package_name in data[lang]:
            return data[lang][package_name]
        
    url = "https://play.google.com/store/apps/details"

    params = {
        "id": package_name,
        "hl": lang
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, params=params, headers=headers)
    if response.status_code != 200:
        return jsonify({"error": "Ошибка запроса"})

    soup = BeautifulSoup(response.text, "html.parser")
    lines = soup.get_text(separator="\n").split("\n")

    description = []
    in_progress = False

    markers = {
        "ru": {
            "start": ["Описание"],
            "stop": ["Что нового", "Обновлено", "Последнее обновление"]
        },
        "en": {
            "start": ["About this app"],
            "stop": ["What's new", "Updated on"]
        }
    }

    if lang in markers:
        start_markers = markers[lang]["start"]
        stop_markers = markers[lang]["stop"]
    else:
        start_markers = markers["ru"]["start"]
        stop_markers = markers["ru"]["stop"]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if any(line.startswith(marker) for marker in start_markers):
            in_progress = True
            continue

        if any(marker in line for marker in stop_markers):
            break

        if "arrow_forward" in line:
            continue

        if in_progress:
            description.append(line)

    description_result = " ".join(description).strip()
    if not description_result:
        description_result = "Описание не найдено"

    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    data[package_name] = {
        "description": description_result,
        "lang": lang
    }

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return jsonify({
        "package": package_name,
        "lang": lang,
        "description": description_result
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)