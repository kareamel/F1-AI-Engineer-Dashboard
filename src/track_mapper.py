"""
Track mapper — public interface for looking up circuit data by the telemetry
name that F1 25 puts into race_state["track_name"].

Two public functions:
  get_track_data()           — returns the full track data dict or None
  get_engineer_track_brief() — returns a formatted TRACK KNOWLEDGE text block
                               ready to inject into the engineer AI prompt

Matching is case-insensitive and handles common short-form variants (e.g.
"COTA" matches "Texas", "Interlagos" matches "Brazil").
"""

from track_data import TRACK_DATA


# ---------------------------------------------------------------------------
# Alias table
# ---------------------------------------------------------------------------

# Maps lowercase variant strings to the canonical TRACK_DATA key.
# Covers common abbreviations, venue names, and city names the game might use.
_ALIASES: dict[str, str] = {
    "abu dhabi":    "Abu Dhabi",
    "yas marina":   "Abu Dhabi",
    "austria":      "Austria",
    "red bull ring":"Austria",
    "melbourne":    "Melbourne",
    "albert park":  "Melbourne",
    "australia":    "Melbourne",
    "baku":         "Baku",
    "azerbaijan":   "Baku",
    "bahrain":      "Sakhir",
    "sakhir":       "Sakhir",
    "brazil":       "Brazil",
    "interlagos":   "Brazil",
    "canada":       "Montreal",
    "montreal":     "Montreal",
    "china":        "Shanghai",
    "shanghai":     "Shanghai",
    "spain":        "Catalunya",
    "barcelona":    "Catalunya",
    "catalunya":    "Catalunya",
    "great britain":"Silverstone",
    "silverstone":  "Silverstone",
    "gb":           "Silverstone",
    "hungary":      "Hungaroring",
    "hungaroring":  "Hungaroring",
    "italy":        "Monza",
    "monza":        "Monza",
    "japan":        "Suzuka",
    "suzuka":       "Suzuka",
    "monaco":       "Monaco",
    "mexico":       "Mexico",
    "mexico city":  "Mexico",
    "netherlands":  "Zandvoort",
    "zandvoort":    "Zandvoort",
    "qatar":        "Losail",
    "losail":       "Losail",
    "lusail":       "Losail",
    "saudi arabia": "Jeddah",
    "jeddah":       "Jeddah",
    "singapore":    "Singapore",
    "marina bay":   "Singapore",
    "usa":          "Texas",
    "texas":        "Texas",
    "cota":         "Texas",
    "miami":        "Miami",
    "las vegas":    "Las Vegas",
    "belgium":      "Spa",
    "spa":          "Spa",
    "imola":        "Imola",
    "emilia romagna":"Imola",
}


# ---------------------------------------------------------------------------
# Internal lookup
# ---------------------------------------------------------------------------

def _resolve_name(telemetry_name: str) -> str | None:
    """Resolves a telemetry name string to a canonical TRACK_DATA key.

    Tries an exact match first, then a case-insensitive alias lookup.

    Parameters:
        telemetry_name: The raw track name string from race_state.

    Returns:
        The canonical TRACK_DATA key, or None if no match found.
    """
    if telemetry_name in TRACK_DATA:
        return telemetry_name
    normalised = telemetry_name.strip().lower()
    if normalised in TRACK_DATA:
        return normalised
    return _ALIASES.get(normalised)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_track_data(telemetry_name: str) -> dict | None:
    """Returns the full track data dictionary for the given telemetry name.

    Parameters:
        telemetry_name: The track_name string from race_state (e.g. "Monza").

    Returns:
        The track data dict, or None if the track is not in the knowledge base.
    """
    key = _resolve_name(telemetry_name)
    return TRACK_DATA.get(key) if key else None


def get_engineer_track_brief(telemetry_name: str) -> str:
    """Returns a formatted TRACK KNOWLEDGE text block ready for Claude.

    Includes: circuit name and length, key braking zones, DRS zone locations,
    tyre degradation characteristics, overtaking spots, and the engineer
    strategy notes. Returns an empty string if the track is unknown.

    Parameters:
        telemetry_name: The track_name string from race_state.

    Returns:
        A multi-line formatted string, or an empty string if not found.
    """
    data = get_track_data(telemetry_name)
    if not data:
        return ""
    lines = [
        "=== TRACK KNOWLEDGE ===",
        f"{data['name']}  |  {data['lap_length_km']} km",
        "",
        "KEY CORNERS:",
    ]
    for corner in data["corners"]:
        braking_flag = " [BRAKING ZONE]" if corner["is_braking_zone"] else ""
        name_part    = f"{corner['name']}" if corner.get("name") else f"Turn {corner['number']}"
        lines.append(
            f"  T{corner['number']} {name_part} ({corner['type'].upper()}){braking_flag}"
            f" — {corner['typical_line_note']}"
        )
    lines.append("")
    lines.append("DRS ZONES:")
    for zone in data["drs_zones"]:
        lines.append(
            f"  Zone {zone['zone']}: detect at {zone['detection']}"
            f", activates {zone['activation']}"
        )
    lines.append("")
    tc = data["tyre_characteristics"]
    lines.append("TYRE CHARACTERISTICS:")
    lines.append(
        f"  Faster wear: {tc['faster_degradation_axle'].upper()} axle"
        f" — {tc['reason']}"
    )
    lines.append(f"  Degradation: {tc['degradation_rating'].upper()}")
    lines.append("")
    lines.append("OVERTAKING SPOTS:")
    for spot in data["overtaking_spots"]:
        lines.append(f"  {spot['location']}: {spot['technique']}")
    lines.append("")
    lines.append("STRATEGY NOTES:")
    lines.append(data["key_engineer_notes"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standalone smoke test
# Run: venv\Scripts\python.exe src\track_mapper.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_cases = [
        ("Monza",       True),
        ("Silverstone", True),
        ("COTA",        True),
        ("Monaco",      True),
        ("Unknown",     False),
    ]
    all_passed = True
    for name, expect_found in test_cases:
        data   = get_track_data(name)
        found  = data is not None
        brief  = get_engineer_track_brief(name)
        status = "OK" if found == expect_found else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  {status}  get_track_data('{name}')  found={found}")

    print()
    print("Sample brief for Monza:")
    print(get_engineer_track_brief("Monza"))
    print()
    print("All tests passed." if all_passed else "SOME TESTS FAILED.")
