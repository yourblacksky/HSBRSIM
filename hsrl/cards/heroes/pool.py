"""
BG Hero and Hero Power Registrations — from data/bg_heroes.json and CardDefs.xml

All heroes and hero powers registered with correct stats and costs.
Hero power scripts are resolved via HERO_POWER_SCRIPT_REGISTRY,
or set to None if not yet implemented.

Data source: Patch 35.2.2.241135 / Season 13 "Cataclysm Calls"
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from hsrl.core.card_db import register_card
from hsrl.core.enums import CardType, GameTag, Race, Rarity

# ── Data paths ────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
_CARD_DEFS = Path(__file__).parent.parent.parent.parent / "hsdata" / "CardDefs.xml"


def _load_data():
    with open(_DATA_DIR / "bg_heroes.json") as f:
        heroes = json.load(f)
    with open(_DATA_DIR / "bg_hero_powers.json") as f:
        powers = json.load(f)
    return heroes, powers


def _build_hero_power_map_from_xml():
    """Build {hero_card_id: power_dbf_id} from CardDefs.xml Tag 380 (HERO_POWER)."""
    hero_to_power_dbf = {}
    tree = ET.parse(str(_CARD_DEFS))
    root = tree.getroot()
    for entity in root.findall("Entity"):
        card_id = entity.get("CardID", "")
        # Skip skin variants
        if "_SKIN" in card_id:
            continue
        # Only process hero entities (those with Tag 380)
        tags = {}
        for t in entity.findall("Tag"):
            tags[int(t.get("enumID", 0))] = int(t.get("value", 0))
        tag_380 = tags.get(380, 0)
        if tag_380:
            hero_to_power_dbf[card_id] = tag_380
    return hero_to_power_dbf


def _build_power_cost_map_from_xml():
    """Build {card_id: cost} from CardDefs.xml Tag 32 or Tag 48 (COST)."""
    cost_map = {}
    tree = ET.parse(str(_CARD_DEFS))
    root = tree.getroot()
    for entity in root.findall("Entity"):
        card_id = entity.get("CardID", "")
        for t in entity.findall("Tag"):
            enum_id = int(t.get("enumID", 0))
            if enum_id in (32, 48):  # COST or HERO_POWER_COST
                cost_map[card_id] = int(t.get("value", 0))
                break
    return cost_map


def register_all_heroes():
    """Register all heroes and hero powers from data files."""
    heroes, powers = _load_data()

    # Build dbf_id → power lookup
    dbf_to_power = {p["dbf_id"]: p for p in powers}

    # Build CardDefs hero→power mapping
    xml_hero_to_power_dbf = _build_hero_power_map_from_xml()

    # Build CardDefs power cost mapping (fallback when JSON missing cost)
    xml_power_costs = _build_power_cost_map_from_xml()

    registered = 0

    for hero in heroes:
        hero_id = hero["id"]
        hero_name = hero["name"]
        hero_health = hero.get("health", 30)

        # Find the hero power for this hero
        power = None
        power_id = None

        # Method 1: authoritative CardDefs Tag 380 mapping. Simple naming is
        # only a fallback; preferring it silently bound Tavish's retired
        # Deadeye power while the 35.6 CardDefs selected Lock and Load.
        if hero_id in xml_hero_to_power_dbf:
            power_dbf = xml_hero_to_power_dbf[hero_id]
            if power_dbf in dbf_to_power:
                power = dbf_to_power[power_dbf]
                power_id = power["id"]

        # Method 2: legacy simple naming ({hero_id}p) when CardDefs has no
        # usable mapping in the versioned JSON snapshot.
        if power is None:
            simple_power_id = hero_id + "p"
            for p in powers:
                if p["id"] == simple_power_id:
                    power = p
                    power_id = simple_power_id
                    break

        # Register hero power card first (if found)
        power_cost = 0
        power_script = None
        if power is not None:
            power_id = power["id"]
            power_name = power["name"]
            power_cost = power.get("cost") or xml_power_costs.get(power_id, 0)
            # Resolve script class
            power_script = _get_script(power_id)

            # Register the hero power card (only if not already registered)
            from hsrl.core.card_db import CARDS
            if power_id not in CARDS:
                register_card(
                    card_id=power_id,
                    name=power_name,
                    text="",  # Text from CardDefs not yet extracted
                    cardtype=CardType.HERO_POWER,
                    tech_level=1,
                    tags={
                        GameTag.HERO_POWER_COST: power_cost,
                    },
                    script_class=power_script,
                )
            else:
                # Update cost on existing card (was previously 0 from JSON)
                existing = CARDS.get(power_id)
                if existing:
                    existing.tags[GameTag.HERO_POWER_COST] = power_cost
                    existing.scripts = power_script
        elif hero_id not in xml_hero_to_power_dbf:
            # Hero has no known power — register a placeholder
            power_id = None

        # Register the hero card
        from hsrl.core.card_db import CARDS
        if hero_id not in CARDS:
            tags = {
                GameTag.BASE_HEALTH: hero_health,
                GameTag.ARMOR: hero.get("armor") or 0,
                GameTag.HERO_POWER_COST: power_cost,
            }
            if power_id:
                tags[GameTag.HERO_POWER] = power_id

            register_card(
                card_id=hero_id,
                name=hero_name,
                text="",
                cardtype=CardType.HERO,
                tech_level=1,
                tags=tags,
                script_class=power_script,
            )
            registered += 1
        else:
            # Update existing hero card with correct cost/power
            existing = CARDS.get(hero_id)
            if existing:
                existing.tags[GameTag.HERO_POWER_COST] = power_cost
                if power_id:
                    existing.tags[GameTag.HERO_POWER] = power_id
                existing.scripts = power_script

    return registered


def _get_script(power_id: str):
    """Return the script class for a hero power, or None if not implemented."""
    from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY

    if power_id in HERO_POWER_SCRIPT_REGISTRY:
        return HERO_POWER_SCRIPT_REGISTRY[power_id]

    return None


# ── Register all on import ────────────────────────────────────────────
register_all_heroes()
