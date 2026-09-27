"""
Circuit Reference Data — 24 F1 25 circuits.
Qualifying target times, race target times, and corner-by-corner coaching
notes calibrated for 106-110 AI difficulty level.

All times are in milliseconds. Turn numbers match F1 25 circuit numbering.
Keys in CIRCUIT_REFERENCE are canonical track names matching TRACK_DATA keys
in track_data.py (same as those resolved by track_mapper.py).
"""


# ---------------------------------------------------------------------------
# Calibration constant
# ---------------------------------------------------------------------------

AI_DIFFICULTY_LEVEL = 108   # Reference data calibrated for 106-110 AI


# ---------------------------------------------------------------------------
# Circuit reference data
# ---------------------------------------------------------------------------
# Per-entry structure:
#   qualifying_target_ms : int   — target qualifying lap time in ms
#   race_target_ms       : int   — target race lap time in ms
#   qualifying           : dict  — {turn_number (int): {board, gear, note}}
#   race                 : dict  — {turn_number (int): {board, gear, note}}
#
# 'board' is the braking board distance string ('100m', '50m', etc.).
# 'gear'  is the gear at the braking point; 0 = no specific gear instruction.
# 'note'  is a single-sentence coaching point for that corner.

CIRCUIT_REFERENCE: dict[str, dict] = {

    # -----------------------------------------------------------------------
    # MIDDLE EAST
    # -----------------------------------------------------------------------

    "Sakhir": {
        "qualifying_target_ms": 88_500,
        "race_target_ms":       93_200,
        "qualifying": {
            1:  {"board": "100m", "gear": 2,
                 "note": "100% peak pressure instantly, trail brake to apex, max rotation."},
            8:  {"board": "100m", "gear": 2,
                 "note": "Hug inside kerb, immediate short-shift to 3rd to negate wheelspin."},
            10: {"board": "50m",  "gear": 0,
                 "note": "Just past the 50m board, aggressive trail braking while steering left — accept front-left micro-lock for rotation."},
        },
        "race": {
            1:  {"board": "115m", "gear": 2,
                 "note": "85% peak pressure, lift and coast 50m prior, avoid traction slide on exit to save rears."},
            8:  {"board": "110m", "gear": 3,
                 "note": "Stay in 3rd gear minimum, linear throttle to protect thermal degradation."},
            10: {"board": "50m",  "gear": 0,
                 "note": "Brake in a straight line longer, ease off steering angle to prevent front-left wear."},
        },
    },

    "Jeddah": {
        "qualifying_target_ms": 87_100,
        "race_target_ms":       92_400,
        "qualifying": {
            1:  {"board": "100m", "gear": 3,
                 "note": "Cut T1 kerb aggressively, immediate direction change for T2."},
            13: {"board": "50m",  "gear": 4,
                 "note": "High minimum speed 170 km/h, lean heavily on aero grip."},
            27: {"board": "50m",  "gear": 4,
                 "note": "Late apex, 100% throttle before the corner exit."},
        },
        "race": {
            1:  {"board": "110m", "gear": 3,
                 "note": "Avoid deep kerb cuts to prevent floor damage and suspension overheating."},
            13: {"board": "50m",  "gear": 3,
                 "note": "Downshift to 3rd for engine braking, coast slightly mid-corner to save front-right tyre."},
            27: {"board": "65m",  "gear": 4,
                 "note": "Soften brake pressure, progressive throttle to limit longitudinal rear slip."},
        },
    },

    "Singapore": {
        "qualifying_target_ms": 90_300,
        "race_target_ms":       96_000,
        "qualifying": {
            7:  {"board": "100m", "gear": 3,
                 "note": "Heavy bump braking, ride the apex kerb."},
            14: {"board": "100m", "gear": 2,
                 "note": "Snap rotation, immediate 100% throttle."},
        },
        "race": {
            7:  {"board": "115m", "gear": 3,
                 "note": "Rear temps go critical here — short-shift out of every slow corner."},
            14: {"board": "115m", "gear": 2,
                 "note": "Progressive throttle, avoid wheelspin entirely."},
        },
    },

    "Losail": {
        "qualifying_target_ms": 82_800,
        "race_target_ms":       88_000,
        "qualifying": {
            1: {"board": "100m", "gear": 4,
                "note": "High minimum speed 160 km/h."},
            6: {"board": "50m",  "gear": 3,
                "note": "Slowest point of the lap, late apex."},
        },
        "race": {
            1: {"board": "115m", "gear": 4,
                "note": "High speed corners destroy the front-left — coast entries."},
            6: {"board": "65m",  "gear": 3,
                "note": "Smooth throttle, do not overdrive the exits."},
        },
    },

    "Abu Dhabi": {
        "qualifying_target_ms": 83_200,
        "race_target_ms":       88_500,
        "qualifying": {
            5: {"board": "100m", "gear": 3,
                "note": "Hairpin — late apex for straight speed."},
            6: {"board": "90m",  "gear": 2,
                "note": "Chicane — spike the brakes and flick the car right."},
        },
        "race": {
            5: {"board": "115m", "gear": 3,
                "note": "Short-shift out of the hairpin to save rears."},
            6: {"board": "110m", "gear": 2,
                "note": "Smooth direction change — rear degradation in Sector 3 ruins race pace."},
        },
    },

    "Baku": {
        "qualifying_target_ms": 100_300,
        "race_target_ms":       106_000,
        "qualifying": {
            1: {"board": "100m", "gear": 3,
                "note": "Max brake pressure, straight exit line."},
            8: {"board": "50m",  "gear": 3,
                "note": "Castle section — millimetres from the wall."},
        },
        "race": {
            1: {"board": "120m", "gear": 3,
                "note": "Lift and coast 100m prior — rear tyre slip kills race pace here."},
            8: {"board": "60m",  "gear": 3,
                "note": "Leave a safety margin at the castle, 80% throttle on exit."},
        },
    },

    # -----------------------------------------------------------------------
    # ASIA-PACIFIC
    # -----------------------------------------------------------------------

    "Suzuka": {
        "qualifying_target_ms": 88_200,
        "race_target_ms":       94_000,
        "qualifying": {
            1:  {"board": "50m",  "gear": 5,
                 "note": "Carry 5th gear, modulate brake pressure to 40% while turning."},
            9:  {"board": "50m",  "gear": 5,
                 "note": "Smash the inside kerb, ignore track limit warnings on exit."},
            16: {"board": "100m", "gear": 2,
                 "note": "100% brake spike, immediate trail-off for chicane flick."},
        },
        "race": {
            1:  {"board": "100m", "gear": 5,
                 "note": "Lift at the 100m board, coast into T1, brake at 50m — saves massive front-left tyre temp."},
            9:  {"board": "50m",  "gear": 5,
                 "note": "Avoid the heavy kerb strike to maintain suspension integrity."},
            16: {"board": "115m", "gear": 2,
                 "note": "Shift brake bias rearward to 52% to stop front lock-ups as tyres degrade."},
        },
    },

    "Shanghai": {
        "qualifying_target_ms": 92_800,
        "race_target_ms":       98_100,
        "qualifying": {
            1:  {"board": "100m", "gear": 0,
                 "note": "Endless trail braking through T1-3 snail complex — keep brake trace at 10-15% throughout."},
            14: {"board": "100m", "gear": 2,
                 "note": "Extreme late apex to maximise exit speed down the pit straight."},
        },
        "race": {
            1:  {"board": "0m",   "gear": 0,
                 "note": "Lift early and coast into the T1-3 spiral — front-left will die if you overdrive entry speed."},
            14: {"board": "120m", "gear": 3,
                 "note": "Shift bias to 54%, smooth traction in 3rd gear — spinning the rears here kills your lap time."},
        },
    },

    "Melbourne": {
        "qualifying_target_ms": 76_800,
        "race_target_ms":       81_500,
        "qualifying": {
            1:  {"board": "100m", "gear": 4,
                 "note": "4th gear, minimum speed 160 km/h, attack exit kerb."},
            3:  {"board": "100m", "gear": 3,
                 "note": "Brake deep, square off for maximum traction into T4."},
            11: {"board": "0m",   "gear": 7,
                 "note": "No brake — slight lift to 80% throttle, 7th gear chicane flip."},
        },
        "race": {
            1:  {"board": "110m", "gear": 4,
                 "note": "Keep off the exit kerb to prevent rear tyre scrubbing."},
            3:  {"board": "115m", "gear": 3,
                 "note": "Smooth trail brake, avoid aggressive downshifts to protect gearbox."},
            11: {"board": "0m",   "gear": 7,
                 "note": "Dab of brake — settle the nose to protect front tyre slip angles in dirty air."},
        },
    },

    # -----------------------------------------------------------------------
    # EUROPE
    # -----------------------------------------------------------------------

    "Monza": {
        "qualifying_target_ms": 79_800,
        "race_target_ms":       84_500,
        "qualifying": {
            1: {"board": "120m", "gear": 3,
                "note": "100% peak brake, cut the first kerb."},
            8: {"board": "75m",  "gear": 6,
                "note": "Ascari entry — max throttle before the first apex."},
        },
        "race": {
            1: {"board": "140m", "gear": 3,
                "note": "Massive lift and coast, brake bias 55% to stop rear locking."},
            8: {"board": "90m",  "gear": 6,
                "note": "Avoid heavy kerb cuts to protect low-downforce stability."},
        },
    },

    "Silverstone": {
        "qualifying_target_ms": 86_300,
        "race_target_ms":       91_500,
        "qualifying": {
            6:  {"board": "50m", "gear": 5,
                 "note": "Heavy trail brake into Brooklands, late apex."},
            15: {"board": "50m", "gear": 6,
                 "note": "Turn into Stowe before hitting the brakes."},
        },
        "race": {
            6:  {"board": "65m", "gear": 5,
                 "note": "Coast entry — front-left degradation is massive here."},
            15: {"board": "75m", "gear": 6,
                 "note": "Softer brake pressure, manage lateral load on the front-left."},
        },
    },

    "Spa": {
        "qualifying_target_ms": 102_800,
        "race_target_ms":       108_500,
        "qualifying": {
            1:  {"board": "100m", "gear": 2,
                 "note": "Extremely late apex for Kemmel Straight speed."},
            18: {"board": "150m", "gear": 2,
                 "note": "Smash the bus stop kerbs."},
        },
        "race": {
            1:  {"board": "115m", "gear": 2,
                 "note": "Avoid front locking — flat spots ruin the long lap."},
            18: {"board": "165m", "gear": 2,
                 "note": "Stay off the massive kerbs to protect tyre carcass."},
        },
    },

    "Monaco": {
        "qualifying_target_ms": 70_800,
        "race_target_ms":       75_500,
        "qualifying": {
            1:  {"board": "50m",  "gear": 3,
                 "note": "Millimetres from the inside barrier, max throttle up the hill."},
            10: {"board": "100m", "gear": 2,
                 "note": "Violent braking, hop both chicane kerbs."},
        },
        "race": {
            1:  {"board": "60m",  "gear": 3,
                 "note": "Leave a margin — prioritize clean exit over entry speed."},
            10: {"board": "110m", "gear": 2,
                 "note": "Do not hop the kerbs — it induces terminal rear tyre slip."},
        },
    },

    "Hungaroring": {
        "qualifying_target_ms": 76_800,
        "race_target_ms":       82_000,
        "qualifying": {
            1: {"board": "100m", "gear": 2,
                "note": "100% brake pressure, deep trail into apex."},
            2: {"board": "50m",  "gear": 3,
                "note": "Downhill — keep tight to the inside line."},
        },
        "race": {
            1: {"board": "120m", "gear": 2,
                "note": "Lift and coast — rear thermal degradation is high, smooth exit required."},
            2: {"board": "65m",  "gear": 3,
                "note": "Avoid mid-corner throttle hesitation to save rears."},
        },
    },

    "Zandvoort": {
        "qualifying_target_ms": 70_300,
        "race_target_ms":       75_000,
        "qualifying": {
            1:  {"board": "100m", "gear": 3,
                 "note": "Dive into the banking, carry 100 km/h minimum speed."},
            11: {"board": "50m",  "gear": 2,
                 "note": "Sharp chicane, aggressive direction change."},
        },
        "race": {
            1:  {"board": "115m", "gear": 3,
                 "note": "Front-left tyre wear is critical here, softer steering lock."},
            11: {"board": "65m",  "gear": 2,
                 "note": "Smooth traction to prevent rear overheating on the banking."},
        },
    },

    "Imola": {
        "qualifying_target_ms": 74_200,
        "race_target_ms":       79_000,
        "qualifying": {
            2:  {"board": "100m", "gear": 4,
                 "note": "Attack the first kerb heavily, ignore the second kerb."},
            14: {"board": "100m", "gear": 3,
                 "note": "Mount the high entry kerb to open the chicane angle."},
        },
        "race": {
            2:  {"board": "110m", "gear": 4,
                 "note": "Avoid deep kerb cuts — suspension damage risk over 60 laps."},
            14: {"board": "115m", "gear": 3,
                 "note": "Use less entry kerb to maintain rear traction stability."},
        },
    },

    "Austria": {
        "qualifying_target_ms": 64_200,
        "race_target_ms":       69_000,
        "qualifying": {
            1: {"board": "50m",  "gear": 4,
                "note": "Attack the exit sausage kerb."},
            3: {"board": "100m", "gear": 2,
                "note": "Uphill — brake extremely late and square off the exit."},
        },
        "race": {
            1: {"board": "60m",  "gear": 4,
                "note": "Avoid the sausage kerbs to prevent floor wear."},
            3: {"board": "115m", "gear": 2,
                "note": "Lift and coast 50m prior, short-shift to 3rd for traction."},
        },
    },

    "Catalunya": {
        "qualifying_target_ms": 72_300,
        "race_target_ms":       78_000,
        "qualifying": {
            1:  {"board": "100m", "gear": 3,
                 "note": "Deep trail brake — compromise T1 exit for T2 entry."},
            10: {"board": "100m", "gear": 2,
                 "note": "100% brake spike, fast rotation."},
        },
        "race": {
            1:  {"board": "115m", "gear": 3,
                 "note": "Left-front tyre is critical here, soften brake application."},
            10: {"board": "120m", "gear": 2,
                 "note": "Progressive throttle on exit — aggressive throttle spikes the rears instantly."},
        },
    },

    # -----------------------------------------------------------------------
    # NORTH AMERICA
    # -----------------------------------------------------------------------

    "Montreal": {
        "qualifying_target_ms": 71_200,
        "race_target_ms":       76_000,
        "qualifying": {
            10: {"board": "100m", "gear": 2,
                 "note": "Hairpin — very late apex, rotate the car quickly."},
            13: {"board": "100m", "gear": 4,
                 "note": "Chicane — bounce the right kerb and kiss the Wall of Champions."},
        },
        "race": {
            10: {"board": "115m", "gear": 2,
                 "note": "Short-shift to 3rd immediately on exit to save rear tyres."},
            13: {"board": "110m", "gear": 4,
                 "note": "Give the Wall of Champions a 1-metre buffer."},
        },
    },

    "Texas": {
        "qualifying_target_ms": 93_300,
        "race_target_ms":       99_000,
        "qualifying": {
            1:  {"board": "100m", "gear": 2,
                 "note": "Uphill blind apex — late cut-back line."},
            11: {"board": "100m", "gear": 2,
                 "note": "Hairpin — brake straight, pivot on apex."},
        },
        "race": {
            1:  {"board": "115m", "gear": 2,
                 "note": "Protect front-left for the Esses — coast into apex."},
            11: {"board": "120m", "gear": 2,
                 "note": "Linear throttle ramp — do not spike the rears before the back straight."},
        },
    },

    "Miami": {
        "qualifying_target_ms": 86_700,
        "race_target_ms":       92_000,
        "qualifying": {
            1:  {"board": "100m", "gear": 3,
                 "note": "Carry 110 km/h minimum speed, ride the outside exit kerb."},
            17: {"board": "100m", "gear": 2,
                 "note": "Heavy 100% braking, square the exit."},
        },
        "race": {
            1:  {"board": "110m", "gear": 3,
                 "note": "Stay off the exit kerb to avoid traction loss and tyre overheating."},
            17: {"board": "120m", "gear": 2,
                 "note": "Lift and coast on the long straight, short-shift to 3rd on exit."},
        },
    },

    "Las Vegas": {
        "qualifying_target_ms": 92_300,
        "race_target_ms":       97_500,
        "qualifying": {
            1:  {"board": "100m", "gear": 3,
                 "note": "Low grip — square the corner."},
            14: {"board": "150m", "gear": 3,
                 "note": "End of the Strip — max brake pressure, hit the apex kerb."},
        },
        "race": {
            1:  {"board": "120m", "gear": 3,
                 "note": "Tyres will be cold — brake early and soft."},
            14: {"board": "170m", "gear": 3,
                 "note": "Massive lift and coast — brake straight to avoid locking cold fronts."},
        },
    },

    # -----------------------------------------------------------------------
    # SOUTH AMERICA
    # -----------------------------------------------------------------------

    "Brazil": {
        "qualifying_target_ms": 69_800,
        "race_target_ms":       74_500,
        "qualifying": {
            1: {"board": "100m", "gear": 3,
                "note": "Downhill Senna S — trail brake deep into T2."},
            4: {"board": "100m", "gear": 4,
                "note": "Attack apex, use full track width on exit."},
        },
        "race": {
            1: {"board": "115m", "gear": 3,
                "note": "Shift bias forward to 56% to prevent downhill rear locking."},
            4: {"board": "110m", "gear": 4,
                "note": "Smooth traction — rear-left takes a beating here."},
        },
    },

    "Mexico": {
        "qualifying_target_ms": 76_800,
        "race_target_ms":       82_000,
        "qualifying": {
            1:  {"board": "100m", "gear": 3,
                 "note": "Thin air means less aero braking — 100% pedal pressure."},
            13: {"board": "50m",  "gear": 2,
                 "note": "Stadium entry — zero wheelspin allowed."},
        },
        "race": {
            1:  {"board": "120m", "gear": 3,
                 "note": "Massive lift and coast for brake temperature management."},
            13: {"board": "65m",  "gear": 2,
                 "note": "Short-shift to 3rd instantly — rear degradation is race-ending here."},
        },
    },
}


# ---------------------------------------------------------------------------
# Alias table for case-insensitive lookup
# ---------------------------------------------------------------------------
# Maps lowercase track name variants to canonical CIRCUIT_REFERENCE keys.

_CIRCUIT_ALIASES: dict[str, str] = {
    "abu dhabi":      "Abu Dhabi",
    "yas marina":     "Abu Dhabi",
    "austria":        "Austria",
    "red bull ring":  "Austria",
    "melbourne":      "Melbourne",
    "albert park":    "Melbourne",
    "australia":      "Melbourne",
    "baku":           "Baku",
    "azerbaijan":     "Baku",
    "bahrain":        "Sakhir",
    "sakhir":         "Sakhir",
    "brazil":         "Brazil",
    "interlagos":     "Brazil",
    "canada":         "Montreal",
    "montreal":       "Montreal",
    "china":          "Shanghai",
    "shanghai":       "Shanghai",
    "spain":          "Catalunya",
    "barcelona":      "Catalunya",
    "catalunya":      "Catalunya",
    "great britain":  "Silverstone",
    "silverstone":    "Silverstone",
    "gb":             "Silverstone",
    "hungary":        "Hungaroring",
    "hungaroring":    "Hungaroring",
    "italy":          "Monza",
    "monza":          "Monza",
    "japan":          "Suzuka",
    "suzuka":         "Suzuka",
    "monaco":         "Monaco",
    "mexico":         "Mexico",
    "mexico city":    "Mexico",
    "netherlands":    "Zandvoort",
    "zandvoort":      "Zandvoort",
    "qatar":          "Losail",
    "losail":         "Losail",
    "lusail":         "Losail",
    "saudi arabia":   "Jeddah",
    "jeddah":         "Jeddah",
    "singapore":      "Singapore",
    "marina bay":     "Singapore",
    "usa":            "Texas",
    "texas":          "Texas",
    "cota":           "Texas",
    "miami":          "Miami",
    "las vegas":      "Las Vegas",
    "belgium":        "Spa",
    "spa":            "Spa",
    "imola":          "Imola",
    "emilia romagna": "Imola",
}


# ---------------------------------------------------------------------------
# Lookup function
# ---------------------------------------------------------------------------

def get_circuit_reference(track_name: str) -> dict | None:
    """Returns the circuit reference dict for the given track name, or None.

    Case-insensitive matching against known track name variants.

    Parameters:
        track_name: The track_name string from race_state (e.g. 'Monza').

    Returns:
        Circuit reference dict containing qualifying_target_ms, race_target_ms,
        qualifying corner notes, and race corner notes. Returns None if the
        track is not in the reference database.
    """
    if track_name in CIRCUIT_REFERENCE:
        return CIRCUIT_REFERENCE[track_name]
    canonical = _CIRCUIT_ALIASES.get(track_name.strip().lower())
    if canonical:
        return CIRCUIT_REFERENCE.get(canonical)
    return None
