"""Mishka rarity types and drop mechanics."""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class MishkaRarity(str, Enum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


@dataclass(frozen=True)
class MishkaInfo:
    rarity: MishkaRarity
    name: str
    accusative_name: str  # For sentences like "получил обычного мишку"
    emoji: str
    column_name: str


MISHKA_TYPES = {
    MishkaRarity.COMMON: MishkaInfo(
        rarity=MishkaRarity.COMMON,
        name="Обычный мишка",
        accusative_name="Обычного мишку",
        emoji="🧸",
        column_name="common_count",
    ),
    MishkaRarity.RARE: MishkaInfo(
        rarity=MishkaRarity.RARE,
        name="Редкий мишка",
        accusative_name="Редкого мишку",
        emoji="🐻",
        column_name="rare_count",
    ),
    MishkaRarity.EPIC: MishkaInfo(
        rarity=MishkaRarity.EPIC,
        name="Эпический мишка",
        accusative_name="Эпического мишку",
        emoji="🐼",
        column_name="epic_count",
    ),
    MishkaRarity.LEGENDARY: MishkaInfo(
        rarity=MishkaRarity.LEGENDARY,
        name="Легендарный мишка",
        accusative_name="Легендарного мишку",
        emoji="🐨",
        column_name="legendary_count",
    ),
}


def parse_rarity(value: str) -> Optional[MishkaRarity]:
    """Parse rarity from user input string (accepts english or russian keywords)."""
    val = value.strip().lower()
    mapping = {
        "common": MishkaRarity.COMMON,
        "обычный": MishkaRarity.COMMON,
        "обычного": MishkaRarity.COMMON,
        "rare": MishkaRarity.RARE,
        "редкий": MishkaRarity.RARE,
        "редкого": MishkaRarity.RARE,
        "epic": MishkaRarity.EPIC,
        "эпический": MishkaRarity.EPIC,
        "эпик": MishkaRarity.EPIC,
        "legendary": MishkaRarity.LEGENDARY,
        "легендарный": MishkaRarity.LEGENDARY,
        "легенда": MishkaRarity.LEGENDARY,
    }
    return mapping.get(val)


def roll_mishka_drop(
    base_chance: float,
    common_chance: float,
    rare_chance: float,
    epic_chance: float,
    legendary_chance: float,
) -> Tuple[bool, Optional[MishkaInfo]]:
    """
    Rolls whether a mishka drops, and if so, rolls which type.
    
    Returns:
        (dropped: bool, mishka_info: Optional[MishkaInfo])
    """
    if base_chance <= 0.0:
        return False, None

    # Roll base chance
    roll = random.uniform(0.0, 100.0)
    if roll > base_chance:
        return False, None

    # Roll rarity type according to weights
    rarities = [
        MishkaRarity.COMMON,
        MishkaRarity.RARE,
        MishkaRarity.EPIC,
        MishkaRarity.LEGENDARY,
    ]
    weights = [common_chance, rare_chance, epic_chance, legendary_chance]

    chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]
    return True, MISHKA_TYPES[chosen_rarity]
