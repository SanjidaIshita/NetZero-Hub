"""Reference data for the Solar Panel Installation service (ORG-001).

System sizes, roof types, add-ons and prices are placeholders for the assignment.
Installers are fictional and matched by NSW postcode range.
"""

SERVICE_ID = "ORG-001"

SYSTEM_SIZES = [
    {"id": "3kw", "name": "3kW system", "price": 3990, "panels": 8,
     "description": "Small homes or apartments. Suits roughly 8-12 kWh per day.", "dailyKwh": 12},
    {"id": "5kw", "name": "5kW system", "price": 5490, "panels": 13,
     "description": "Most popular for 2-3 person households. Roughly 12-20 kWh per day.", "dailyKwh": 20},
    {"id": "6.6kw", "name": "6.6kW system", "price": 6590, "panels": 16,
     "description": "Family homes with daytime usage. Roughly 20-26 kWh per day.", "dailyKwh": 26},
    {"id": "10kw", "name": "10kW system", "price": 9490, "panels": 24,
     "description": "Large homes, pools or EVs. Roughly 26-40 kWh per day.", "dailyKwh": 40},
    {"id": "13kw", "name": "13kW system", "price": 11990, "panels": 30,
     "description": "Very high usage or small business premises. 40+ kWh per day.", "dailyKwh": 999},
]

ROOF_TYPES = [
    {"id": "tiled", "name": "Concrete tiles", "surcharge": 0, "description": "Standard tile hooks."},
    {"id": "metal", "name": "Colorbond / metal", "surcharge": 0, "description": "Quickest install type."},
    {"id": "terracotta", "name": "Terracotta tiles", "surcharge": 350, "description": "Extra care for brittle tiles."},
    {"id": "flat", "name": "Flat roof", "surcharge": 600, "description": "Tilt frames for the right angle."},
    {"id": "slate", "name": "Slate", "surcharge": 900, "description": "Specialist mounting required."},
]

PROPERTY_TYPES = [
    {"id": "house", "name": "House"},
    {"id": "townhouse", "name": "Townhouse"},
    {"id": "apartment", "name": "Apartment (strata approval needed)"},
    {"id": "business", "name": "Business premises"},
]

STOREYS = [
    {"id": "single", "name": "Single storey", "surcharge": 0},
    {"id": "double", "name": "Double storey", "surcharge": 300},
    {"id": "triple", "name": "Three or more", "surcharge": 650},
]

ADD_ONS = [
    {"id": "battery", "name": "Home battery (10 kWh)", "price": 8990,
     "description": "Store daytime solar to use at night and during outages."},
    {"id": "ev_charger", "name": "EV charger (7 kW)", "price": 1590,
     "description": "Wall-mounted charger that can run on excess solar."},
    {"id": "monitoring", "name": "Smart energy monitoring", "price": 299,
     "description": "Track generation and usage live in an app."},
    {"id": "bird_proofing", "name": "Bird proofing mesh", "price": 450,
     "description": "Stops pigeons nesting under the panels."},
    {"id": "panel_cleaning", "name": "First-year panel clean", "price": 149,
     "description": "One professional clean 12 months after install."},
]

TIME_SLOTS = [
    {"id": "am", "label": "8am – 12pm", "start": "08:00", "end": "12:00", "capacity": 6},
    {"id": "pm", "label": "12pm – 4pm", "start": "12:00", "end": "16:00", "capacity": 6},
]

# Fictional installation partners by postcode range (NSW)
INSTALLERS = [
    ((2500, 2534), "Illawarra Solar Installs", "Wollongong"),
    ((2000, 2234), "Harbour City Solar", "Sydney"),
    ((2745, 2786), "Blue Mountains Energy Co.", "the Blue Mountains"),
    ((2250, 2263), "Central Coast Sun Systems", "the Central Coast"),
    ((2280, 2310), "Hunter Solar Group", "Newcastle"),
    ((2535, 2541), "South Coast Solar", "the South Coast"),
    ((2600, 2620), "Capital Solar Services", "Canberra"),
]

# Suburbs we can auto-fill
SUBURBS = {
    "2500": ["WOLLONGONG", "NORTH WOLLONGONG", "GWYNNEVILLE", "KEIRAVILLE", "MOUNT KEIRA", "WEST WOLLONGONG"],
    "2502": ["CRINGILA", "LAKE HEIGHTS", "PRIMBEE", "WARRAWONG"],
    "2505": ["PORT KEMBLA"],
    "2515": ["THIRROUL", "AUSTINMER", "COLEDALE", "WOMBARRA"],
    "2516": ["BULLI"],
    "2517": ["WOONONA", "RUSSELL VALE"],
    "2518": ["CORRIMAL", "BELLAMBI", "EAST CORRIMAL", "TOWRADGI"],
    "2519": ["FAIRY MEADOW", "FERNHILL", "MOUNT OUSLEY", "BALGOWNIE"],
    "2525": ["FIGTREE"],
    "2526": ["UNANDERRA", "FARMBOROUGH HEIGHTS", "KEMBLAWARRA"],
    "2527": ["ALBION PARK", "ALBION PARK RAIL"],
    "2528": ["SHELLHARBOUR", "WARILLA", "BARRACK HEIGHTS", "LAKE ILLAWARRA"],
    "2529": ["SHELLHARBOUR CITY CENTRE", "FLINDERS", "SHELL COVE"],
    "2530": ["DAPTO", "HORSLEY", "KANAHOOKA", "BROWNSVILLE"],
    "2533": ["KIAMA", "MINNAMURRA"],
    "2000": ["SYDNEY", "THE ROCKS", "DAWES POINT", "HAYMARKET"],
    "2010": ["SURRY HILLS", "DARLINGHURST"],
    "2150": ["PARRAMATTA", "HARRIS PARK"],
}


def find_installer(postcode: str):
    if not postcode.isdigit() or len(postcode) != 4:
        return None
    pc = int(postcode)
    for (lo, hi), name, region in INSTALLERS:
        if lo <= pc <= hi:
            return {"name": name, "region": region}
    return None


def by_id(items, item_id):
    return next((i for i in items if i["id"] == item_id), None)
