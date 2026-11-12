"""Synthetic Data Generator Agent and Seed Pipeline for MediFlux Supply Chain."""

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.api.v1.endpoints.inventory import DEFAULT_INVENTORY
from app.api.v1.endpoints.nodes import DEFAULT_NODES
from app.api.v1.endpoints.products import DEFAULT_PRODUCTS
from app.core.security import get_service_db_client
from app.events.service import set_in_memory_stock

logger = logging.getLogger("mediflux.agents.seed")

NAMESPACE_MEDIFLUX = uuid.UUID("a3b4c5d6-e7f8-4a5b-9c0d-1e2f3a4b5c6d")


def deterministic_uuid(entity_type: str, identifier: str) -> str:
    """Generate deterministic, reproducible UUID v5 for supply chain entities."""
    return str(uuid.uuid5(NAMESPACE_MEDIFLUX, f"mediflux:{entity_type}:{identifier}"))


class SyntheticNode(BaseModel):
    id: str
    tier: str
    name: str
    region: str
    parent_id: str | None = None
    address: str | None = None
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=lambda: {"is_synthetic": True})


class SyntheticProduct(BaseModel):
    id: str
    sku: str
    name: str
    generic_name: str
    schedule_class: str = "GENERAL"
    is_cold_chain: bool = False
    storage_min_c: float | None = None
    storage_max_c: float | None = None
    is_lifesaving: bool = False
    unit: str = "strip"
    price_per_unit: float
    metadata: dict[str, Any] = Field(default_factory=lambda: {"is_synthetic": True})


class SyntheticBatch(BaseModel):
    id: str
    product_id: str
    manufacturer_id: str
    batch_no: str
    mfg_date: str
    expiry_date: str
    status: str = "active"
    initial_quantity: int
    metadata: dict[str, Any] = Field(default_factory=lambda: {"is_synthetic": True})


class SyntheticInventory(BaseModel):
    id: str
    node_id: str
    product_id: str
    batch_id: str
    quantity: int
    reserved: int = 0
    safety_stock: int = 10
    metadata: dict[str, Any] = Field(default_factory=lambda: {"is_synthetic": True})


class SyntheticCreditAccount(BaseModel):
    id: str
    node_id: str
    credit_limit: float
    used_credit: float
    credit_score: int
    metadata: dict[str, Any] = Field(default_factory=lambda: {"is_synthetic": True})


class SyntheticFleetVehicle(BaseModel):
    id: str
    distributor_id: str
    vehicle_number: str
    vehicle_type: str
    is_reefer: bool
    temperature_capacity_min: float | None = None
    temperature_capacity_max: float | None = None
    is_available: bool = True
    metadata: dict[str, Any] = Field(default_factory=lambda: {"is_synthetic": True})


class SyntheticProductionLine(BaseModel):
    id: str
    plant_id: str
    line_code: str
    capacity_per_day: int
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=lambda: {"is_synthetic": True})


class SyntheticApiInventory(BaseModel):
    id: str
    manufacturer_id: str
    ingredient_name: str
    quantity: float
    unit: str = "kg"
    reorder_level: float
    metadata: dict[str, Any] = Field(default_factory=lambda: {"is_synthetic": True})


class SeedAgent:
    """Agent that creates structured, deterministic synthetic data for the 4-tier supply chain."""

    def __init__(self, fixtures_dir: str | Path | None = None) -> None:
        self.fixtures_dir = self._find_fixtures_dir(fixtures_dir)

    def _find_fixtures_dir(self, custom_path: str | Path | None) -> Path:
        candidates = [
            Path(custom_path) if custom_path else None,
            Path("fixtures"),
            Path("backend/fixtures"),
            Path(__file__).parent.parent.parent / "fixtures",
            Path(__file__).parent.parent.parent.parent / "fixtures",
        ]
        for p in candidates:
            if p and p.is_dir() and (p / "drug_schedules.json").is_file():
                return p
        return Path("fixtures")

    def load_drug_schedules(self) -> list[dict[str, Any]]:
        """Load human-verified pharmaceutical schedules."""
        file_path = self.fixtures_dir / "drug_schedules.json"
        if not file_path.is_file():
            # Fallback check
            alt = Path("fixtures/drug_schedules.json")
            if alt.is_file():
                file_path = alt
            else:
                alt2 = Path("backend/fixtures/drug_schedules.json")
                if alt2.is_file():
                    file_path = alt2
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)

    def load_doctor_registry(self) -> list[dict[str, Any]]:
        """Load curated mock doctor registry."""
        file_path = self.fixtures_dir / "doctor_registry.json"
        if not file_path.is_file():
            alt = Path("fixtures/doctor_registry.json")
            if alt.is_file():
                file_path = alt
            else:
                alt2 = Path("backend/fixtures/doctor_registry.json")
                if alt2.is_file():
                    file_path = alt2
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)

    def generate_topology(self) -> list[SyntheticNode]:
        """Generate full 4-tier network nodes: 2 Manufacturers, 3 Distributors, 5 Stockists, 15 Pharmacies."""
        nodes: list[SyntheticNode] = []

        # 1. Manufacturers (2)
        mfg1_id = deterministic_uuid("node", "mfg-alpha-pharma")
        mfg2_id = deterministic_uuid("node", "mfg-apex-bio")
        nodes.extend([
            SyntheticNode(
                id=mfg1_id,
                tier="manufacturer",
                name="Alpha Pharma Mfg - Plant Baddi",
                region="North",
                parent_id=None,
                address="Plot 12-14, Industrial Area, Baddi, Himachal Pradesh 173205",
                metadata={"is_synthetic": True, "tier": "manufacturer"},
            ),
            SyntheticNode(
                id=mfg2_id,
                tier="manufacturer",
                name="Apex Bio Labs - Plant Sanand",
                region="West",
                parent_id=None,
                address="GIDC Estate, Sanand, Ahmedabad, Gujarat 382110",
                metadata={"is_synthetic": True, "tier": "manufacturer"},
            ),
        ])

        # 2. Regional Distributors (3)
        dist_metro_id = deterministic_uuid("node", "dist-metro-logistics")
        dist_west_id = deterministic_uuid("node", "dist-west-logistics")
        dist_south_id = deterministic_uuid("node", "dist-south-logistics")
        nodes.extend([
            SyntheticNode(
                id=dist_metro_id,
                tier="distributor",
                name="Metro Logistics Hub - North Depot",
                region="North",
                parent_id=mfg1_id,
                address="Sector 18, Udyog Vihar, Gurugram, Haryana 122015",
                metadata={"is_synthetic": True, "tier": "distributor"},
            ),
            SyntheticNode(
                id=dist_west_id,
                tier="distributor",
                name="West Coast Pharma Logistics Depot",
                region="West",
                parent_id=mfg2_id,
                address="Bhiwandi Logistics Park, Thane, Maharashtra 421302",
                metadata={"is_synthetic": True, "tier": "distributor"},
            ),
            SyntheticNode(
                id=dist_south_id,
                tier="distributor",
                name="South Regional Distribution Hub",
                region="South",
                parent_id=mfg1_id,
                address="Electronic City Phase II, Bengaluru, Karnataka 560100",
                metadata={"is_synthetic": True, "tier": "distributor"},
            ),
        ])

        # 3. Stockists / Wholesalers (5)
        stk1_id = deterministic_uuid("node", "stk-delhi-central")
        stk2_id = deterministic_uuid("node", "stk-mumbai-west")
        stk3_id = deterministic_uuid("node", "stk-bengaluru-south")
        stk4_id = deterministic_uuid("node", "stk-kolkata-east")
        stk5_id = deterministic_uuid("node", "stk-ahmedabad-central")

        nodes.extend([
            SyntheticNode(
                id=stk1_id,
                tier="stockist",
                name="Delhi Central Med Stockists",
                region="North",
                parent_id=dist_metro_id,
                address="Bhagirath Palace, Chandni Chowk, Delhi 110006",
                metadata={"is_synthetic": True, "tier": "stockist"},
            ),
            SyntheticNode(
                id=stk2_id,
                tier="stockist",
                name="Mumbai West Pharma Stockists",
                region="West",
                parent_id=dist_west_id,
                address="Princess Street, Marine Lines, Mumbai 400002",
                metadata={"is_synthetic": True, "tier": "stockist"},
            ),
            SyntheticNode(
                id=stk3_id,
                tier="stockist",
                name="Bengaluru South Wholesalers",
                region="South",
                parent_id=dist_south_id,
                address="Sultanpet Main Road, Bengaluru, Karnataka 560053",
                metadata={"is_synthetic": True, "tier": "stockist"},
            ),
            SyntheticNode(
                id=stk4_id,
                tier="stockist",
                name="Kolkata East Med Distributors",
                region="East",
                parent_id=dist_metro_id,
                address="Canning Street, BBD Bagh, Kolkata, West Bengal 700001",
                metadata={"is_synthetic": True, "tier": "stockist"},
            ),
            SyntheticNode(
                id=stk5_id,
                tier="stockist",
                name="Ahmedabad Central Stockists",
                region="West",
                parent_id=dist_west_id,
                address="Relief Road, Kalupur, Ahmedabad, Gujarat 380001",
                metadata={"is_synthetic": True, "tier": "stockist"},
            ),
        ])

        # 4. Retail Pharmacies (~15) across 5 regional stockists (3 per stockist)
        pharmacy_specs = [
            # Delhi / North (stk1)
            ("pharm-del-01", "Apollo Pharmacy - CP Inner Circle", "North", stk1_id, "Connaught Place, New Delhi 110001"),
            ("pharm-del-02", "MedPlus Pharmacy - Rohini Sector 7", "North", stk1_id, "Sector 7, Rohini, Delhi 110085"),
            ("pharm-del-03", "Fortis Health Retail - Saket", "North", stk1_id, "Press Enclave Marg, Saket, New Delhi 110017"),
            # Mumbai / West (stk2)
            ("pharm-mum-01", "Noble Chemist - Andheri West", "West", stk2_id, "SV Road, Andheri West, Mumbai 400058"),
            ("pharm-mum-02", "Wellness Forever - Bandra Linking Rd", "West", stk2_id, "Linking Road, Bandra West, Mumbai 400050"),
            ("pharm-mum-03", "Dhanvantari Med Store - Dadar TT", "West", stk2_id, "Dadar TT Circle, Mumbai 400014"),
            # Bengaluru / South (stk3)
            ("pharm-blr-01", "Aster Pharmacy - Indiranagar 100ft", "South", stk3_id, "100 Feet Rd, Indiranagar, Bengaluru 560038"),
            ("pharm-blr-02", "Trust Chemist - Koramangala 5th Block", "South", stk3_id, "Koramangala 5th Block, Bengaluru 560095"),
            ("pharm-blr-03", "Health & Glow Meds - Whitefield", "South", stk3_id, "ITPB Main Rd, Whitefield, Bengaluru 560066"),
            # Kolkata / East (stk4)
            ("pharm-kol-01", "Frank Ross Pharmacy - Park Street", "East", stk4_id, "Park Street, Kolkata 700016"),
            ("pharm-kol-02", "Blue Cross Pharma - Salt Lake Sec 1", "East", stk4_id, "Sector 1, Salt Lake, Kolkata 700064"),
            ("pharm-kol-03", "City Medicos - Howrah Station Road", "East", stk4_id, "Station Road, Howrah 711101"),
            # Ahmedabad / West (stk5)
            ("pharm-amd-01", "Sanjivani Pharmacy - Navrangpura", "West", stk5_id, "CG Road, Navrangpura, Ahmedabad 380009"),
            ("pharm-amd-02", "Lifeline Chemist - Vastrapur Lake", "West", stk5_id, "Vastrapur Lake Road, Ahmedabad 380015"),
            ("pharm-amd-03", "Gujarat Med Store - Maninagar Cross", "West", stk5_id, "Maninagar Char Rasta, Ahmedabad 380008"),
        ]

        for p_code, p_name, p_region, p_parent, p_addr in pharmacy_specs:
            nodes.append(
                SyntheticNode(
                    id=deterministic_uuid("node", p_code),
                    tier="pharmacy",
                    name=p_name,
                    region=p_region,
                    parent_id=p_parent,
                    address=p_addr,
                    metadata={"is_synthetic": True, "tier": "pharmacy", "code": p_code},
                )
            )

        return nodes

    def generate_products(self) -> list[SyntheticProduct]:
        """Generate verified products directly from curated drug schedules fixture."""
        schedules = self.load_drug_schedules()
        products: list[SyntheticProduct] = []

        schedule_map = {
            "Schedule H": "SCHEDULE_H",
            "Schedule H1": "SCHEDULE_H1",
            "Schedule G": "SCHEDULE_H",
            "OTC": "OTC",
            "Narcotic": "SCHEDULE_X",
        }

        for item in schedules:
            sku = item["sku"]
            prod_id = deterministic_uuid("product", sku)
            sched_type = item.get("schedule_type", "OTC")
            sched_class = schedule_map.get(sched_type, "GENERAL")
            ceiling = float(item.get("neml_ceiling_price", 25.0))
            price = round(ceiling * 0.92, 2)  # Retail selling price slightly below DPCO ceiling

            # Extract generic name by removing strength and dosage form suffixes
            name_tokens = item["product_name"].split(" ")
            filtered_tokens = [
                w for w in name_tokens
                if not any(c.isdigit() for c in w) and w.lower() not in ("tablets", "capsules", "injection", "syrup", "vials", "drops")
            ]
            derived_generic_name = " ".join(filtered_tokens) if filtered_tokens else name_tokens[0]

            products.append(
                SyntheticProduct(
                    id=prod_id,
                    sku=sku,
                    name=item["product_name"],
                    generic_name=derived_generic_name,
                    schedule_class=sched_class,
                    is_cold_chain=bool(item.get("is_cold_chain", False)),
                    storage_min_c=item.get("min_temp_celsius"),
                    storage_max_c=item.get("max_temp_celsius"),
                    is_lifesaving=sched_class in ("SCHEDULE_X", "SCHEDULE_H1") or bool(item.get("is_cold_chain")),
                    unit="vial" if item.get("is_cold_chain") else "strip",
                    price_per_unit=price,
                    metadata={
                        "is_synthetic": True,
                        "category": item.get("category", "general"),
                        "schedule_type": sched_type,
                        "requires_prescription": item.get("requires_prescription", False),
                        "neml_ceiling_price": ceiling,
                    },
                )
            )
        return products

    def generate_batches(
        self, products: list[SyntheticProduct], nodes: list[SyntheticNode]
    ) -> list[SyntheticBatch]:
        """Generate batches associated with manufacturers."""
        manufacturers = [n for n in nodes if n.tier == "manufacturer"]
        mfg1_id = manufacturers[0].id if manufacturers else deterministic_uuid("node", "mfg-alpha-pharma")
        mfg2_id = manufacturers[1].id if len(manufacturers) > 1 else mfg1_id

        batches: list[SyntheticBatch] = []
        for idx, prod in enumerate(products):
            mfg_id = mfg1_id if idx % 2 == 0 else mfg2_id

            # Batch 1 (Standard Active Batch)
            b1_no = f"B26-{prod.sku.replace('MED-', '')}-01"
            batches.append(
                SyntheticBatch(
                    id=deterministic_uuid("batch", f"{prod.sku}:01"),
                    product_id=prod.id,
                    manufacturer_id=mfg_id,
                    batch_no=b1_no,
                    mfg_date="2026-01-10",
                    expiry_date="2027-12-31",
                    status="active",
                    initial_quantity=25000,
                    metadata={"is_synthetic": True, "batch_index": 1},
                )
            )

            # Batch 2 (Secondary Batch)
            b2_no = f"B26-{prod.sku.replace('MED-', '')}-02"
            batches.append(
                SyntheticBatch(
                    id=deterministic_uuid("batch", f"{prod.sku}:02"),
                    product_id=prod.id,
                    manufacturer_id=mfg_id,
                    batch_no=b2_no,
                    mfg_date="2026-02-15",
                    expiry_date="2028-06-30",
                    status="active",
                    initial_quantity=15000,
                    metadata={"is_synthetic": True, "batch_index": 2},
                )
            )

        return batches

    def generate_inventory(
        self,
        nodes: list[SyntheticNode],
        products: list[SyntheticProduct],
        batches: list[SyntheticBatch],
    ) -> list[SyntheticInventory]:
        """Generate inventory allocations across all tiers."""
        inventory: list[SyntheticInventory] = []
        product_batches: dict[str, list[SyntheticBatch]] = {}
        for b in batches:
            product_batches.setdefault(b.product_id, []).append(b)

        for node in nodes:
            tier = node.tier
            # Determine stock parameters per tier
            if tier == "pharmacy":
                # Pharmacies carry first batch of 15 products
                target_products = products[:15]
                qty, safety = 80, 15
            elif tier == "stockist":
                target_products = products
                qty, safety = 800, 100
            elif tier == "distributor":
                target_products = products
                qty, safety = 5000, 500
            elif tier == "manufacturer":
                target_products = products
                qty, safety = 20000, 2000
            else:
                target_products = []
                qty, safety = 50, 10

            for prod in target_products:
                p_batches = product_batches.get(prod.id, [])
                if not p_batches:
                    continue
                # Assign to primary batch
                primary_batch = p_batches[0]
                inv_id = deterministic_uuid("inv", f"{node.id}:{prod.id}:{primary_batch.id}")
                inventory.append(
                    SyntheticInventory(
                        id=inv_id,
                        node_id=node.id,
                        product_id=prod.id,
                        batch_id=primary_batch.id,
                        quantity=qty,
                        reserved=0,
                        safety_stock=safety,
                        metadata={"is_synthetic": True, "tier": tier},
                    )
                )

        return inventory

    def generate_credit_accounts(self, nodes: list[SyntheticNode]) -> list[SyntheticCreditAccount]:
        """Generate credit limits and balance records."""
        accounts: list[SyntheticCreditAccount] = []
        tier_credit = {
            "pharmacy": (150000.0, 18500.0, 750),
            "stockist": (1500000.0, 220000.0, 810),
            "distributor": (8000000.0, 1100000.0, 840),
            "manufacturer": (50000000.0, 0.0, 890),
        }

        for node in nodes:
            limit, used, score = tier_credit.get(node.tier, (100000.0, 0.0, 700))
            accounts.append(
                SyntheticCreditAccount(
                    id=deterministic_uuid("credit", node.id),
                    node_id=node.id,
                    credit_limit=limit,
                    used_credit=used,
                    credit_score=score,
                    metadata={"is_synthetic": True, "tier": node.tier},
                )
            )
        return accounts

    def generate_fleet_vehicles(self, nodes: list[SyntheticNode]) -> list[SyntheticFleetVehicle]:
        """Generate transport fleet vehicles for distributors."""
        distributors = [n for n in nodes if n.tier == "distributor"]
        vehicles: list[SyntheticFleetVehicle] = []

        for idx, dist in enumerate(distributors):
            prefix = ["DL", "MH", "KA"][idx % 3]
            # Reefer cold-chain van
            v1_no = f"{prefix}-01-RF-{1000 + idx}"
            vehicles.append(
                SyntheticFleetVehicle(
                    id=deterministic_uuid("vehicle", v1_no),
                    distributor_id=dist.id,
                    vehicle_number=v1_no,
                    vehicle_type="Refrigerated Reefer Van 3.5T",
                    is_reefer=True,
                    temperature_capacity_min=2.0,
                    temperature_capacity_max=8.0,
                    is_available=True,
                    metadata={"is_synthetic": True, "distributor": dist.name},
                )
            )
            # Ambient delivery truck
            v2_no = f"{prefix}-01-TR-{2000 + idx}"
            vehicles.append(
                SyntheticFleetVehicle(
                    id=deterministic_uuid("vehicle", v2_no),
                    distributor_id=dist.id,
                    vehicle_number=v2_no,
                    vehicle_type="Ambient Freight Truck 7.5T",
                    is_reefer=False,
                    temperature_capacity_min=15.0,
                    temperature_capacity_max=30.0,
                    is_available=True,
                    metadata={"is_synthetic": True, "distributor": dist.name},
                )
            )

        return vehicles

    def generate_manufacturing_assets(
        self, nodes: list[SyntheticNode]
    ) -> tuple[list[SyntheticProductionLine], list[SyntheticApiInventory]]:
        """Generate production lines and Active Pharmaceutical Ingredient (API) inventory."""
        manufacturers = [n for n in nodes if n.tier == "manufacturer"]
        lines: list[SyntheticProductionLine] = []
        api_items: list[SyntheticApiInventory] = []

        for idx, mfg in enumerate(manufacturers):
            l1_code = f"LINE-{idx + 1}-SOLIDS"
            l2_code = f"LINE-{idx + 1}-INJECT"

            lines.append(
                SyntheticProductionLine(
                    id=deterministic_uuid("line", f"{mfg.id}:{l1_code}"),
                    plant_id=mfg.id,
                    line_code=l1_code,
                    capacity_per_day=80000,
                    is_active=True,
                    metadata={"is_synthetic": True, "dosage_form": "tablets_capsules"},
                )
            )
            lines.append(
                SyntheticProductionLine(
                    id=deterministic_uuid("line", f"{mfg.id}:{l2_code}"),
                    plant_id=mfg.id,
                    line_code=l2_code,
                    capacity_per_day=25000,
                    is_active=True,
                    metadata={"is_synthetic": True, "dosage_form": "injectables_vials"},
                )
            )

            # API Ingredients
            ingredients = [
                ("Amoxicillin Trihydrate IP", 750.0, 150.0),
                ("Azithromycin Dihydrate IP", 400.0, 80.0),
                ("Paracetamol Granules USP", 1500.0, 300.0),
                ("Metformin HCl Raw Material", 1000.0, 200.0),
            ]
            for ing_name, qty, reorder in ingredients:
                api_items.append(
                    SyntheticApiInventory(
                        id=deterministic_uuid("api", f"{mfg.id}:{ing_name}"),
                        manufacturer_id=mfg.id,
                        ingredient_name=ing_name,
                        quantity=qty,
                        unit="kg",
                        reorder_level=reorder,
                        metadata={"is_synthetic": True, "purity_grade": "Pharma Grade 99.8%"},
                    )
                )

        return lines, api_items

    def generate_all(self) -> dict[str, list[Any]]:
        """Generate the complete synthetic supply chain network dataset."""
        nodes = self.generate_topology()
        products = self.generate_products()
        batches = self.generate_batches(products, nodes)
        inventory = self.generate_inventory(nodes, products, batches)
        credit = self.generate_credit_accounts(nodes)
        vehicles = self.generate_fleet_vehicles(nodes)
        lines, api_items = self.generate_manufacturing_assets(nodes)

        return {
            "nodes": [n.model_dump() for n in nodes],
            "products": [p.model_dump() for p in products],
            "batches": [b.model_dump() for b in batches],
            "inventory": [i.model_dump() for i in inventory],
            "credit_accounts": [c.model_dump() for c in credit],
            "fleet_vehicles": [v.model_dump() for v in vehicles],
            "production_lines": [pline.model_dump() for pline in lines],
            "api_inventory": [a.model_dump() for a in api_items],
        }

    def seed_database(self, supabase_client: Any = None) -> dict[str, int]:
        """Seed generated synthetic data into Supabase (if connected) and in-memory caches.

        Idempotent: Uses deterministic UUIDs and upsert logic.
        """
        data = self.generate_all()
        client = supabase_client or get_service_db_client()
        counts: dict[str, int] = {}

        # 1. Update in-memory state for API endpoints and test runtimes
        # Sync DEFAULT_NODES
        DEFAULT_NODES.clear()
        for n in data["nodes"]:
            DEFAULT_NODES.append({
                "id": n["id"],
                "tier": n["tier"],
                "name": n["name"],
                "region": n["region"],
                "parent_id": n["parent_id"],
                "address": n["address"],
                "is_active": n["is_active"],
            })

        # Sync DEFAULT_PRODUCTS
        DEFAULT_PRODUCTS.clear()
        for p in data["products"]:
            DEFAULT_PRODUCTS.append({
                "id": p["id"],
                "name": p["name"],
                "generic_name": p["generic_name"],
                "schedule_class": p["schedule_class"],
                "is_cold_chain": p["is_cold_chain"],
                "storage_min_c": p["storage_min_c"],
                "storage_max_c": p["storage_max_c"],
                "is_lifesaving": p["is_lifesaving"],
                "unit": p["unit"],
                "price_per_unit": p["price_per_unit"],
            })

        # Sync DEFAULT_INVENTORY & _in_memory_inventory in events.service
        DEFAULT_INVENTORY.clear()
        for inv in data["inventory"]:
            DEFAULT_INVENTORY.append({
                "id": inv["id"],
                "node_id": inv["node_id"],
                "product_id": inv["product_id"],
                "batch_id": inv["batch_id"],
                "quantity": inv["quantity"],
                "reserved": inv["reserved"],
                "safety_stock": inv["safety_stock"],
            })
            set_in_memory_stock(
                pharmacy_id=inv["node_id"],
                product_id=inv["product_id"],
                batch_id=inv["batch_id"],
                quantity=inv["quantity"],
            )

        # 2. Persist to Supabase if connected
        if client:
            table_order = [
                ("nodes", data["nodes"]),
                ("products", data["products"]),
                ("batches", data["batches"]),
                ("inventory", data["inventory"]),
                ("credit_accounts", data["credit_accounts"]),
                ("fleet_vehicles", data["fleet_vehicles"]),
                ("production_lines", data["production_lines"]),
                ("api_inventory", data["api_inventory"]),
            ]
            for table_name, records in table_order:
                try:
                    # Upsert records using on_conflict="id"
                    res = client.table(table_name).upsert(records, on_conflict="id").execute()
                    counts[table_name] = len(res.data) if hasattr(res, "data") and res.data else len(records)
                except Exception as exc:
                    logger.warning("Supabase upsert into [%s] skipped/failed: %s", table_name, exc)
                    counts[table_name] = len(records)
        else:
            for k, v in data.items():
                counts[k] = len(v)

        logger.info("Seed completed: %s", counts)
        return counts


seed_agent = SeedAgent()
