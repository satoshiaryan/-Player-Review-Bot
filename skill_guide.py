# =============================================
# === HARDCODED SKILL POINT GUIDE DATABASE ===
# =============================================

SKILL_GUIDE = {
    # ====================
    # === WINGERS (LW/RW/LM/RM) ===
    # ====================
    "Winger_Traditional": {
        "positions": ["LW", "RW", "LM", "RM"],
        "skill_name": "Traditional Winger",
        "recommendations": ["Passing", "Dribbling", "Physical"],
        "note": "For Playmaker trait or Traditional Winger skill point"
    },
    "Winger_Inverted": {
        "positions": ["LW", "RW", "LM", "RM"],
        "skill_name": "Inverted Winger",
        "recommendations": ["Scoring", "Dribbling", "Physical"],
        "note": "For Inverted Winger skill point"
    },
    "Winger_At_ST": {
        "positions": ["LW", "RW", "ST", "CAM"],
        "skill_name": "Winger at ST/CAM",
        "recommendations": ["Shooting", "Passing", "Dribbling"],
        "note": "When playing winger at ST or CAM position"
    },

    # ====================
    # === STRIKERS (ST) ===
    # ====================
    "Striker_Any": {
        "positions": ["ST"],
        "skill_name": "Striker (All Types)",
        "recommendations": ["Shooting", "Dribbling", "Physical"],
        "note": "Irrespective of first skill point"
    },

    # ====================
    # === WIDE MIDFIELDERS (LM/RM) ===
    # ====================
    "Wide_Midfielder_Any": {
        "positions": ["LM", "RM"],
        "skill_name": "Wide Midfielder (All Types)",
        "recommendations": ["Scoring", "Passing", "Dribbling"],
        "note": "Irrespective of first skill point"
    },

    # ====================
    # === ATTACKING MIDFIELDERS (CAM) ===
    # ====================
    "CAM_Any": {
        "positions": ["CAM"],
        "skill_name": "Attacking Midfielder (All Types)",
        "recommendations": ["Scoring", "Passing", "Dribbling"],
        "note": "Irrespective of first skill point"
    },

    # ====================
    # === DEFENSIVE MIDFIELDERS (CDM) ===
    # ====================
    "CDM_MH": {
        "positions": ["CDM"],
        "skill_name": "CDM (M/H or CB at CDM)",
        "recommendations": ["Passing", "Defending", "Physical"],
        "note": "For M/H workrate or CB playing at CDM"
    },
    "CDM_HH": {
        "positions": ["CDM"],
        "skill_name": "CDM (H/H Workrate)",
        "recommendations": ["Scoring", "Passing", "Physical"],
        "note": "For H/H workrate CDMs"
    },

    # ====================
    # === CENTRAL MIDFIELDERS (CM) ===
    # ====================
    "CM_BoxToBox": {
        "positions": ["CM"],
        "skill_name": "CM - Box to Box",
        "recommendations": ["Passing", "Defending", "Physical"],
        "note": "For Box to Box skill point"
    },
    "CM_Playmaker": {
        "positions": ["CM"],
        "skill_name": "CM - Playmaker/Attacking",
        "recommendations": ["Scoring or Passing", "Dribbling", "Physical"],
        "note": "For Playmaker or attacking-minded CMs"
    },
    "CM_Balanced": {
        "positions": ["CM"],
        "skill_name": "CM - Balanced",
        "recommendations": ["Passing", "Dribbling", "Physical"],
        "note": "For balanced midfielders"
    },
    "CM_HalfWinger": {
        "positions": ["CM"],
        "skill_name": "CM - Half Winger",
        "recommendations": ["Passing", "Dribbling or Physical", "Scoring"],
        "note": "For Half Winger skill point"
    },

    # ====================
    # === CENTRE BACKS (CB) ===
    # ====================
    "CB_Any": {
        "positions": ["CB"],
        "skill_name": "Centre Back (All Types)",
        "recommendations": ["Scoring", "Physical", "Defending"],
        "note": "Irrespective of first skill point"
    },

    # ====================
    # === FULL BACKS (LB/RB) ===
    # ====================
    "FB_Wingback": {
        "positions": ["LB", "RB"],
        "skill_name": "Fullback - Wingback/Falseback",
        "recommendations": ["Dribbling", "Defending", "Physical"],
        "note": "For Wingback or Falseback skill points"
    },
    "FB_Fullback": {
        "positions": ["LB", "RB"],
        "skill_name": "Fullback - Defensive",
        "recommendations": ["Passing", "Defending", "Physical"],
        "note": "For traditional Fullback skill point"
    },

    # ====================
    # === GOALKEEPERS (GK) ===
    # ====================
    "GK_Any": {
        "positions": ["GK"],
        "skill_name": "Goalkeeper (All Types)",
        "recommendations": ["GK Kicking", "GK Rush", "High Balls"],
        "note": "Irrespective of first skill point"
    },
}


def get_skill_guide(position: str, playstyle: str = None) -> dict:
    """
    Get skill point recommendations for a position.
    
    Args:
        position: The position (e.g., "CAM", "ST", "CDM")
        playstyle: Optional playstyle/workrate/skill point type
    
    Returns:
        dict with recommendations or None if no match
    """
    position = position.upper()
    
    position_map = {
        "LW": "Winger", "RW": "Winger",
        "ST": "Striker",
        "LM": "Wide_Midfielder", "RM": "Wide_Midfielder",
        "CAM": "CAM", "CDM": "CDM", "CM": "CM",
        "CB": "CB", "LB": "FB", "RB": "FB", "GK": "GK"
    }
    
    group = position_map.get(position, position)
    
    matching_guides = []
    for key, guide in SKILL_GUIDE.items():
        if position in guide.get("positions", []):
            matching_guides.append((key, guide))
    
    if not matching_guides:
        return None
    
    # If multiple matches and playstyle provided, try to narrow down
    if playstyle and len(matching_guides) > 1:
        playstyle_lower = playstyle.lower()
        for key, guide in matching_guides:
            if playstyle_lower in guide["skill_name"].lower():
                return guide
            if "Any" in key and "Irrespective" in guide.get("note", ""):
                return guide
    
    # Return first match (or "Any" type if available)
    for key, guide in matching_guides:
        if "Any" in key:
            return guide
    
    return matching_guides[0][1]


def get_position_options(position: str) -> list:
    """Get all playstyle options for a position"""
    position = position.upper()
    options = []
    
    for key, guide in SKILL_GUIDE.items():
        if position in guide.get("positions", []):
            options.append({
                "key": key,
                "skill_name": guide["skill_name"],
                "note": guide["note"]
            })
    
    return options
