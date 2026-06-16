"""
Sample data generator — mimics real IndiaMART scrape output
Run this if the live scraper is blocked (dev/CI environments)
"""
import pandas as pd
import numpy as np
import os, random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

CATEGORIES = {
    "industrial_machinery": [
        "CNC Milling Machine", "Hydraulic Press Machine", "Lathe Machine",
        "Conveyor Belt System", "Industrial Boiler", "Pneumatic Drill",
        "Sheet Metal Bending Machine", "Injection Moulding Machine",
        "Welding Machine", "Industrial Compressor", "Grinding Machine",
        "Forklift Truck", "Industrial Mixer", "Packaging Machine",
        "Cutting Machine", "Drilling Machine", "Stamping Machine",
        "Extrusion Machine", "Vibration Sieve Machine", "Heat Exchanger",
    ],
    "electronics": [
        "LED Strip Light", "Solar Panel 250W", "CCTV Camera", "UPS Battery",
        "Servo Motor", "PLC Controller", "Inverter", "Transformer",
        "Circuit Breaker", "Variable Frequency Drive", "Temperature Sensor",
        "Proximity Sensor", "Industrial Display Panel", "PCB Assembly",
        "Power Supply Unit", "Relay Module", "Arduino Board",
        "Raspberry Pi Module", "Bluetooth Module", "IoT Gateway Device",
    ],
    "textiles": [
        "Cotton Fabric Roll", "Polyester Yarn", "Denim Fabric",
        "Silk Saree", "Linen Shirt Fabric", "Woolen Blanket",
        "Nylon Thread", "Jute Bag", "Non-Woven Fabric",
        "Viscose Fabric", "Knitted Fabric", "Woven Label",
        "Embroidered Patch", "Terry Towel", "Velvet Fabric",
        "Lycra Fabric", "Spandex Blend", "Microfibre Cloth",
        "Canvas Tote Bag", "Polyester Fleece",
    ],
    "chemicals": [
        "Sulphuric Acid", "Sodium Hydroxide", "Hydrochloric Acid",
        "Acetic Acid", "Ferrous Sulphate", "Calcium Carbonate",
        "Sodium Carbonate", "Titanium Dioxide", "Epoxy Resin",
        "Polyurethane Foam", "Activated Carbon", "Chlorine Gas",
        "Isopropyl Alcohol", "Methanol", "Ethanol Industrial Grade",
        "Potassium Permanganate", "Hydrogen Peroxide", "Silica Gel",
        "Carbon Black", "Zinc Oxide",
    ],
    "agriculture": [
        "Tractor 45 HP", "Rotavator", "Seed Drill Machine",
        "Drip Irrigation Kit", "Sprinkler System", "Mini Rice Mill",
        "Thresher Machine", "Chaff Cutter", "Potato Digger",
        "Soil Testing Kit", "Organic Fertilizer", "DAP Fertilizer",
        "Urea Granules", "Pesticide Sprayer", "Greenhouse Film",
        "Poultry Feed", "Fish Feed", "Hydroponic Kit",
        "Cold Storage Unit", "Grain Silo",
    ],
}

CITIES = [
    ("Mumbai", "Maharashtra"), ("Delhi", "Delhi"), ("Bengaluru", "Karnataka"),
    ("Chennai", "Tamil Nadu"), ("Hyderabad", "Telangana"), ("Ahmedabad", "Gujarat"),
    ("Pune", "Maharashtra"), ("Kolkata", "West Bengal"), ("Surat", "Gujarat"),
    ("Jaipur", "Rajasthan"), ("Ludhiana", "Punjab"), ("Coimbatore", "Tamil Nadu"),
    ("Noida", "Uttar Pradesh"), ("Gurgaon", "Haryana"), ("Kochi", "Kerala"),
    ("Indore", "Madhya Pradesh"), ("Nagpur", "Maharashtra"), ("Vadodara", "Gujarat"),
    ("Patna", "Bihar"), ("Bhopal", "Madhya Pradesh"),
]

PRICE_RANGES = {
    "industrial_machinery": (5000, 500000),
    "electronics":          (200, 50000),
    "textiles":             (50, 5000),
    "chemicals":            (100, 20000),
    "agriculture":          (500, 200000),
}

SUPPLIERS = [
    "{city} Industries Pvt Ltd", "{city} Traders", "Global {cat} Co.",
    "Shree {cat} Enterprises", "Sri {city} Suppliers",
    "National {cat} Works", "{city} Manufacturing Co.",
    "Reliable {cat} Solutions", "Premium {cat} Exports",
    "Modern {city} Tech", "Star {cat} Corporation",
    "United {city} Traders", "BK Industries", "RK Enterprises",
    "Apex {cat} Solutions", "Pioneer {cat} Works",
]

def gen_supplier(city, cat):
    tmpl = random.choice(SUPPLIERS)
    cat_word = cat.replace("_", " ").title().split()[0]
    return tmpl.format(city=city, cat=cat_word)

def gen_price(cat):
    lo, hi = PRICE_RANGES[cat]
    base = random.uniform(lo, hi)
    if random.random() < 0.6:
        pmax = base * random.uniform(1.2, 2.5)
        return round(base, 2), round(pmax, 2)
    return round(base, 2), round(base, 2)

def gen_dataset(n=500):
    rows = []
    cat_keys = list(CATEGORIES.keys())
    start_date = datetime(2025, 1, 1)

    for _ in range(n):
        cat    = random.choice(cat_keys)
        prod   = random.choice(CATEGORIES[cat])
        city, state = random.choice(CITIES)
        pmin, pmax = gen_price(cat)
        supplier = gen_supplier(city, cat)
        rating = round(random.uniform(3.0, 5.0), 1) if random.random() > 0.25 else None
        moq_n  = random.choice([1, 5, 10, 50, 100, 500, 1000])
        unit   = random.choice(["Piece", "Kg", "Meter", "Set", "Unit", "Litre", "Ton"])
        verified = random.random() > 0.4
        days   = random.randint(0, 180)
        scraped = (start_date + timedelta(days=days)).isoformat()

        # Inject realistic missing values
        if random.random() < 0.12: pmin = None; pmax = None
        if random.random() < 0.08: city = "Unknown"; state = "Unknown"
        if random.random() < 0.22: rating = None
        if random.random() < 0.18: moq_n = None

        rows.append({
            "product_name":  prod,
            "supplier_name": supplier,
            "location":      f"{city}, {state}",
            "city":          city,
            "state":         state,
            "category":      cat,
            "price_min":     pmin,
            "price_max":     pmax,
            "price_mid":     round((pmin+pmax)/2, 2) if pmin and pmax else None,
            "price_unit":    unit,
            "currency":      "INR",
            "rating":        rating,
            "moq":           f"Min {moq_n} {unit}" if moq_n else None,
            "verified":      verified,
            "product_url":   f"https://www.indiamart.com/proddetail/{prod.lower().replace(' ','-')}.html",
            "scraped_at":    scraped,
        })

    # Add ~3% duplicates to test dedup
    dup_rows = random.sample(rows, int(n * 0.03))
    rows.extend(dup_rows)
    random.shuffle(rows)

    return pd.DataFrame(rows)

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    df = gen_dataset(500)
    path = os.path.join(out_dir, "indiamart_raw.csv")
    df.to_csv(path, index=False)
    print(f"✅ Generated {len(df)} rows → {path}")
    print(df.groupby("category").size())
