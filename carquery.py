import requests
import json
import re

BASE_URL = "https://www.carqueryapi.com/api/0.3/"


def _parse_jsonp(text):
    """Parse JSONP response to plain JSON."""
    match = re.search(r'\((.*)\)', text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _get(params):
    """Make a request to CarQuery API and parse response."""
    params["callback"] = "cb"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.carqueryapi.com/",
    }
    resp = requests.get(BASE_URL, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    return _parse_jsonp(resp.text)


def get_makes(year=None):
    """Get list of car manufacturers, optionally filtered by year."""
    params = {"cmd": "getMakes"}
    if year:
        params["year"] = str(year)
    data = _get(params)
    if data and "Makes" in data:
        return data["Makes"]
    return []


def get_models(make, year=None, body=None):
    """Get list of models for a given make."""
    params = {"cmd": "getModels", "make": make}
    if year:
        params["year"] = str(year)
    if body:
        params["body"] = body
    data = _get(params)
    if data and "Models" in data:
        return data["Models"]
    return []


def get_trims(make, model, year=None):
    """Get trim/technical data for a given make and model."""
    params = {"cmd": "getTrims", "make": make, "model": model}
    if year:
        params["year"] = str(year)
    data = _get(params)
    if data and "Trims" in data:
        return data["Trims"]
    return []


def get_model_detail(model_id):
    """Get detailed specs for a specific model ID."""
    params = {"cmd": "getModel", "model": str(model_id)}
    data = _get(params)
    if data:
        # API returns a list for getModel
        if isinstance(data, list) and data:
            return data[0]
        return data
    return None


def search_cars(make=None, model=None, year=None, body=None, min_power=None,
                max_power=None, fuel_type=None, drive=None):
    """Search cars with various filters. Returns trims matching criteria."""
    if not make:
        return {"error": "Podaj przynajmniej markę samochodu (make)."}

    params = {"cmd": "getTrims", "make": make}
    if model:
        params["model"] = model
    if year:
        params["year"] = str(year)
    if body:
        params["body"] = body
    if fuel_type:
        params["fuel_type"] = fuel_type
    if drive:
        params["drive"] = drive

    data = _get(params)
    if not data or "Trims" not in data:
        return []

    trims = data["Trims"]

    # Filter by power if specified
    if min_power or max_power:
        filtered = []
        for t in trims:
            hp = t.get("model_engine_power_ps")
            if hp:
                try:
                    hp_val = int(hp)
                    if min_power and hp_val < int(min_power):
                        continue
                    if max_power and hp_val > int(max_power):
                        continue
                    filtered.append(t)
                except (ValueError, TypeError):
                    continue
        trims = filtered

    return trims


def compare_cars(car_specs_list):
    """Format comparison data for multiple cars (list of trim dicts)."""
    keys = [
        ("model_make_id", "Marka"),
        ("model_name", "Model"),
        ("model_year", "Rok"),
        ("model_trim", "Wersja"),
        ("model_body", "Nadwozie"),
        ("model_engine_type", "Typ silnika"),
        ("model_engine_cc", "Pojemność [cc]"),
        ("model_engine_power_ps", "Moc [KM]"),
        ("model_engine_torque_nm", "Moment [Nm]"),
        ("model_drive", "Napęd"),
        ("model_transmission_type", "Skrzynia"),
        ("model_weight_kg", "Masa [kg]"),
        ("model_fuel_cap_l", "Zbiornik [l]"),
        ("model_doors", "Drzwi"),
        ("model_seats", "Miejsca"),
    ]

    result = []
    for spec in car_specs_list:
        car_info = {}
        for api_key, label in keys:
            val = spec.get(api_key, "b/d")
            car_info[label] = val if val else "b/d"
        result.append(car_info)
    return result
