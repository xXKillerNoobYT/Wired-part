"""Seed the database with realistic mock data for development and demos.

Creates:
  - 8 users (all PIN 1423) with various hats
  - 5 suppliers
  - 6 categories
  - 5 brands
  - 15 branded + 50 non-branded = 65 parts total (wire, outlets, switches,
    boxes, cover plates, conduit, fittings, breakers, lighting, consumables)
  - 7 trucks (stocked with inventory)
  - 5 active jobs
  - 17 purchase orders (mixed statuses)

Run:
    python -m execution.seed_mock_data          (from project root)
    python execution/seed_mock_data.py          (direct)

WARNING: This script INSERTS data — run against a fresh DB to avoid
duplicates. Delete data/wired_part.db first for a clean start.
"""

import os
import sys

# Ensure project src is on the path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import (
    Brand,
    Category,
    Job,
    Part,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    Truck,
    User,
)
from wired_part.database.repository import Repository

PIN = "1423"


def seed(repo: Repository):
    """Populate the database with mock data."""

    pin_hash = Repository.hash_pin(PIN)

    # ── 1. Users ──────────────────────────────────────────────────
    print("Creating users...")
    users = [
        ("admin", "Mike Torres", "Admin / CEO / Owner"),
        ("sarah", "Sarah Chen", "Office / HR"),
        ("derek", "Derek Martinez", "Job Manager"),
        ("jose", "José Ramirez", "Foreman"),
        ("kevin", "Kevin O'Brien", "Worker"),
        ("carlos", "Carlos Vega", "Worker"),
        ("jake", "Jake Petrov", "Grunt"),
        ("itadmin", "IT Admin", "IT / Tech Junkie"),
    ]
    user_ids = {}
    for username, display, hat_name in users:
        u = User(
            username=username,
            display_name=display,
            pin_hash=pin_hash,
            role="admin" if "Admin" in hat_name else "user",
            is_active=1,
        )
        uid = repo.create_user(u)
        user_ids[username] = uid
        hat = repo.get_hat_by_name(hat_name)
        if hat:
            repo.assign_hat(uid, hat.id, assigned_by=uid)
    print(f"  → {len(users)} users created (all PIN {PIN})")

    admin_id = user_ids["admin"]

    # ── 2. Suppliers ──────────────────────────────────────────────
    print("Creating suppliers...")
    suppliers_data = [
        Supplier(name="Home Depot Pro", contact_name="Jim Stewart",
                 phone="555-100-2001", email="pro@homedepot.com",
                 address="1200 Industrial Blvd, Dallas TX",
                 is_supply_house=1, preference_score=80,
                 operating_hours="Mon-Sat 6am-8pm"),
        Supplier(name="Graybar Electric", contact_name="Lisa Park",
                 phone="555-200-3002", email="orders@graybar.com",
                 address="450 Distributor Way, Austin TX",
                 is_supply_house=1, preference_score=90,
                 operating_hours="Mon-Fri 7am-5pm"),
        Supplier(name="Wesco International", contact_name="Tom Hardy",
                 phone="555-300-4003", email="sales@wesco.com",
                 address="78 Commerce Dr, Houston TX",
                 preference_score=70),
        Supplier(name="City Electric Supply", contact_name="Maria Lopez",
                 phone="555-400-5004", email="orders@cityelectric.com",
                 address="320 Supply Ave, San Antonio TX",
                 is_supply_house=1, preference_score=85,
                 operating_hours="Mon-Fri 6:30am-5pm, Sat 7am-12pm"),
        Supplier(name="Platt Electric Supply", contact_name="Dave Wilson",
                 phone="555-500-6005", email="orders@platt.com",
                 address="901 Electrical Blvd, Fort Worth TX",
                 preference_score=75),
    ]
    supplier_ids = {}
    for s in suppliers_data:
        sid = repo.create_supplier(s)
        supplier_ids[s.name] = sid
    print(f"  → {len(suppliers_data)} suppliers created")

    # ── 3. Categories ─────────────────────────────────────────────
    print("Creating categories...")
    # Use existing default categories if they exist, else create
    existing = {c.name: c.id for c in repo.get_all_categories()}
    categories_data = [
        Category(name="Wire & Cable", description="Romex, THHN, MC cable",
                 color="#89b4fa"),
        Category(name="Boxes & Covers", description="Junction, switch, outlet boxes",
                 color="#f9e2af"),
        Category(name="Switches & Receptacles", description="Dimmers, outlets, GFCIs",
                 color="#a6e3a1"),
        Category(name="Panels & Breakers", description="Load centers, breakers",
                 color="#f38ba8"),
        Category(name="Conduit & Fittings", description="EMT, PVC, connectors",
                 color="#cba6f7"),
        Category(name="Lighting", description="LEDs, fixtures, ballasts",
                 color="#fab387"),
    ]
    cat_ids = {}
    for cat in categories_data:
        if cat.name in existing:
            cat_ids[cat.name] = existing[cat.name]
        else:
            cid = repo.create_category(cat)
            cat_ids[cat.name] = cid
    print(f"  → {len(categories_data)} categories ensured")

    # ── 4. Brands ─────────────────────────────────────────────────
    print("Creating brands...")
    brands_data = [
        Brand(name="Leviton", website="leviton.com", notes="Wiring devices"),
        Brand(name="Siemens", website="siemens.com", notes="Panels and breakers"),
        Brand(name="Southwire", website="southwire.com", notes="Wire manufacturer"),
        Brand(name="Eaton", website="eaton.com", notes="Breakers and panels"),
        Brand(name="Lutron", website="lutron.com", notes="Dimmers and controls"),
    ]
    brand_ids = {}
    for b in brands_data:
        existing_brand = repo.get_brand_by_name(b.name)
        if existing_brand:
            brand_ids[b.name] = existing_brand.id
        else:
            bid = repo.create_brand(b)
            brand_ids[b.name] = bid
    print(f"  → {len(brands_data)} brands ensured")

    # ── 5. Parts — 15 branded + 5 non-branded ────────────────────
    print("Creating parts...")
    parts_branded = [
        Part(part_number="WC-14-250", name="14/2 NM-B Romex 250ft",
             description="14/2 Non-Metallic Sheathed Cable 250ft roll",
             category_id=cat_ids["Wire & Cable"],
             brand_id=brand_ids["Southwire"],
             brand_part_number="SW-28827427",
             unit_cost=78.50, quantity=12, min_quantity=5, max_quantity=30,
             part_type="specific", supplier="Graybar Electric"),
        Part(part_number="WC-12-250", name="12/2 NM-B Romex 250ft",
             description="12/2 Non-Metallic Sheathed Cable 250ft roll",
             category_id=cat_ids["Wire & Cable"],
             brand_id=brand_ids["Southwire"],
             brand_part_number="SW-28827428",
             unit_cost=98.75, quantity=8, min_quantity=4, max_quantity=20,
             part_type="specific", supplier="Graybar Electric"),
        Part(part_number="WC-10-100", name="10/3 NM-B Romex 100ft",
             description="10/3 Non-Metallic Sheathed Cable 100ft roll",
             category_id=cat_ids["Wire & Cable"],
             brand_id=brand_ids["Southwire"],
             brand_part_number="SW-63946821",
             unit_cost=115.00, quantity=4, min_quantity=3, max_quantity=10,
             part_type="specific", supplier="Graybar Electric"),
        Part(part_number="SR-DPLX-15", name="Duplex Receptacle 15A",
             description="Standard duplex outlet, 15A 125V, white",
             category_id=cat_ids["Switches & Receptacles"],
             brand_id=brand_ids["Leviton"],
             brand_part_number="LEV-5320-W",
             unit_cost=1.85, quantity=200, min_quantity=50, max_quantity=500,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="SR-GFCI-15", name="GFCI Receptacle 15A",
             description="Ground Fault Circuit Interrupter, 15A 125V, white",
             category_id=cat_ids["Switches & Receptacles"],
             brand_id=brand_ids["Leviton"],
             brand_part_number="LEV-GFNT1-W",
             unit_cost=16.50, quantity=45, min_quantity=20, max_quantity=100,
             part_type="specific", supplier="City Electric Supply"),
        Part(part_number="SR-AFCI-15", name="AFCI Receptacle 15A",
             description="Arc Fault Circuit Interrupter outlet, 15A, white",
             category_id=cat_ids["Switches & Receptacles"],
             brand_id=brand_ids["Leviton"],
             brand_part_number="LEV-AFTR1-W",
             unit_cost=28.50, quantity=30, min_quantity=10, max_quantity=60,
             part_type="specific", supplier="City Electric Supply"),
        Part(part_number="SR-DIMM-LED", name="LED Dimmer Switch",
             description="Single-pole LED dimmer, 150W, white",
             category_id=cat_ids["Switches & Receptacles"],
             brand_id=brand_ids["Lutron"],
             brand_part_number="LUT-DVCL-153P",
             unit_cost=22.75, quantity=25, min_quantity=10, max_quantity=50,
             part_type="specific", supplier="Home Depot Pro"),
        Part(part_number="SR-3WAY-15", name="3-Way Toggle Switch 15A",
             description="3-way toggle switch, 15A 120V, white",
             category_id=cat_ids["Switches & Receptacles"],
             brand_id=brand_ids["Leviton"],
             brand_part_number="LEV-1453-2W",
             unit_cost=3.25, quantity=75, min_quantity=25, max_quantity=200,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="PB-20SP", name="20-Space Load Center",
             description="20-space 40-circuit 200A main breaker panel",
             category_id=cat_ids["Panels & Breakers"],
             brand_id=brand_ids["Siemens"],
             brand_part_number="SIE-P2040B1200CU",
             unit_cost=189.00, quantity=3, min_quantity=2, max_quantity=6,
             part_type="specific", supplier="Graybar Electric"),
        Part(part_number="PB-BR-20", name="20A Single-Pole Breaker",
             description="20A single-pole circuit breaker, bolt-on",
             category_id=cat_ids["Panels & Breakers"],
             brand_id=brand_ids["Siemens"],
             brand_part_number="SIE-Q120",
             unit_cost=8.75, quantity=40, min_quantity=15, max_quantity=80,
             part_type="general", supplier="Graybar Electric"),
        Part(part_number="PB-BR-15", name="15A Single-Pole Breaker",
             description="15A single-pole circuit breaker, bolt-on",
             category_id=cat_ids["Panels & Breakers"],
             brand_id=brand_ids["Siemens"],
             brand_part_number="SIE-Q115",
             unit_cost=7.50, quantity=50, min_quantity=20, max_quantity=100,
             part_type="general", supplier="Graybar Electric"),
        Part(part_number="PB-GFCI-BR-20", name="20A GFCI Breaker",
             description="20A GFCI circuit breaker, bolt-on",
             category_id=cat_ids["Panels & Breakers"],
             brand_id=brand_ids["Eaton"],
             brand_part_number="EAT-BRGF120",
             unit_cost=42.00, quantity=8, min_quantity=4, max_quantity=20,
             part_type="specific", supplier="Wesco International"),
        Part(part_number="LT-LED-FLAT", name="LED Flat Panel 2x4",
             description="LED flat panel troffer, 2x4, 5000K, 50W",
             category_id=cat_ids["Lighting"],
             brand_id=brand_ids["Eaton"],
             brand_part_number="EAT-FP24-50W",
             unit_cost=65.00, quantity=15, min_quantity=5, max_quantity=30,
             part_type="specific", supplier="Wesco International"),
        Part(part_number="LT-CAN-6", name="6\" LED Recessed Can",
             description="6-inch LED recessed downlight, 3000K, 12W",
             category_id=cat_ids["Lighting"],
             brand_id=brand_ids["Eaton"],
             brand_part_number="EAT-RL6-12W",
             unit_cost=18.50, quantity=35, min_quantity=15, max_quantity=60,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="LT-EXIT-LED", name="LED Exit Sign",
             description="LED exit sign with emergency backup, red letters",
             category_id=cat_ids["Lighting"],
             brand_id=brand_ids["Eaton"],
             brand_part_number="EAT-LXNY-R",
             unit_cost=32.00, quantity=6, min_quantity=3, max_quantity=12,
             part_type="specific", supplier="Platt Electric Supply"),
    ]

    parts_nonbranded = [
        # ── Boxes & Covers ────────────────────────────────────
        Part(part_number="BC-1G-NM", name="1-Gang New Work Box",
             description="Single gang plastic new work electrical box",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=0.65, quantity=300, min_quantity=100, max_quantity=600,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="BC-2G-NM", name="2-Gang New Work Box",
             description="Double gang plastic new work electrical box",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=1.15, quantity=150, min_quantity=50, max_quantity=300,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="BC-3G-NM", name="3-Gang New Work Box",
             description="Triple gang plastic new work electrical box",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=2.10, quantity=60, min_quantity=20, max_quantity=150,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="BC-4S-METAL", name="4\" Square Metal Box",
             description="4 inch square steel junction box, 1-1/2\" deep",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=1.85, quantity=120, min_quantity=40, max_quantity=300,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="BC-4S-DEEP", name="4\" Square Deep Metal Box",
             description="4 inch square steel junction box, 2-1/8\" deep",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=2.45, quantity=80, min_quantity=25, max_quantity=200,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="BC-OCT-NM", name="Octagon Box",
             description="4\" octagon box for ceiling fixtures, NM clamps",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=1.35, quantity=100, min_quantity=30, max_quantity=250,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="BC-1G-OW", name="1-Gang Old Work Box",
             description="Single gang cut-in box for remodel/retrofit",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=1.25, quantity=100, min_quantity=30, max_quantity=250,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="BC-2G-OW", name="2-Gang Old Work Box",
             description="Double gang cut-in box for remodel/retrofit",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=2.35, quantity=50, min_quantity=15, max_quantity=125,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="BC-ROUND-PAN", name="Round Pancake Box",
             description="Round pancake ceiling box, 1/2\" deep",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=2.15, quantity=40, min_quantity=15, max_quantity=100,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="BC-WP-1G", name="Weatherproof 1-Gang Box",
             description="1-gang weatherproof outdoor box, gray",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=4.50, quantity=30, min_quantity=10, max_quantity=80,
             part_type="general", supplier="Home Depot Pro"),
        # ── Cover Plates ──────────────────────────────────────
        Part(part_number="CP-1G-BLANK", name="1-Gang Blank Cover Plate",
             description="1-gang blank wall plate, white",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=0.55, quantity=200, min_quantity=50, max_quantity=500,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="CP-1G-DPLX", name="1-Gang Duplex Cover Plate",
             description="1-gang duplex receptacle wall plate, white",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=0.45, quantity=300, min_quantity=75, max_quantity=600,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="CP-1G-TOGL", name="1-Gang Toggle Cover Plate",
             description="1-gang toggle switch wall plate, white",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=0.45, quantity=250, min_quantity=60, max_quantity=500,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="CP-1G-DECO", name="1-Gang Decora Cover Plate",
             description="1-gang Decora/rocker wall plate, white",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=0.65, quantity=200, min_quantity=50, max_quantity=400,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="CP-2G-DPLX", name="2-Gang Duplex Cover Plate",
             description="2-gang duplex receptacle wall plate, white",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=0.85, quantity=100, min_quantity=25, max_quantity=250,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="CP-2G-TOGL", name="2-Gang Toggle Cover Plate",
             description="2-gang toggle switch wall plate, white",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=0.85, quantity=80, min_quantity=20, max_quantity=200,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="CP-2G-DECO", name="2-Gang Decora Cover Plate",
             description="2-gang Decora/rocker wall plate, white",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=1.05, quantity=80, min_quantity=20, max_quantity=200,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="CP-3G-TOGL", name="3-Gang Toggle Cover Plate",
             description="3-gang toggle switch wall plate, white",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=1.45, quantity=30, min_quantity=10, max_quantity=75,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="CP-4S-FLAT", name="4\" Square Flat Cover",
             description="4\" square flat blank cover plate, steel",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=0.75, quantity=120, min_quantity=30, max_quantity=300,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CP-4S-1G", name="4\" Square 1-Gang Mud Ring",
             description="4\" square to 1-gang plaster/mud ring",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=1.10, quantity=100, min_quantity=25, max_quantity=250,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CP-4S-2G", name="4\" Square 2-Gang Mud Ring",
             description="4\" square to 2-gang plaster/mud ring",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=1.45, quantity=60, min_quantity=15, max_quantity=150,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CP-WP-1G", name="Weatherproof Cover 1-Gang",
             description="Weatherproof in-use cover, 1-gang, clear",
             category_id=cat_ids["Boxes & Covers"],
             unit_cost=5.75, quantity=20, min_quantity=8, max_quantity=50,
             part_type="general", supplier="Home Depot Pro"),
        # ── Wire & Cable extras ───────────────────────────────
        Part(part_number="WC-14-3-250", name="14/3 NM-B Romex 250ft",
             description="14/3 Non-Metallic Sheathed Cable 250ft roll, with ground",
             category_id=cat_ids["Wire & Cable"],
             unit_cost=105.00, quantity=4, min_quantity=2, max_quantity=12,
             part_type="general", supplier="Graybar Electric"),
        Part(part_number="WC-6-3-CU", name="6/3 NM-B Romex 125ft",
             description="6/3 NM-B cable for ranges/dryers, 125ft",
             category_id=cat_ids["Wire & Cable"],
             unit_cost=285.00, quantity=2, min_quantity=1, max_quantity=6,
             part_type="specific", supplier="Graybar Electric"),
        Part(part_number="WC-THHN-12-BLK", name="THHN 12 AWG Black 500ft",
             description="12 AWG THHN stranded copper wire, black, 500ft spool",
             category_id=cat_ids["Wire & Cable"],
             unit_cost=68.00, quantity=6, min_quantity=3, max_quantity=15,
             part_type="general", supplier="Graybar Electric"),
        Part(part_number="WC-THHN-12-WHT", name="THHN 12 AWG White 500ft",
             description="12 AWG THHN stranded copper wire, white, 500ft spool",
             category_id=cat_ids["Wire & Cable"],
             unit_cost=68.00, quantity=6, min_quantity=3, max_quantity=15,
             part_type="general", supplier="Graybar Electric"),
        Part(part_number="WC-THHN-12-RED", name="THHN 12 AWG Red 500ft",
             description="12 AWG THHN stranded copper wire, red, 500ft spool",
             category_id=cat_ids["Wire & Cable"],
             unit_cost=68.00, quantity=4, min_quantity=2, max_quantity=10,
             part_type="general", supplier="Graybar Electric"),
        Part(part_number="WC-THHN-12-GRN", name="THHN 12 AWG Green 500ft",
             description="12 AWG THHN stranded copper wire, green, 500ft spool",
             category_id=cat_ids["Wire & Cable"],
             unit_cost=68.00, quantity=4, min_quantity=2, max_quantity=10,
             part_type="general", supplier="Graybar Electric"),
        Part(part_number="WC-THHN-10-BLK", name="THHN 10 AWG Black 500ft",
             description="10 AWG THHN stranded copper wire, black, 500ft spool",
             category_id=cat_ids["Wire & Cable"],
             unit_cost=98.00, quantity=3, min_quantity=2, max_quantity=8,
             part_type="general", supplier="Graybar Electric"),
        Part(part_number="WC-MC-12-2-250", name="12/2 MC Cable 250ft",
             description="12/2 Metal Clad cable, 250ft coil",
             category_id=cat_ids["Wire & Cable"],
             unit_cost=175.00, quantity=4, min_quantity=2, max_quantity=10,
             part_type="specific", supplier="Graybar Electric"),
        Part(part_number="WC-UF-12-2-250", name="12/2 UF-B Cable 250ft",
             description="12/2 Underground Feeder cable, 250ft",
             category_id=cat_ids["Wire & Cable"],
             unit_cost=135.00, quantity=2, min_quantity=1, max_quantity=6,
             part_type="general", supplier="Graybar Electric"),
        Part(part_number="WC-GND-12", name="Ground Wire 12 AWG 500ft",
             description="12 AWG bare copper ground wire, 500ft spool",
             category_id=cat_ids["Wire & Cable"],
             unit_cost=82.00, quantity=3, min_quantity=2, max_quantity=8,
             part_type="general", supplier="Graybar Electric"),
        # ── Switches & Receptacles extras ─────────────────────
        Part(part_number="SR-SP-TOGL-15", name="Single-Pole Toggle Switch 15A",
             description="Standard single-pole toggle switch, 15A 120V, white",
             category_id=cat_ids["Switches & Receptacles"],
             unit_cost=1.50, quantity=150, min_quantity=40, max_quantity=400,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="SR-DECO-15", name="Decora Rocker Switch 15A",
             description="Single-pole Decora rocker switch, 15A 120V, white",
             category_id=cat_ids["Switches & Receptacles"],
             unit_cost=2.85, quantity=100, min_quantity=30, max_quantity=300,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="SR-DECO-3W-15", name="Decora 3-Way Switch 15A",
             description="3-way Decora rocker switch, 15A, white",
             category_id=cat_ids["Switches & Receptacles"],
             unit_cost=4.50, quantity=50, min_quantity=15, max_quantity=150,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="SR-20A-DPLX", name="Duplex Receptacle 20A",
             description="Commercial grade duplex outlet, 20A 125V, white",
             category_id=cat_ids["Switches & Receptacles"],
             unit_cost=3.50, quantity=80, min_quantity=25, max_quantity=200,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="SR-GFCI-20", name="GFCI Receptacle 20A",
             description="Ground Fault Circuit Interrupter, 20A 125V, white",
             category_id=cat_ids["Switches & Receptacles"],
             unit_cost=19.50, quantity=25, min_quantity=10, max_quantity=60,
             part_type="specific", supplier="City Electric Supply"),
        Part(part_number="SR-WR-15", name="Weather-Resistant Receptacle 15A",
             description="Tamper/weather-resistant duplex outlet for outdoor use",
             category_id=cat_ids["Switches & Receptacles"],
             unit_cost=3.75, quantity=40, min_quantity=15, max_quantity=100,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="SR-USB-DPLX", name="USB Duplex Receptacle",
             description="Duplex outlet with 2x USB-A + 1x USB-C ports",
             category_id=cat_ids["Switches & Receptacles"],
             unit_cost=24.50, quantity=15, min_quantity=5, max_quantity=40,
             part_type="specific", supplier="Home Depot Pro"),
        Part(part_number="SR-DPLX-DED-20", name="Dedicated 20A Outlet",
             description="Single receptacle, 20A 125V, spec-grade, orange",
             category_id=cat_ids["Switches & Receptacles"],
             unit_cost=5.25, quantity=20, min_quantity=8, max_quantity=50,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="SR-DRYER-30", name="Dryer Receptacle 30A",
             description="30A 4-prong dryer outlet, flush mount",
             category_id=cat_ids["Switches & Receptacles"],
             unit_cost=12.50, quantity=5, min_quantity=2, max_quantity=15,
             part_type="specific", supplier="Home Depot Pro"),
        Part(part_number="SR-RANGE-50", name="Range Receptacle 50A",
             description="50A 4-prong range outlet, flush mount",
             category_id=cat_ids["Switches & Receptacles"],
             unit_cost=14.75, quantity=3, min_quantity=2, max_quantity=10,
             part_type="specific", supplier="Home Depot Pro"),
        # ── Conduit & Fittings ────────────────────────────────
        Part(part_number="CF-EMT-075", name="3/4\" EMT Conduit 10ft",
             description="3/4 inch EMT conduit, 10 foot stick",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=4.85, quantity=60, min_quantity=20, max_quantity=120,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CF-CONN-075", name="3/4\" EMT Connector",
             description="3/4 inch EMT compression connector",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=1.20, quantity=100, min_quantity=30, max_quantity=200,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CF-COUP-075", name="3/4\" EMT Coupling",
             description="3/4 inch EMT compression coupling",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=1.05, quantity=80, min_quantity=25, max_quantity=150,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CF-EMT-050", name="1/2\" EMT Conduit 10ft",
             description="1/2 inch EMT conduit, 10 foot stick",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=3.45, quantity=80, min_quantity=25, max_quantity=160,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CF-CONN-050", name="1/2\" EMT Connector",
             description="1/2 inch EMT compression connector",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=0.85, quantity=150, min_quantity=40, max_quantity=300,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CF-EMT-100", name="1\" EMT Conduit 10ft",
             description="1 inch EMT conduit, 10 foot stick",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=7.25, quantity=30, min_quantity=10, max_quantity=60,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CF-LB-075", name="3/4\" LB Conduit Body",
             description="3/4 inch LB conduit body with cover",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=6.50, quantity=15, min_quantity=5, max_quantity=40,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CF-STRAP-075", name="3/4\" 1-Hole Strap",
             description="3/4 inch 1-hole conduit strap, steel",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=0.35, quantity=200, min_quantity=50, max_quantity=500,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CF-PVC-075-10", name="3/4\" PVC Conduit 10ft",
             description="3/4 inch schedule 40 PVC conduit, 10 foot stick",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=3.25, quantity=40, min_quantity=15, max_quantity=80,
             part_type="general", supplier="City Electric Supply"),
        Part(part_number="CF-FLEX-075", name="3/4\" Flex Conduit 25ft",
             description="3/4 inch flexible metal conduit, 25ft roll",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=18.50, quantity=10, min_quantity=4, max_quantity=25,
             part_type="general", supplier="City Electric Supply"),
        # ── Miscellaneous / Consumables ───────────────────────
        Part(part_number="MS-WIRENUTS-YL", name="Wire Nuts Yellow (100pk)",
             description="Yellow wing-type wire connectors, 100-pack",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=7.50, quantity=20, min_quantity=8, max_quantity=50,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="MS-WIRENUTS-RD", name="Wire Nuts Red (100pk)",
             description="Red wing-type wire connectors, 100-pack",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=8.25, quantity=15, min_quantity=6, max_quantity=40,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="MS-TAPE-BLK", name="Electrical Tape Black",
             description="3/4\" x 66ft black vinyl electrical tape",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=2.50, quantity=40, min_quantity=15, max_quantity=100,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="MS-STAPLES-14", name="NM Cable Staples (100pk)",
             description="Cable staples for 14/2 and 12/2 NM cable, 100-pack",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=5.25, quantity=25, min_quantity=10, max_quantity=60,
             part_type="general", supplier="Home Depot Pro"),
        Part(part_number="MS-GROUND-CLIP", name="Ground Clips (50pk)",
             description="Grounding clips for metal boxes, 50-pack",
             category_id=cat_ids["Conduit & Fittings"],
             unit_cost=8.75, quantity=10, min_quantity=4, max_quantity=25,
             part_type="general", supplier="City Electric Supply"),
    ]

    all_parts = parts_branded + parts_nonbranded
    part_ids = {}
    for p in all_parts:
        pid = repo.create_part(p)
        part_ids[p.part_number] = pid
    print(f"  → {len(parts_branded)} branded + {len(parts_nonbranded)} non-branded = "
          f"{len(all_parts)} parts created")

    # ── 6. Trucks ─────────────────────────────────────────────────
    print("Creating trucks...")
    trucks_data = [
        Truck(truck_number="T-01", name="Mike's F-250",
              assigned_user_id=user_ids["admin"]),
        Truck(truck_number="T-02", name="Derek's Transit",
              assigned_user_id=user_ids["derek"]),
        Truck(truck_number="T-03", name="José's Ram 2500",
              assigned_user_id=user_ids["jose"]),
        Truck(truck_number="T-04", name="Kevin's Sprinter",
              assigned_user_id=user_ids["kevin"]),
        Truck(truck_number="T-05", name="Carlos's ProMaster",
              assigned_user_id=user_ids["carlos"]),
        Truck(truck_number="T-06", name="Spare Truck",
              assigned_user_id=None),
        Truck(truck_number="T-07", name="Jake's Ranger",
              assigned_user_id=user_ids["jake"]),
    ]
    truck_ids = {}
    for t in trucks_data:
        tid = repo.create_truck(t)
        truck_ids[t.truck_number] = tid
    print(f"  → {len(trucks_data)} trucks created")

    # Stock each truck with common parts
    print("Stocking trucks...")
    stock_plan = {
        "T-01": [("SR-DPLX-15", 20), ("SR-GFCI-15", 5), ("SR-3WAY-15", 8),
                 ("SR-SP-TOGL-15", 10), ("BC-1G-NM", 30), ("BC-2G-NM", 15),
                 ("BC-1G-OW", 10), ("CP-1G-DPLX", 25), ("CP-1G-TOGL", 15),
                 ("CP-1G-BLANK", 10), ("PB-BR-20", 4), ("PB-BR-15", 6),
                 ("WC-14-250", 2), ("MS-WIRENUTS-YL", 3), ("MS-TAPE-BLK", 4)],
        "T-02": [("SR-DPLX-15", 15), ("SR-GFCI-15", 4), ("SR-DIMM-LED", 3),
                 ("SR-DECO-15", 8), ("BC-1G-NM", 25), ("BC-4S-METAL", 10),
                 ("CP-1G-DECO", 15), ("CP-4S-FLAT", 10),
                 ("CF-EMT-075", 10), ("CF-CONN-075", 15), ("CF-STRAP-075", 20),
                 ("LT-CAN-6", 6), ("MS-WIRENUTS-RD", 2)],
        "T-03": [("SR-DPLX-15", 25), ("SR-AFCI-15", 6), ("SR-3WAY-15", 10),
                 ("SR-20A-DPLX", 8), ("BC-1G-NM", 40), ("BC-2G-NM", 20),
                 ("BC-3G-NM", 5), ("CP-1G-DPLX", 30), ("CP-2G-DPLX", 10),
                 ("WC-12-250", 2), ("WC-THHN-12-BLK", 1),
                 ("PB-BR-20", 6), ("PB-BR-15", 8), ("MS-STAPLES-14", 3)],
        "T-04": [("SR-DPLX-15", 10), ("SR-GFCI-15", 3), ("BC-1G-NM", 20),
                 ("BC-4S-DEEP", 8), ("CP-1G-DPLX", 15), ("CP-4S-1G", 8),
                 ("CF-EMT-075", 8), ("CF-EMT-050", 10), ("CF-CONN-075", 10),
                 ("CF-CONN-050", 12), ("CF-COUP-075", 8), ("CF-LB-075", 3),
                 ("MS-TAPE-BLK", 3)],
        "T-05": [("SR-DPLX-15", 12), ("SR-GFCI-15", 3), ("SR-DIMM-LED", 2),
                 ("SR-USB-DPLX", 2), ("BC-1G-NM", 20), ("BC-OCT-NM", 8),
                 ("CP-1G-DECO", 12), ("CP-1G-DPLX", 10),
                 ("LT-CAN-6", 8), ("LT-LED-FLAT", 2), ("MS-WIRENUTS-YL", 2)],
        "T-06": [("SR-DPLX-15", 5), ("BC-1G-NM", 10), ("CP-1G-DPLX", 5),
                 ("MS-TAPE-BLK", 2)],
        "T-07": [("SR-DPLX-15", 8), ("SR-SP-TOGL-15", 5), ("BC-1G-NM", 15),
                 ("BC-1G-OW", 5), ("CP-1G-DPLX", 8), ("CP-1G-TOGL", 5),
                 ("CF-CONN-075", 5), ("MS-WIRENUTS-YL", 1)],
    }
    stocked = 0
    for truck_num, items in stock_plan.items():
        tid = truck_ids[truck_num]
        for pn, qty in items:
            repo.add_to_truck_inventory(tid, part_ids[pn], qty)
            stocked += 1
    print(f"  → {stocked} truck inventory entries created")

    # ── 7. Jobs ───────────────────────────────────────────────────
    print("Creating jobs...")
    jobs_data = [
        Job(job_number="J-2025-001", name="Highland Park Residence",
            customer="Thompson Family",
            address="4521 Abbott Ave, Dallas TX 75205",
            status="active", priority=2, bill_out_rate="T&M",
            notes="Full house rewire, 3-story, 4200 sq ft"),
        Job(job_number="J-2025-002", name="Preston Hollow Addition",
            customer="Garcia Estate",
            address="6200 Royal Ln, Dallas TX 75230",
            status="active", priority=2, bill_out_rate="C",
            notes="New addition — 2 bedrooms, 1 bath, media room"),
        Job(job_number="J-2025-003", name="Oak Lawn Office TI",
            customer="Metro Cowork",
            address="3300 Oaklawn Ave #200, Dallas TX 75219",
            status="active", priority=3, bill_out_rate="T&M",
            notes="Tenant improvement, open office + 4 private offices"),
        Job(job_number="J-2025-004", name="Service Call — Panel Upgrade",
            customer="Williams",
            address="1812 Swiss Ave, Dallas TX 75204",
            status="active", priority=1, bill_out_rate="SERVICE",
            notes="200A panel upgrade, replace Federal Pacific panel"),
        Job(job_number="J-2025-005", name="Lakewood Renovation",
            customer="Patel Family",
            address="6830 Tokalon Dr, Dallas TX 75214",
            status="active", priority=3, bill_out_rate="C",
            notes="Kitchen/bath reno, add circuits, LED retrofit"),
    ]
    job_ids = {}
    for j in jobs_data:
        jid = repo.create_job(j)
        job_ids[j.job_number] = jid
    print(f"  → {len(jobs_data)} jobs created")

    # ── 8. Purchase Orders (17 total, mixed statuses) ─────────────
    print("Creating purchase orders...")
    graybar_id = supplier_ids["Graybar Electric"]
    homedepot_id = supplier_ids["Home Depot Pro"]
    cityelectric_id = supplier_ids["City Electric Supply"]
    wesco_id = supplier_ids["Wesco International"]
    platt_id = supplier_ids["Platt Electric Supply"]

    orders_config = [
        # Draft orders
        ("PO-2025-001", graybar_id, "draft",
         [("WC-14-250", 10, 78.50), ("WC-12-250", 6, 98.75), ("WC-10-100", 4, 115.00)]),
        ("PO-2025-002", homedepot_id, "draft",
         [("SR-DPLX-15", 100, 1.85), ("SR-3WAY-15", 30, 3.25)]),
        ("PO-2025-003", cityelectric_id, "draft",
         [("SR-GFCI-15", 25, 16.50), ("SR-AFCI-15", 15, 28.50)]),
        # Submitted orders
        ("PO-2025-004", graybar_id, "submitted",
         [("PB-20SP", 3, 189.00), ("PB-BR-20", 20, 8.75), ("PB-BR-15", 30, 7.50)]),
        ("PO-2025-005", homedepot_id, "submitted",
         [("SR-DIMM-LED", 15, 22.75), ("LT-CAN-6", 20, 18.50)]),
        ("PO-2025-006", wesco_id, "submitted",
         [("PB-GFCI-BR-20", 10, 42.00), ("LT-LED-FLAT", 8, 65.00)]),
        ("PO-2025-007", cityelectric_id, "submitted",
         [("CF-EMT-075", 40, 4.85), ("CF-CONN-075", 50, 1.20), ("CF-COUP-075", 40, 1.05)]),
        # Partial (some items received)
        ("PO-2025-008", graybar_id, "partial",
         [("WC-14-250", 5, 78.50), ("PB-BR-20", 10, 8.75)]),
        ("PO-2025-009", homedepot_id, "partial",
         [("BC-1G-NM", 200, 0.65), ("BC-2G-NM", 100, 1.15)]),
        ("PO-2025-010", cityelectric_id, "partial",
         [("SR-GFCI-15", 15, 16.50)]),
        # Received orders
        ("PO-2025-011", graybar_id, "received",
         [("WC-14-250", 8, 78.50), ("WC-12-250", 5, 98.75)]),
        ("PO-2025-012", homedepot_id, "received",
         [("SR-DPLX-15", 50, 1.85), ("BC-1G-NM", 100, 0.65)]),
        ("PO-2025-013", wesco_id, "received",
         [("LT-LED-FLAT", 10, 65.00)]),
        ("PO-2025-014", platt_id, "received",
         [("LT-EXIT-LED", 6, 32.00)]),
        # Closed orders
        ("PO-2025-015", graybar_id, "closed",
         [("PB-20SP", 2, 189.00), ("PB-BR-20", 15, 8.75)]),
        ("PO-2025-016", homedepot_id, "closed",
         [("SR-DPLX-15", 75, 1.85), ("SR-3WAY-15", 20, 3.25)]),
        # Cancelled order
        ("PO-2025-017", platt_id, "cancelled",
         [("LT-EXIT-LED", 10, 32.00)]),
    ]

    for order_num, sid, status, items in orders_config:
        po = PurchaseOrder(
            order_number=order_num,
            supplier_id=sid,
            status=status,
            created_by=admin_id,
            notes=f"Mock order — {status}",
        )
        oid = repo.create_purchase_order(po)
        for pn, qty, cost in items:
            item = PurchaseOrderItem(
                order_id=oid,
                part_id=part_ids[pn],
                quantity_ordered=qty,
                unit_cost=cost,
            )
            repo.add_order_item(item)

    print(f"  → {len(orders_config)} purchase orders created")

    # ── Done ──────────────────────────────────────────────────────
    print("\n✓ Mock data seeded successfully!")
    print(f"  Users: {len(users)} (all PIN {PIN})")
    print(f"  Parts: {len(all_parts)} ({len(parts_branded)} branded)")
    print(f"  Trucks: {len(trucks_data)}")
    print(f"  Jobs: {len(jobs_data)}")
    print(f"  Orders: {len(orders_config)}")
    print(f"  Suppliers: {len(suppliers_data)}")


def main():
    from wired_part.config import Config
    db_path = Config.DATABASE_PATH
    print(f"Database: {db_path}")

    # Confirm if DB exists
    if os.path.exists(db_path):
        resp = input("Database already exists. Seed anyway? (y/N): ").strip().lower()
        if resp != "y":
            print("Aborted.")
            return

    db = DatabaseConnection(db_path)
    repo = Repository(db)
    seed(repo)


if __name__ == "__main__":
    main()
