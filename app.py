import os
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from anthropic import Anthropic
import carquery

load_dotenv()

app = Flask(__name__)

SYSTEM_PROMPT = """\
PROMPT SYSTEMOWY – AGENT PORÓWNYWARKI SAMOCHODÓW

Jesteś inteligentnym agentem AI pełniącym rolę eksperta motoryzacyjnego oraz doradcy zakupowego samochodów.
Twoim celem jest pomoc użytkownikowi w wyborze najlepszego samochodu na podstawie jego indywidualnych potrzeb, preferencji i ograniczeń.

Masz dostęp do narzędzi pozwalających wyszukiwać i porównywać samochody z bazy CarQuery API.
Uzupełniaj dane z API własną wiedzą motoryzacyjną (ceny orientacyjne, niezawodność, koszty eksploatacji itp.).

Zasady:
- Odpowiadaj po polsku.
- Jeśli użytkownik nie poda kluczowych informacji, zadaj 1–2 pytania doprecyzowujące.
- Przedstawiaj dane w czytelnej formie (tabele markdown, listy).
- Uzasadniaj rekomendacje.
- Jeśli nie masz danych – poinformuj jasno, nie wymyślaj specyfikacji.
- Bądź rzeczowy, profesjonalny i przyjazny.
"""

TOOLS = [
    {
        "name": "search_cars",
        "description": "Wyszukaj samochody w bazie CarQuery wg kryteriów. Zwraca listę wersji (trims) z danymi technicznymi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "make": {
                    "type": "string",
                    "description": "Marka samochodu (np. 'Toyota', 'BMW'). Wymagane."
                },
                "model": {
                    "type": "string",
                    "description": "Model samochodu (np. 'Corolla', 'X5'). Opcjonalne."
                },
                "year": {
                    "type": "string",
                    "description": "Rok produkcji (np. '2020'). Opcjonalne."
                },
                "body": {
                    "type": "string",
                    "description": "Typ nadwozia (np. 'SUV', 'Sedan', 'Hatchback'). Opcjonalne."
                },
                "min_power": {
                    "type": "string",
                    "description": "Minimalna moc w KM. Opcjonalne."
                },
                "max_power": {
                    "type": "string",
                    "description": "Maksymalna moc w KM. Opcjonalne."
                },
                "fuel_type": {
                    "type": "string",
                    "description": "Rodzaj paliwa (np. 'Gasoline', 'Diesel', 'Electric'). Opcjonalne."
                },
                "drive": {
                    "type": "string",
                    "description": "Typ napędu (np. 'Front', 'Rear', 'All'). Opcjonalne."
                }
            },
            "required": ["make"]
        }
    },
    {
        "name": "get_car_details",
        "description": "Pobierz szczegółowe dane techniczne konkretnego modelu na podstawie jego ID z CarQuery.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "ID modelu z CarQuery (pole model_id z wyników wyszukiwania)."
                }
            },
            "required": ["model_id"]
        }
    },
    {
        "name": "compare_cars",
        "description": "Porównaj 2 lub więcej samochodów. Podaj marki i modele do porównania. Opcjonalnie podaj rok.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cars": {
                    "type": "array",
                    "description": "Lista samochodów do porównania. Każdy element to obiekt z polami make, model, year (opcjonalne).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "make": {"type": "string", "description": "Marka"},
                            "model": {"type": "string", "description": "Model"},
                            "year": {"type": "string", "description": "Rok (opcjonalnie)"}
                        },
                        "required": ["make", "model"]
                    }
                }
            },
            "required": ["cars"]
        }
    },
    {
        "name": "get_makes",
        "description": "Pobierz listę wszystkich marek samochodów dostępnych w bazie, opcjonalnie filtrując po roku.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "string",
                    "description": "Rok produkcji do filtrowania (opcjonalne)."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_models",
        "description": "Pobierz listę modeli dla danej marki.",
        "input_schema": {
            "type": "object",
            "properties": {
                "make": {
                    "type": "string",
                    "description": "Marka samochodu."
                },
                "year": {
                    "type": "string",
                    "description": "Rok produkcji (opcjonalne)."
                },
                "body": {
                    "type": "string",
                    "description": "Typ nadwozia (opcjonalne)."
                }
            },
            "required": ["make"]
        }
    }
]


def execute_tool(name, input_data):
    try:
        if name == "search_cars":
            result = carquery.search_cars(
                make=input_data.get("make"),
                model=input_data.get("model"),
                year=input_data.get("year"),
                body=input_data.get("body"),
                min_power=input_data.get("min_power"),
                max_power=input_data.get("max_power"),
                fuel_type=input_data.get("fuel_type"),
                drive=input_data.get("drive"),
            )
            if isinstance(result, list) and len(result) > 15:
                result = result[:15]
                result.append({"_note": "Wyniki ograniczone do 15. Zawęź kryteria wyszukiwania."})
            return json.dumps(result, ensure_ascii=False)

        elif name == "get_car_details":
            result = carquery.get_model_detail(input_data["model_id"])
            return json.dumps(result, ensure_ascii=False) if result else '{"error": "Nie znaleziono modelu."}'

        elif name == "compare_cars":
            cars = input_data["cars"]
            all_specs = []
            for car in cars:
                trims = carquery.get_trims(
                    make=car["make"],
                    model=car["model"],
                    year=car.get("year"),
                )
                if trims:
                    all_specs.append(trims[0])
                else:
                    all_specs.append({
                        "model_make_id": car["make"],
                        "model_name": car["model"],
                        "_note": "Brak danych w bazie CarQuery"
                    })
            comparison = carquery.compare_cars(all_specs)
            return json.dumps(comparison, ensure_ascii=False)

        elif name == "get_makes":
            result = carquery.get_makes(year=input_data.get("year"))
            return json.dumps(result, ensure_ascii=False)

        elif name == "get_models":
            result = carquery.get_models(
                make=input_data["make"],
                year=input_data.get("year"),
                body=input_data.get("body"),
            )
            return json.dumps(result, ensure_ascii=False)

        else:
            return json.dumps({"error": f"Nieznane narzędzie: {name}"})

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


client = Anthropic()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/profil")
def profil():
    return render_template("profil.html")


@app.route("/ulubione")
def ulubione():
    return render_template("ulubione.html")


@app.route("/sprzedaj")
def sprzedaj():
    return render_template("sprzedaj.html")


@app.route("/porownaj")
def porownaj():
    return render_template("porownaj.html")


@app.route("/car/<car_id>")
def car_detail(car_id):
    try:
        car_data = carquery.get_model_detail(car_id)

        if not car_data:
            return render_template("error.html",
                                   message="Nie znaleziono samochodu o podanym ID."), 404

        return render_template("car_detail.html", car=car_data)

    except Exception as e:
        return render_template("error.html",
                               message=f"Błąd podczas pobierania danych: {str(e)}"), 500




@app.route("/api/cars", methods=["POST"])
def api_cars():
    data = request.get_json()
    ids = data.get("ids", [])

    if not ids:
        return jsonify({"cars": []})

    cars = []
    for model_id in ids:
        detail = carquery.get_model_detail(str(model_id))
        if detail:
            cars.append(detail)

    return jsonify({"cars": cars})


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    body = request.args.get("body", "").strip()
    fuel = request.args.get("fuel", "").strip()

    parts = query.split() if query else []
    make = parts[0] if parts else ""
    model = " ".join(parts[1:]) if len(parts) > 1 else ""

    results = []

    try:
        if make:
            trims = carquery.search_cars(
                make=make,
                model=model if model else None,
                body=body if body else None,
                fuel_type=fuel if fuel else None,
            )
            if isinstance(trims, list):
                results = trims
        elif body or fuel:
            for popular_make in ["Toyota", "BMW", "Ford", "Honda", "Volkswagen",
                                 "Mercedes-Benz", "Audi", "Hyundai", "Kia", "Tesla"]:
                trims = carquery.search_cars(
                    make=popular_make,
                    body=body if body else None,
                    fuel_type=fuel if fuel else None,
                )
                if isinstance(trims, list) and trims:
                    results.extend(trims)
                if len(results) >= 50:
                    break
    except Exception:
        results = []

    seen = set()
    unique = []
    for r in results:
        if not isinstance(r, dict):
            continue
        key = (r.get("model_make_id", ""), r.get("model_name", ""), r.get("model_year", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
        if len(unique) >= 12:
            break

    formatted = []
    for r in unique:
        formatted.append({
            "id": r.get("model_id", ""),
            "make": r.get("model_make_id", ""),
            "model": r.get("model_name", ""),
            "year": r.get("model_year", ""),
            "trim": r.get("model_trim", ""),
            "body": r.get("model_body", ""),
            "power": r.get("model_engine_power_ps", ""),
            "engine": r.get("model_engine_type", ""),
            "drive": r.get("model_drive", ""),
        })

    return jsonify({"results": formatted})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "Brak wiadomości"}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"error": "Brak klucza ANTHROPIC_API_KEY. Ustaw zmienną środowiskową przed uruchomieniem serwera."}), 500

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": _serialize_content(response.content)})
            messages.append({"role": "user", "content": tool_results})

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

        assistant_text = ""
        for block in response.content:
            if block.type == "text":
                assistant_text += block.text

        return jsonify({"response": assistant_text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _serialize_content(content_blocks):
    result = []
    for block in content_blocks:
        if block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return result


if __name__ == "__main__":
    app.run(debug=True, port=5000)
