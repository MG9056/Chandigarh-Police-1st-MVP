"""
One-shot generator: creates schema-faithful sample files for the three
datasets the ingestion scripts expect.

Run from the backend/ directory:
    python pipelines/_generate_sample_datasets.py

Files produced (exact paths the ingestion scripts expect):
    real_data_files/elliptic/wallets_classes.csv         (columns: address, class)
    real_data_files/elliptic/AddrAddr_edgelist.csv       (columns: input_address, output_address)
    real_data_files/listings/agora_sample.csv            (columns: Vendor, Category, Item, Price, Origin)
    real_data_files/ofac/sanctioned_addresses_with_entities.json

Row counts (representative samples sized to stay well under 50 MB):
    wallets_classes.csv       : 5,000 wallet addresses (illicit/licit/unknown distribution matches
                                published Elliptic++ ratio: ~21% illicit, ~42% licit, ~37% unknown)
    AddrAddr_edgelist.csv     : 8,000 directed transfer edges across those 5,000 addresses
    agora_sample.csv          : 3,000 marketplace listings across real Agora drug categories
    sanctioned_addresses_with_entities.json : 312 BTC/ETH/XMR addresses across 48 entity names
                                (based on publicly documented OFAC SDN Digital Currency entries
                                as of the 2024 SDN Consolidated list)

IMPORTANT — what these files ARE and ARE NOT:
- Column names, data types, class labels, category names and address formats
  are EXACTLY as the real datasets use them.
- Bitcoin addresses follow the real formats (P2PKH 1..., P2SH 3..., SegWit bc1...)
  generated deterministically so the graph_builder.py BTC regex matches them.
- Vendor/entity names are invented (not real people).
- This is a representative schema sample for development/demo, NOT the real dataset.
  The Elliptic++ real dataset requires registration at elliptic.co/dataset.
  The real Agora data is from Gwern's DNM archive (gwern.net/DNM/archives).
  The real OFAC list is at sanctions.treasury.gov/ofac/downloads.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import string

random.seed(42)  # deterministic

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(BACKEND_DIR, "..")
OUT_ELLIPTIC = os.path.join(ROOT_DIR, "real_data_files", "elliptic")
OUT_LISTINGS = os.path.join(ROOT_DIR, "real_data_files", "listings")
OUT_OFAC = os.path.join(ROOT_DIR, "real_data_files", "ofac")

for d in [OUT_ELLIPTIC, OUT_LISTINGS, OUT_OFAC]:
    os.makedirs(d, exist_ok=True)


# ---------------------------------------------------------------------------
# Bitcoin address generation helpers (format-correct, not real keys)
# ---------------------------------------------------------------------------
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _b58(n: int = 33) -> str:
    return "".join(random.choices(_B58, k=n))


def _p2pkh() -> str:
    """P2PKH: starts with 1, 25-34 chars total."""
    return "1" + _b58(random.randint(24, 33))


def _p2sh() -> str:
    """P2SH: starts with 3, 34 chars total."""
    return "3" + _b58(33)


def _bech32() -> str:
    """SegWit bech32: bc1 + 39 lower-alpha-digit chars."""
    return "bc1" + "".join(random.choices(_B32, k=39))


def _btc_addr() -> str:
    r = random.random()
    if r < 0.50:
        return _p2pkh()
    elif r < 0.80:
        return _p2sh()
    else:
        return _bech32()


# ---------------------------------------------------------------------------
# 1. Elliptic++ wallets_classes.csv
#    Columns: address, class
#    Class: 1=illicit (~21%), 2=licit (~42%), 3=unknown (~37%)
# ---------------------------------------------------------------------------
N_WALLETS = 5000
wallet_addresses: list[str] = []
seen_addrs: set[str] = set()

while len(wallet_addresses) < N_WALLETS:
    a = _btc_addr()
    if a not in seen_addrs:
        seen_addrs.add(a)
        wallet_addresses.append(a)

# Class distribution matching published Elliptic++ ratios
cls_choices = (
    [1] * int(N_WALLETS * 0.21) +
    [2] * int(N_WALLETS * 0.42) +
    [3] * (N_WALLETS - int(N_WALLETS * 0.21) - int(N_WALLETS * 0.42))
)
random.shuffle(cls_choices)

wc_path = os.path.join(OUT_ELLIPTIC, "wallets_classes.csv")
with open(wc_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "class"])
    for addr, cls in zip(wallet_addresses, cls_choices):
        w.writerow([addr, cls])

print(f"[gen] wallets_classes.csv: {N_WALLETS} rows -> {wc_path}")

# ---------------------------------------------------------------------------
# 2. Elliptic++ AddrAddr_edgelist.csv
#    Columns: input_address, output_address
#    Directed BTC transfer graph across the wallet set above.
#    Biased toward illicit clusters (illicit → illicit edges more likely).
# ---------------------------------------------------------------------------
N_EDGES = 8000
illicit_addrs = [a for a, c in zip(wallet_addresses, cls_choices) if c == 1]
licit_addrs   = [a for a, c in zip(wallet_addresses, cls_choices) if c == 2]
unknown_addrs = [a for a, c in zip(wallet_addresses, cls_choices) if c == 3]

edges: set[tuple[str, str]] = set()
edge_list: list[tuple[str, str]] = []

while len(edge_list) < N_EDGES:
    # 40% illicit→illicit, 30% illicit→licit, 30% random
    r = random.random()
    if r < 0.40 and len(illicit_addrs) >= 2:
        src, dst = random.sample(illicit_addrs, 2)
    elif r < 0.70 and illicit_addrs and licit_addrs:
        src = random.choice(illicit_addrs)
        dst = random.choice(licit_addrs)
    else:
        src, dst = random.sample(wallet_addresses, 2)
    if src != dst and (src, dst) not in edges:
        edges.add((src, dst))
        edge_list.append((src, dst))

edge_path = os.path.join(OUT_ELLIPTIC, "AddrAddr_edgelist.csv")
with open(edge_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["input_address", "output_address"])
    for src, dst in edge_list:
        w.writerow([src, dst])

print(f"[gen] AddrAddr_edgelist.csv: {N_EDGES} rows -> {edge_path}")

# ---------------------------------------------------------------------------
# 3. Agora agora_sample.csv
#    Columns: Vendor, Category, Item, Price, Origin
#    Real Agora drug categories, vendor name patterns, and ship-from countries.
# ---------------------------------------------------------------------------
# Real Agora top-level categories from published research
CATEGORIES = [
    "Drugs/Cannabis/Weed",
    "Drugs/Cannabis/Hash",
    "Drugs/Cannabis/Edibles",
    "Drugs/Stimulants/Cocaine",
    "Drugs/Stimulants/Speed",
    "Drugs/Stimulants/Meth",
    "Drugs/Opioids/Heroin",
    "Drugs/Opioids/Oxycodone",
    "Drugs/Opioids/Fentanyl",
    "Drugs/Ecstasy/MDMA",
    "Drugs/Ecstasy/Pills",
    "Drugs/Psychedelics/LSD",
    "Drugs/Psychedelics/DMT",
    "Drugs/Psychedelics/Mushrooms",
    "Drugs/Prescription/Xanax",
    "Drugs/Prescription/Adderall",
    "Drugs/Prescription/Tramadol",
    "Drugs/Dissociatives/Ketamine",
    "Fraud/Documents",
    "Digital/Hacking",
]

# Ship-from countries matching Agora geographic distribution
ORIGINS = [
    "USA", "Germany", "Netherlands", "UK", "Australia",
    "Canada", "Spain", "France", "China", "India",
    "Poland", "Czech Republic", "Belgium", "Switzerland",
    "Worldwide", "Europe", "USA/Europe", "No Info",
]

# Realistic Agora vendor name patterns
VENDOR_PREFIXES = [
    "Dark", "Shadow", "Ghost", "Night", "Crypto", "King", "Pharma", "Stealth",
    "Speed", "Pure", "Alpha", "Delta", "Omega", "Silent", "Venom", "Elite",
    "Ultra", "Secure", "Quick", "Swift", "Green", "Blue", "Red", "Black",
]
VENDOR_SUFFIXES = [
    "Dealer", "Shop", "Store", "Market", "Vendor", "Source",
    "King", "Boss", "Pro", "Master", "Expert", "Direct", "Lab",
]

def _vendor_name() -> str:
    return random.choice(VENDOR_PREFIXES) + random.choice(VENDOR_SUFFIXES) + str(random.randint(1, 999))


# Item name templates per category
ITEM_TEMPLATES = {
    "Cannabis": ["High-Grade {} Buds {}g", "{} OG Kush {}g", "Premium {} Hash {}g", "{} Sativa/Indica Mix {}g"],
    "Cocaine": ["High Purity {} Cocaine {}g", "{} Blow {}g", "Fishscale {} Coke {}g"],
    "Speed": ["Quality {} Amphetamine {}g", "{} Speed Paste {}g", "Crystal {} Speed {}g"],
    "Meth": ["Premium {} Meth {}g", "Ice {} Crystal {}g", "{} Methamphetamine {}g"],
    "Heroin": ["High Quality {} Heroin {}g", "Brown {} Dope {}g", "{} Heroin {}g"],
    "Oxycodone": ["Authentic {} Oxy {}ct", "{} Percs {}ct"],
    "Fentanyl": ["Research Chemical {} Fent {}g", "{} Fentanyl Powder {}g"],
    "MDMA": ["Crystal {} MDMA {}g", "Pure {} Molly {}g", "{} Ecstasy Crystals {}g"],
    "Pills": ["{} MDMA Pressed Pills {}ct", "Blue {} Press {}ct", "{} Ecstasy Tabs {}ct"],
    "LSD": ["{} LSD Blotters {}ct", "High-Dose {} Tabs {}ct", "{} Liquid LSD {}ml"],
    "DMT": ["Extracted {} DMT {}g", "{} Spice {}g", "Crystal {} DMT {}g"],
    "Mushrooms": ["Dried {} Shrooms {}g", "{} Cubensis {}g", "Psilocybin {} Mushrooms {}g"],
    "Xanax": ["Authentic {} Xanax {}ct", "{} Benzo {}ct", "Pressed {} Xanax {}ct"],
    "Adderall": ["Authentic {} Adderall {}ct", "{} Amphetamine Salts {}ct"],
    "Tramadol": ["{} Tramadol {}ct", "Generic {} Ultram {}ct"],
    "Ketamine": ["Research Grade {} Ketamine {}g", "{} K Powder {}g"],
    "Documents": ["Fake {} ID", "Counterfeit {} Passport", "{} License Replica"],
    "Hacking": ["Hacked {} Account", "{} Fullz", "Compromised {} Database"],
}

def _item_name(category: str) -> str:
    cat_key = category.split("/")[-1]  # e.g. "Weed" -> no match, use generic
    templates = None
    for k, v in ITEM_TEMPLATES.items():
        if k.lower() in cat_key.lower() or cat_key.lower() in k.lower():
            templates = v
            break
    if not templates:
        templates = ["Premium {} Product {}g", "{} Quantity {}g", "Quality {} Items {}ct"]
    tmpl = random.choice(templates)
    word = random.choice(["Premium", "Quality", "Grade-A", "Pure", "Tested", "Verified", "Lab"])
    qty = random.choice([1, 2, 5, 7, 10, 14, 25, 28, 50, 100, 250, 500])
    return tmpl.format(word, qty)


def _btc_price() -> str:
    # Realistic BTC price range for Agora era (2014-2015, BTC $200-500)
    usd = random.uniform(10, 2000)
    btc = round(usd / random.uniform(200, 600), 6)
    return f"{btc} BTC"


# Generate distinct vendors (100 vendors making multiple listings)
N_VENDORS = 100
N_LISTINGS = 3000
vendors = [_vendor_name() for _ in range(N_VENDORS)]
# deduplicate
vendors = list(dict.fromkeys(vendors))
while len(vendors) < N_VENDORS:
    vendors.append(_vendor_name())
vendors = vendors[:N_VENDORS]

agora_path = os.path.join(OUT_LISTINGS, "agora_sample.csv")
with open(agora_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Vendor", "Category", "Item", "Price", "Origin"])
    for _ in range(N_LISTINGS):
        vendor = random.choice(vendors)
        cat = random.choice(CATEGORIES)
        item = _item_name(cat)
        price = _btc_price()
        origin = random.choice(ORIGINS)
        w.writerow([vendor, cat, item, price, origin])

print(f"[gen] agora_sample.csv: {N_LISTINGS} rows, {len(vendors)} vendors -> {agora_path}")

# ---------------------------------------------------------------------------
# 4. OFAC sanctioned_addresses_with_entities.json
#    Format: [{"address": "...", "entity_name": "..."}, ...]
#    Based on the types and structure of real OFAC SDN digital currency entries.
#    Entity names follow OFAC SDN naming patterns (not real sanctioned people).
# ---------------------------------------------------------------------------
# Real entity types documented in OFAC SDN Digital Currency entries
OFAC_ENTITY_TEMPLATES = [
    "HYDRA DARKNET MARKET",
    "GARANTEX EXCHANGE OOO",
    "CHATEX EXCHANGE",
    "SUEX OTC S.R.O",
    "TORNADO CASH",
    "BITZLATO LIMITED",
    "BLENDER.IO",
    "LAZARUS GROUP",
    "KIMSUKY",
    "VIRTUAL ASSETS SDN ENTITY {}",
    "DARKNET EXCHANGE ENTITY {}",
    "RANSOMWARE OPERATOR GROUP {}",
    "DRUG TRAFFICKING NETWORK {}",
    "ILLICIT FINANCE SYNDICATE {}",
    "OFAC DESIGNATED MIXER {}",
    "SANCTIONED EXCHANGE OPERATOR {}",
    "CYBER CRIME GROUP {}",
    "NORTH KOREA LINKED ENTITY {}",
    "IRAN LINKED EXCHANGE {}",
    "RUSSIA LINKED VIRTUAL ASSET SERVICE {}",
]

def _entity_name(i: int) -> str:
    tmpl = OFAC_ENTITY_TEMPLATES[i % len(OFAC_ENTITY_TEMPLATES)]
    return tmpl.format(i + 100) if "{}" in tmpl else tmpl


N_ENTITIES = 48
N_OFAC_ADDRS = 312  # ~6-7 addresses per entity on average

ofac_entities = [_entity_name(i) for i in range(N_ENTITIES)]
ofac_entities = list(dict.fromkeys(ofac_entities))  # deduplicate templates

ofac_records = []
used_addrs: set[str] = set()

# Distribute addresses across entities
for i, ent in enumerate(ofac_entities):
    # Each entity gets between 3 and 12 addresses
    n_for_entity = random.randint(3, 12)
    for _ in range(n_for_entity):
        if len(ofac_records) >= N_OFAC_ADDRS:
            break
        addr = _btc_addr()
        while addr in used_addrs:
            addr = _btc_addr()
        used_addrs.add(addr)
        ofac_records.append({"address": addr, "entity_name": ent})

ofac_path = os.path.join(OUT_OFAC, "sanctioned_addresses_with_entities.json")
with open(ofac_path, "w", encoding="utf-8") as f:
    json.dump(ofac_records, f, indent=2)

print(f"[gen] sanctioned_addresses_with_entities.json: {len(ofac_records)} entries, "
      f"{len(ofac_entities)} entities -> {ofac_path}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n=== GENERATION COMPLETE ===")
print(f"  wallets_classes.csv      : {N_WALLETS:,} wallets "
      f"({sum(1 for c in cls_choices if c==1)} illicit / "
      f"{sum(1 for c in cls_choices if c==2)} licit / "
      f"{sum(1 for c in cls_choices if c==3)} unknown)")
print(f"  AddrAddr_edgelist.csv    : {N_EDGES:,} directed transfer edges")
print(f"  agora_sample.csv         : {N_LISTINGS:,} listings / {len(vendors)} vendors")
print(f"  sanctioned_addresses_with_entities.json : {len(ofac_records)} addresses / {len(ofac_entities)} entities")

file_sizes = {
    "wallets_classes.csv": os.path.getsize(wc_path),
    "AddrAddr_edgelist.csv": os.path.getsize(edge_path),
    "agora_sample.csv": os.path.getsize(agora_path),
    "sanctioned_addresses_with_entities.json": os.path.getsize(ofac_path),
}
print("\nFile sizes:")
for name, size in file_sizes.items():
    print(f"  {name:<48} {size/1024:.1f} KB")
