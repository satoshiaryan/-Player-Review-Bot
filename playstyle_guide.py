# =============================================
# === PLAYSTYLE GUIDE DATABASE ===
# =============================================

PLAYSTYLE_GUIDE = {
    "H2H": {
        "name": "Head to Head",
        "emoji": "⚔️",
        "description": "Real-time PvP matches",
        "categories": {
            "Attack": {
                "emoji": "⚡",
                "playstyles": ["Rapid", "Trickster", "Finesse Expert"]
            },
            "Midfield": {
                "emoji": "🎯",
                "playstyles": ["Tiki Taka", "Bullet Pass", "Relentless"]
            },
            "Defence": {
                "emoji": "🛡️",
                "playstyles": ["Anticipate", "Bruiser", "Accelerator", "Guardian"]
            }
        }
    },
    "MM": {
        "name": "Manager Mode",
        "emoji": "👔",
        "description": "Simulation-based matches",
        "categories": {
            "Attack": {
                "emoji": "⚡",
                "playstyles": ["Rapid"]
            },
            "Midfield": {
                "emoji": "🎯",
                "playstyles": ["Tiki Taka", "Relentless"]
            },
            "Defence": {
                "emoji": "🛡️",
                "playstyles": ["Anticipate", "Bruiser", "Accelerator"]
            }
        }
    },
    "VSA": {
        "name": "VS Attack",
        "emoji": "🎯",
        "description": "Turn-based attack mode",
        "categories": {
            "Attack": {
                "emoji": "⚡",
                "playstyles": ["Rapid", "Trickster", "Finesse Expert"]
            },
            "Midfield": {
                "emoji": "🎯",
                "playstyles": []
            },
            "Defence": {
                "emoji": "🛡️",
                "playstyles": []
            }
        }
    }
}


def get_playstyle_guide(mode: str) -> dict:
    """
    Get playstyle recommendations for a specific game mode.
    
    Args:
        mode: The game mode (e.g., "H2H", "MM", "VSA")
    
    Returns:
        dict with mode info and categories, or None if mode not found
    """
    mode = mode.upper()
    return PLAYSTYLE_GUIDE.get(mode)


def get_all_modes() -> list:
    """Get all available game modes"""
    return [
        {
            "key": mode_key,
            "name": mode_data["name"],
            "emoji": mode_data["emoji"],
            "description": mode_data["description"]
        }
        for mode_key, mode_data in PLAYSTYLE_GUIDE.items()
    ]


def get_mode_playstyles(mode: str) -> dict:
    """
    Get playstyles organized by category for a specific mode.
    
    Args:
        mode: The game mode (e.g., "H2H", "MM", "VSA")
    
    Returns:
        dict with categories as keys and playstyle lists as values
    """
    mode = mode.upper()
    mode_data = PLAYSTYLE_GUIDE.get(mode)
    
    if not mode_data:
        return {}
    
    result = {}
    for category, data in mode_data["categories"].items():
        result[category] = {
            "emoji": data["emoji"],
            "playstyles": data["playstyles"]
        }
    
    return result
