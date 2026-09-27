"""
Track knowledge base for all 24 circuits on the 2025 F1 calendar.

Each entry is keyed by the exact telemetry_name string that the f1-packets
library returns from the TRACKS lookup (packets.TRACKS[track_id]).  That
string is what RaceStateManager puts into race_state["track_name"] and what
the engineer briefing carries.

Data per track:
  name                  — full official circuit name
  telemetry_name        — string as emitted by F1 25 UDP telemetry
  lap_length_km         — official lap length
  corners               — key engineering corners (braking zones, slow chicanes,
                          high-speed commitment points)
  drs_zones             — detection point and activation point per zone
  tyre_characteristics  — which axle degrades faster and why, overall rating
  overtaking_spots      — where passes happen and how
  key_engineer_notes    — 4-5 sentences of strategy context for Claude
"""


# ---------------------------------------------------------------------------
# Track knowledge base
# ---------------------------------------------------------------------------

# Each value is a dict describing one circuit.
# Keyed by the exact string from packets.TRACKS (e.g. "Monza", "Silverstone").

TRACK_DATA: dict[str, dict] = {

    # -----------------------------------------------------------------------
    "Melbourne": {
        "name":           "Albert Park Circuit",
        "telemetry_name": "Melbourne",
        "lap_length_km":  5.303,
        "corners": [
            {"number": 1,  "name": "Turn 1",         "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight right hander; heavy braking from 310km/h, apex kerb critical for T2 exit speed"},
            {"number": 3,  "name": "Turn 3",         "type": "fast",   "is_braking_zone": False, "typical_line_note": "Flat in qualifying, lift slightly in race; high-speed commitment corner"},
            {"number": 9,  "name": "Turn 9/10",      "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Chicane, key overtaking spot under braking into T9"},
            {"number": 11, "name": "Turn 11",        "type": "medium", "is_braking_zone": True,  "typical_line_note": "Tight right, traction zone onto back straight"},
            {"number": 13, "name": "Turn 13",        "type": "fast",   "is_braking_zone": False, "typical_line_note": "High-speed kink, confidence corner — losing time here costs the lap"},
            {"number": 15, "name": "Turn 15/16",     "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Final chicane before main straight DRS zone"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 15", "activation": "Start of main straight"},
            {"zone": 2, "detection": "Turn 2",  "activation": "Lakeside straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "front",
            "reason":                  "High-speed direction changes and several medium-speed corners load front axle heavily; rear is comparatively gentle",
            "degradation_rating":      "medium",
        },
        "overtaking_spots": [
            {"location": "Turn 1", "technique": "Late braking down the inside; DRS from main straight gives a large speed advantage"},
            {"location": "Turn 9", "technique": "Chicane braking zone, side-by-side possible with DRS from lakeside straight"},
        ],
        "key_engineer_notes": (
            "Melbourne runs anti-clockwise and oscillates between high-speed blasts and tight chicanes. "
            "Safety car probability is high — the circuit is semi-permanent with barriers close to the track. "
            "Undercut is strong here because fresh tyres unlock significant delta on cold asphalt in the early laps of a stint. "
            "Pit window opens around lap 18-22 on a standard 58-lap race; a two-stop is feasible if tyre degradation is higher than predicted. "
            "Front tyre management through the T1-T4 sequence is the biggest differentiator across a stint."
        ),
    },

    # -----------------------------------------------------------------------
    "Jeddah": {
        "name":           "Jeddah Corniche Circuit",
        "telemetry_name": "Jeddah",
        "lap_length_km":  6.174,
        "corners": [
            {"number": 1,  "name": "Turn 1",    "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight right hander; hardest braking point on the circuit, late apex to set up T2"},
            {"number": 4,  "name": "Turn 4",    "type": "fast",   "is_braking_zone": False, "typical_line_note": "Flat-out kink at 300+ km/h, wall close on exit"},
            {"number": 13, "name": "Turn 13",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Second DRS detection; heavy braking, tight hairpin"},
            {"number": 17, "name": "Turn 17/18","type": "medium", "is_braking_zone": True,  "typical_line_note": "S-complex, high kerb risk; lose exit and the back straight is compromised"},
            {"number": 27, "name": "Turn 27",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Final hairpin before pit straight, key overtaking venue under heavy braking"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 22", "activation": "After Turn 22 onto back straight"},
            {"zone": 2, "detection": "Turn 1",  "activation": "Pit straight"},
            {"zone": 3, "detection": "Turn 13", "activation": "Middle straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Long straights followed by heavy braking and traction zones load rear tyres; lateral forces are brief but sharp",
            "degradation_rating":      "low",
        },
        "overtaking_spots": [
            {"location": "Turn 1",  "technique": "Main DRS zone, heavy braking, multiple lines viable"},
            {"location": "Turn 27", "technique": "Final hairpin, undercut threat is strong given DRS zones"},
        ],
        "key_engineer_notes": (
            "Jeddah is the longest circuit on the calendar and suits low-degradation strategies. "
            "One-stop is usually viable; two-stop only if there is an early safety car or unusual wear. "
            "Three DRS zones make overtaking very achievable, so track position is less critical than at Monaco-type circuits. "
            "Overcut can work here if the driver on used tyres can manage the gap — the long lap means a short pit window. "
            "Safety car probability is medium-high due to tight walls and high closing speeds."
        ),
    },

    # -----------------------------------------------------------------------
    "Sakhir": {
        "name":           "Bahrain International Circuit",
        "telemetry_name": "Sakhir",
        "lap_length_km":  5.412,
        "corners": [
            {"number": 1,  "name": "Turn 1/2",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Classic 90-degree right; late braking gives inside line for T2"},
            {"number": 4,  "name": "Turn 4",    "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hairpin, major traction demand on exits — tyre deg amplified here"},
            {"number": 8,  "name": "Turn 8",    "type": "fast",   "is_braking_zone": False, "typical_line_note": "High-speed right, committed entry with early apex"},
            {"number": 10, "name": "Turn 10",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Chicane entry, key DRS detection point, heavy braking"},
            {"number": 13, "name": "Turn 13",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hairpin at end of back straight, biggest overtaking point on circuit"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 10", "activation": "Back straight toward T13"},
            {"zone": 2, "detection": "Turn 14", "activation": "Pit straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Sand and abrasive asphalt degrade all tyres but rear-exit traction from slow corners is the dominant wear mechanism",
            "degradation_rating":      "high",
        },
        "overtaking_spots": [
            {"location": "Turn 1",  "technique": "DRS from pit straight, outbrake into T1"},
            {"location": "Turn 13", "technique": "Long back straight with DRS, classic hairpin dive"},
        ],
        "key_engineer_notes": (
            "Bahrain is a tyre-wear circuit — high degradation makes a two-stop almost always faster on paper. "
            "The undercut is extremely powerful because fresh soft/medium tyres lap 1.5-2s faster in the first few laps. "
            "If boxed in traffic, prioritise the undercut window even if nominal strategy says stay out longer. "
            "Rear tyre blistering can occur on harder compounds if push laps are done early in the stint. "
            "Safety car probability is low; base strategy should be two-stop unless the first stint shows unusually low degradation."
        ),
    },

    # -----------------------------------------------------------------------
    "Shanghai": {
        "name":           "Shanghai International Circuit",
        "telemetry_name": "Shanghai",
        "lap_length_km":  5.451,
        "corners": [
            {"number": 1,  "name": "Turn 1/2",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hairpin entry, track-rod slow-in-fast-out; wide run-off makes aggressive moves viable"},
            {"number": 3,  "name": "Turn 3",    "type": "fast",   "is_braking_zone": False, "typical_line_note": "Long decreasing-radius right hander; huge front load, key to sector 1 time"},
            {"number": 6,  "name": "Turn 6",    "type": "medium", "is_braking_zone": True,  "typical_line_note": "Mid-speed chicane; smooth flow critical, curbing limits exit speed"},
            {"number": 11, "name": "Turn 11",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hairpin, main overtaking point on the back straight with DRS"},
            {"number": 14, "name": "Turn 14/16","type": "slow",   "is_braking_zone": True,  "typical_line_note": "Final hairpin complex; traction exit onto main straight is lap-time critical"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 7",  "activation": "Back straight after T7"},
            {"zone": 2, "detection": "Turn 13", "activation": "Main straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "front",
            "reason":                  "Turn 3 long-radius right exerts sustained lateral load on the front-left for the entire corner",
            "degradation_rating":      "medium",
        },
        "overtaking_spots": [
            {"location": "Turn 1",  "technique": "DRS from main straight; run-off area reduces risk, late braking viable"},
            {"location": "Turn 11", "technique": "Long back straight DRS; hairpin braking at high speed, car-width gap needed"},
        ],
        "key_engineer_notes": (
            "Shanghai favours a one-stop but front-left wear on Turn 3 can force an earlier pit if management lapses. "
            "The Turn 3 exit is where the lap is made or lost — if the driver reports understeer there, front degradation is accelerating. "
            "Undercut window is around laps 25-32 on a 56-lap race; boxed in dirty air, go earlier. "
            "Safety car probability is medium; the hairpin complex at T14 is a common incident point. "
            "Overcut rarely works here because the long lap means a large window to cover."
        ),
    },

    # -----------------------------------------------------------------------
    "Miami": {
        "name":           "Miami International Autodrome",
        "telemetry_name": "Miami",
        "lap_length_km":  5.412,
        "corners": [
            {"number": 1,  "name": "Turn 1",       "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight right off the start; DRS overtaking zone, late braking inside"},
            {"number": 6,  "name": "Turn 6/7",     "type": "medium", "is_braking_zone": True,  "typical_line_note": "Chicane, bumpy on entry; smooth hands limit front wear through this section"},
            {"number": 11, "name": "Turn 11",      "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hairpin at end of back straight; heaviest braking of the lap, rear lockup risk"},
            {"number": 14, "name": "Turn 14/15/16","type": "medium", "is_braking_zone": True,  "typical_line_note": "Tight infield sequence, high kerb-strike risk; rear wear generated here"},
            {"number": 17, "name": "Turn 17",      "type": "fast",   "is_braking_zone": False, "typical_line_note": "Long sweeping right; committed entry with traction run to final straight"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 15", "activation": "Final straight to Turn 1"},
            {"zone": 2, "detection": "Turn 8",  "activation": "Back straight to Turn 11"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "High traction demand at T11 and the infield complex plus bumpy surface generate rear deg and blistering risk",
            "degradation_rating":      "medium",
        },
        "overtaking_spots": [
            {"location": "Turn 1",  "technique": "DRS from final straight, hard braking on inside"},
            {"location": "Turn 11", "technique": "Back straight DRS into hairpin, high closing speeds"},
        ],
        "key_engineer_notes": (
            "Miami is a street-style circuit with medium degradation — one-stop is the default but a safety car can force two. "
            "Track position matters due to the limited overtaking zones, so defending on older tyres is viable. "
            "The bumpy surface causes unexpected graining on softer compounds in cooler conditions; check track temperature trends. "
            "Undercut window is around laps 22-28; a 4-lap undercut gap is needed to clear traffic after the pit. "
            "Safety car probability is high — tight walls at T6-T7 and the infield complex are common incident points."
        ),
    },

    # -----------------------------------------------------------------------
    "Imola": {
        "name":           "Autodromo Enzo e Dino Ferrari",
        "telemetry_name": "Imola",
        "lap_length_km":  4.909,
        "corners": [
            {"number": 1,  "name": "Tamburello",  "type": "fast",   "is_braking_zone": False, "typical_line_note": "Long fast left-hander; small lift required, front-limited on exit"},
            {"number": 2,  "name": "Villeneuve",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight chicane after Tamburello; heavy braking, curbing risk on right-left transition"},
            {"number": 5,  "name": "Acque Minerali","type":"slow",  "is_braking_zone": True,  "typical_line_note": "Chicane mid-sector, bumpy entry, traction exit sets up the back section"},
            {"number": 9,  "name": "Piratella",   "type": "fast",   "is_braking_zone": True,  "typical_line_note": "Fast right over crest; braking reference points unreliable in changing conditions"},
            {"number": 15, "name": "Variante Alta","type":"slow",   "is_braking_zone": True,  "typical_line_note": "Tight chicane, only real overtaking zone, DRS detection point"},
            {"number": 18, "name": "Rivazza",     "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Two-part right hander; good exit critical for pit straight run"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Variante Alta T15", "activation": "Pit straight after Rivazza"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "front",
            "reason":                  "High-speed chicanes and sustained front-left loading through fast corners; Piratella and Acque Minerali front-limited",
            "degradation_rating":      "low",
        },
        "overtaking_spots": [
            {"location": "Variante Alta", "technique": "Only real DRS overtaking point; must be alongside by braking zone or the door closes"},
        ],
        "key_engineer_notes": (
            "Imola is a track where overtaking is extremely difficult — qualifying and track position dominate. "
            "Only one DRS zone means the undercut must be used aggressively if stuck behind a slower car. "
            "Tyre degradation is low; one-stop is almost always optimal unless a safety car reshuffles strategy. "
            "Safety car probability is medium-high — the narrow track with gravel traps punishes mistakes severely. "
            "Prioritise a clean first sector — time lost at Tamburello and the chicane cannot be recovered through the rest of the lap."
        ),
    },

    # -----------------------------------------------------------------------
    "Monaco": {
        "name":           "Circuit de Monaco",
        "telemetry_name": "Monaco",
        "lap_length_km":  3.337,
        "corners": [
            {"number": 1,  "name": "Sainte Devote",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Slow right hander; first corner, track position critical, no overtaking — must be clear by here"},
            {"number": 5,  "name": "Massenet",       "type": "medium", "is_braking_zone": False, "typical_line_note": "Medium-speed left, wall on exit; any contact here is race-ending"},
            {"number": 6,  "name": "Casino",         "type": "medium", "is_braking_zone": True,  "typical_line_note": "Left-right at Casino Square; front locked under braking is a DNF risk"},
            {"number": 10, "name": "Mirabeau",       "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight right, very slow; rear lockup risk, heavy tyre load on rear-left"},
            {"number": 11, "name": "Loews/Hairpin",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hairpin; slowest corner in F1, traction exit critical to avoid slipstreaming through tunnel"},
            {"number": 12, "name": "Portier",        "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Right-left before tunnel, last braking before high-speed blind section"},
            {"number": 13, "name": "Tunnel",         "type": "fast",   "is_braking_zone": False, "typical_line_note": "Flat-out at 280km/h in darkness; exit chicane requires car in correct position"},
            {"number": 14, "name": "Nouvelle Chicane","type":"slow",   "is_braking_zone": True,  "typical_line_note": "Chicane after tunnel; curbing use maximises chicane speed, pit entry here"},
            {"number": 19, "name": "Rascasse",       "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Final hairpin; only late-race overtaking window under DRS but walls are very close"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Rascasse T19", "activation": "Pit straight (largely ineffective due to track width)"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Tight slow corners with heavy traction demand degrade rear tyres; front wear relatively low except at Casino",
            "degradation_rating":      "low",
        },
        "overtaking_spots": [
            {"location": "Sainte Devote", "technique": "Only viable after safety car restart; dive into T1 is the one chance"},
            {"location": "Rascasse",      "technique": "DRS rarely decisive; can attempt under braking but walls punish errors"},
        ],
        "key_engineer_notes": (
            "Monaco is the only circuit where track position completely overrides tyre strategy — overtaking is virtually impossible. "
            "The pit strategy must be used offensively: box before your rival on a safety car or VSC to take position, not just freshen tyres. "
            "Tyre degradation is the lowest of the year; a one-stop on medium or hard is standard in normal conditions. "
            "Safety car probability is the highest on the calendar — plan for at least one SC, often two. "
            "If ahead and in clean air, manage tyres aggressively and build the maximum gap before any VSC closes the field."
        ),
    },

    # -----------------------------------------------------------------------
    "Montreal": {
        "name":           "Circuit Gilles Villeneuve",
        "telemetry_name": "Montreal",
        "lap_length_km":  4.361,
        "corners": [
            {"number": 1,  "name": "Turn 1",      "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hard right off the start; outbraking is possible with DRS from pit straight"},
            {"number": 6,  "name": "Turn 6",      "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Medium hairpin; key traction exit to set up back section"},
            {"number": 8,  "name": "Hairpin",     "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Slowest point of the lap; DRS back straight leads here — main overtaking point"},
            {"number": 10, "name": "Wall of Champions","type":"slow","is_braking_zone": True,  "typical_line_note": "Tight right before pit straight; wall on exit claims champions, no late turn-in"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 8 hairpin", "activation": "Back straight after hairpin"},
            {"zone": 2, "detection": "Turn 11",        "activation": "Pit straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Heavy traction demand at the hairpin and Wall of Champions corner plus heavy braking cycles load rears",
            "degradation_rating":      "medium",
        },
        "overtaking_spots": [
            {"location": "T8 Hairpin",  "technique": "Best overtaking point — long DRS straight, heavy braking into slow hairpin"},
            {"location": "Turn 1",      "technique": "DRS from pit straight, viable late-braking move on the inside"},
        ],
        "key_engineer_notes": (
            "Montreal has medium degradation and favours a one-stop on most compound choices. "
            "Safety car probability is very high — the Wall of Champions claims multiple cars every year. "
            "A safety car almost always makes a two-stop viable; be ready to box immediately if the SC is deployed in laps 20-35. "
            "Undercut works well here due to clean air advantage on the back straight DRS zone. "
            "Watch brake temperatures — the stop-start nature of the lap places extreme thermal demand on brakes, which feeds into rear brake wear."
        ),
    },

    # -----------------------------------------------------------------------
    "Catalunya": {
        "name":           "Circuit de Barcelona-Catalunya",
        "telemetry_name": "Catalunya",
        "lap_length_km":  4.675,
        "corners": [
            {"number": 1,  "name": "Turn 1",    "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Slow right hander; heavy braking from high speed, understeer risk on entry"},
            {"number": 3,  "name": "Turn 3",    "type": "fast",   "is_braking_zone": False, "typical_line_note": "High-speed left, nearly flat; front-right loaded heavily through this section"},
            {"number": 5,  "name": "Turn 5",    "type": "medium", "is_braking_zone": True,  "typical_line_note": "Medium-speed right; traction zone onto short back straight"},
            {"number": 7,  "name": "Turn 7/8",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight chicane, heavy braking; dirt off-line makes defending difficult"},
            {"number": 9,  "name": "Turn 9",    "type": "fast",   "is_braking_zone": False, "typical_line_note": "Long fast right 'Campsa' corner — biggest commitment point on the lap"},
            {"number": 13, "name": "Turn 13/14","type": "slow",   "is_braking_zone": True,  "typical_line_note": "Final chicane before pit straight, only real overtaking opportunity"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 12", "activation": "Pit straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "front",
            "reason":                  "Turn 3 and Campsa T9 place enormous sustained lateral load on the front-right; front deg is the dominant variable",
            "degradation_rating":      "high",
        },
        "overtaking_spots": [
            {"location": "Turn 1",  "technique": "Only viable DRS point; outbraking possible but dirty air disrupts braking balance"},
        ],
        "key_engineer_notes": (
            "Barcelona is the benchmark tyre-wear circuit — front degradation through T3 and T9 is the dominant strategy factor. "
            "Two-stop is almost always optimal; front-right is the tyre to watch and determines when you box. "
            "Overtaking is very difficult without DRS, so the undercut from around lap 20-25 is the primary position-gaining tool. "
            "An overcut only works if the driver can lap on heavily worn fronts without losing more than 2s per lap. "
            "Ask for target lap times every 5 laps — front-right temperature and wear must be managed from lap 1."
        ),
    },

    # -----------------------------------------------------------------------
    "Austria": {
        "name":           "Red Bull Ring",
        "telemetry_name": "Austria",
        "lap_length_km":  4.318,
        "corners": [
            {"number": 1,  "name": "Turn 1",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Slow right hander uphill; heavy deceleration, late apex gives best T2 line"},
            {"number": 2,  "name": "Turn 2",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hairpin at top of hill, DRS zone target; major overtaking point — uphill kills speed delta"},
            {"number": 3,  "name": "Turn 3",  "type": "fast",   "is_braking_zone": False, "typical_line_note": "Fast downhill right, near-flat; front load and commitment"},
            {"number": 4,  "name": "Turn 4",  "type": "fast",   "is_braking_zone": False, "typical_line_note": "Fast left, chicane exit — smooth hands through here protect rear tyre life"},
            {"number": 9,  "name": "Turn 9",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Final hairpin before pit straight; traction important for DRS detection"},
            {"number": 10, "name": "Turn 10", "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight right hander; exit onto main straight, second major overtaking zone"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 9",  "activation": "Back straight to Turn 2 (short but steep)"},
            {"zone": 2, "detection": "Turn 10", "activation": "Pit straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Two hard braking zones with heavy traction exits and downhill compressions load the rear disproportionately",
            "degradation_rating":      "medium",
        },
        "overtaking_spots": [
            {"location": "Turn 2",  "technique": "Uphill into hairpin, DRS from back straight; must be alongside before braking to hold the inside"},
            {"location": "Turn 10", "technique": "DRS from main straight, late braking into final hairpin"},
        ],
        "key_engineer_notes": (
            "Red Bull Ring is a short lap with high energy inputs — degradation is moderate but blistering risk exists on hard compounds. "
            "One-stop is standard on medium-hard; two-stop if on soft-medium due to the short stint on softs. "
            "Two DRS zones make overtaking possible; track position is less critical than at pure traction circuits. "
            "Safety car probability is low-medium; the runoff areas are generous and incidents tend to be contained. "
            "In changeable weather, the elevated circuit means conditions can shift quickly — monitor weather radar from lap 10 onward."
        ),
    },

    # -----------------------------------------------------------------------
    "Silverstone": {
        "name":           "Silverstone Circuit",
        "telemetry_name": "Silverstone",
        "lap_length_km":  5.891,
        "corners": [
            {"number": 1,  "name": "Copse",       "type": "fast",   "is_braking_zone": False, "typical_line_note": "High-speed right, flat in modern F1; front-left heavily loaded over entire corner"},
            {"number": 3,  "name": "Maggotts/Becketts","type":"fast","is_braking_zone": False, "typical_line_note": "Iconic high-speed chicane complex; the biggest front-axle test of the season"},
            {"number": 6,  "name": "Chapel",       "type": "fast",   "is_braking_zone": False, "typical_line_note": "Fast right exit onto Hangar straight; run-out here costs time the full length of the straight"},
            {"number": 7,  "name": "Stowe",        "type": "medium", "is_braking_zone": True,  "typical_line_note": "Medium-speed right at Hangar straight end; car settles before Vale"},
            {"number": 9,  "name": "Vale/Club",    "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Slow chicane, tricky balance between traction and kerb usage"},
            {"number": 15, "name": "Luffield",     "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight right before Wellington; exit speed key for pit straight DRS"},
            {"number": 18, "name": "Brooklands/Woodcote","type":"medium","is_braking_zone": True, "typical_line_note": "Medium complex before pit straight; DRS detection in this region"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 16", "activation": "Pit straight toward Copse"},
            {"zone": 2, "detection": "Turn 5",  "activation": "Hangar straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "front",
            "reason":                  "Maggotts-Becketts complex places the highest sustained lateral load on front tyres of any circuit on the calendar",
            "degradation_rating":      "high",
        },
        "overtaking_spots": [
            {"location": "Turn 1 Copse",  "technique": "Long DRS into Copse — outbraking viable on inside but Copse is fast"},
            {"location": "Stowe",         "technique": "DRS from Hangar straight, medium-speed braking zone, more room"},
        ],
        "key_engineer_notes": (
            "Silverstone is the front-tyre circuit — Maggotts-Becketts is the most demanding sustained front load in the calendar. "
            "Two-stop is virtually always optimal; the front-left wear rate through the Becketts complex determines pit timing. "
            "If the driver reports understeer at Maggotts, the fronts are going off and you have 4-6 laps before significant lap time loss. "
            "Undercut is powerful from lap 20-30 on a 52-lap race; a 5-lap fresher tyre advantage is worth 1.5-2s per lap at Silverstone. "
            "Weather is unpredictable — Silverstone can change conditions within a single lap, so keep wet tyre readiness on standby from lap 15 onward."
        ),
    },

    # -----------------------------------------------------------------------
    "Spa": {
        "name":           "Circuit de Spa-Francorchamps",
        "telemetry_name": "Spa",
        "lap_length_km":  7.004,
        "corners": [
            {"number": 1,  "name": "La Source",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight hairpin at the top of the hill; dive to the inside is the primary pass at the start"},
            {"number": 3,  "name": "Eau Rouge/Raidillon","type":"fast","is_braking_zone": False,"typical_line_note": "Iconic uphill esses, flat in race conditions; energy through floor under compression"},
            {"number": 5,  "name": "Kemmel Straight","type":"fast",  "is_braking_zone": False, "typical_line_note": "Not a corner — 1km straight after Raidillon, highest speed of the lap"},
            {"number": 6,  "name": "Les Combes",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Chicane at end of Kemmel; biggest braking zone, most overtaking attempts end here"},
            {"number": 10, "name": "Pouhon",       "type": "fast",   "is_braking_zone": False, "typical_line_note": "Fast downhill double-apex left; sustained front-left load, second only to Becketts"},
            {"number": 17, "name": "Stavelot",     "type": "medium", "is_braking_zone": True,  "typical_line_note": "Medium-speed right before final section, traction exit feeds Bus Stop"},
            {"number": 19, "name": "Bus Stop Chicane","type":"slow",  "is_braking_zone": True,  "typical_line_note": "Final chicane, heavy braking; cutting this corner can gain a place but risks penalty"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Bus Stop T19", "activation": "Kemmel straight (longest DRS zone on calendar)"},
            {"zone": 2, "detection": "T1 La Source", "activation": "Pit straight (shorter)"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "front",
            "reason":                  "Pouhon and Raidillon-exit compressions load the front axle; rear is gentler due to long straights resetting load",
            "degradation_rating":      "low",
        },
        "overtaking_spots": [
            {"location": "Les Combes",    "technique": "Kemmel DRS the longest on the calendar; outbrake into T6 with a run up the hill"},
            {"location": "La Source T1",  "technique": "Shorter DRS but high-speed approach; T1 hairpin is wide enough for a side-by-side"},
        ],
        "key_engineer_notes": (
            "Spa is the longest circuit on the calendar with very low degradation — one-stop is almost always optimal. "
            "The biggest variable is weather: Spa can rain on one sector while the rest is dry, forcing an asymmetric tyre strategy. "
            "Safety car probability is high; the long lap and changeable conditions create frequent incidents. "
            "Under safety car at Spa, always consider pitting — the long lap means a lapped car loses significant time relative to the field. "
            "The Kemmel DRS zone is so long that a 0.5s gap at the detection point is closeable; defend early into Bus Stop when under pressure."
        ),
    },

    # -----------------------------------------------------------------------
    "Hungaroring": {
        "name":           "Hungaroring",
        "telemetry_name": "Hungaroring",
        "lap_length_km":  4.381,
        "corners": [
            {"number": 1,  "name": "Turn 1",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Heavy braking into tight right; only viable overtaking on this track under heavy braking"},
            {"number": 2,  "name": "Turn 2",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Left hairpin after T1; important to carry momentum through T1-T2 sequence"},
            {"number": 4,  "name": "Turn 4",  "type": "fast",   "is_braking_zone": False, "typical_line_note": "Fast right over crest; committed entry, front-right loaded on landing"},
            {"number": 6,  "name": "Turn 6",  "type": "medium", "is_braking_zone": True,  "typical_line_note": "Medium hairpin, key traction zone for back section"},
            {"number": 11, "name": "Turn 11", "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight right before main straight, DRS detection; traction exit onto pit straight"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 14", "activation": "Pit straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Tight and twisty with heavy traction demand; rear-limited circuit with high lateral loads through T4 and T6",
            "degradation_rating":      "medium",
        },
        "overtaking_spots": [
            {"location": "Turn 1", "technique": "Only viable pass; DRS from pit straight into the hard-braking T1 hairpin"},
        ],
        "key_engineer_notes": (
            "Hungary is the Monaco of non-street circuits — overtaking is nearly impossible outside of Turn 1. "
            "One-stop is almost always the right strategy regardless of degradation, because a two-stop loses positions that cannot be reclaimed. "
            "If stuck in traffic, the undercut at Turn 1 is the only tool — box before your rival and use clean air to build the gap. "
            "Safety car probability is low; the narrow track limits incident likelihood but a SC can completely reorder strategy. "
            "Focus on clean exits from T6 and T11 — the traction zones onto the pit straight determine DRS opportunity in the following lap."
        ),
    },

    # -----------------------------------------------------------------------
    "Zandvoort": {
        "name":           "Circuit Zandvoort",
        "telemetry_name": "Zandvoort",
        "lap_length_km":  4.259,
        "corners": [
            {"number": 1,  "name": "Tarzan",       "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight hairpin at end of pit straight; primary overtaking and undercut trigger point"},
            {"number": 3,  "name": "Hugenholtzbocht","type":"fast",   "is_braking_zone": False, "typical_line_note": "Banked high-speed right; banking allows higher speed than flat equivalent"},
            {"number": 7,  "name": "Scheivlak",    "type": "fast",   "is_braking_zone": False, "typical_line_note": "Fast right, committed at over 260km/h; front-left loaded heavily"},
            {"number": 9,  "name": "Arie Luyendijk","type":"fast",   "is_braking_zone": False, "typical_line_note": "Banked high-speed right; banking allows flat-out approach to main straight"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 9", "activation": "Pit straight to Tarzan"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "front",
            "reason":                  "Scheivlak and Hugenholtz place sustained lateral load on front tyres; banking reduces some rear loading",
            "degradation_rating":      "medium",
        },
        "overtaking_spots": [
            {"location": "Tarzan T1", "technique": "Only real DRS braking zone on the circuit — must be close at detection point"},
        ],
        "key_engineer_notes": (
            "Zandvoort is a short circuit with only one effective DRS zone — passing is very hard and track position is critical. "
            "One-stop strategy is standard; the narrow track makes it almost impossible to reclaim positions lost in the pit cycle. "
            "Undercut is the primary strategy tool — use it before your immediate rival, not reactively. "
            "Safety car probability is medium; the sand bordering the track can cause loss of control and VSC situations. "
            "The banked final corner means tyre temperatures build quickly on the out-lap — check for unusual graining on the first new tyre lap."
        ),
    },

    # -----------------------------------------------------------------------
    "Monza": {
        "name":           "Autodromo Nazionale Monza",
        "telemetry_name": "Monza",
        "lap_length_km":  5.793,
        "corners": [
            {"number": 1,  "name": "Variante del Rettifilo","type":"slow","is_braking_zone": True,  "typical_line_note": "First chicane; heavy braking from 340km/h, inside kerb can launch car if taken too aggressively"},
            {"number": 3,  "name": "Curva Grande",          "type":"fast","is_braking_zone": False, "typical_line_note": "Fast right, nearly flat; slight compression on exit loads front briefly"},
            {"number": 4,  "name": "Variante della Roggia", "type":"slow","is_braking_zone": True,  "typical_line_note": "Second chicane; heavy braking into tight left-right, key traction point"},
            {"number": 6,  "name": "Lesmo 1",               "type":"fast","is_braking_zone": True,  "typical_line_note": "Fast right, requires late apex for Lesmo 2 entry; front-limited through here"},
            {"number": 7,  "name": "Lesmo 2",               "type":"fast","is_braking_zone": True,  "typical_line_note": "Tighter fast right than Lesmo 1; rear traction out of here sets up the long Ascari run"},
            {"number": 8,  "name": "Ascari Chicane",        "type":"slow","is_braking_zone": True,  "typical_line_note": "High-speed chicane at over 300km/h; kerbs are large, ride height critical"},
            {"number": 11, "name": "Parabolica/Curva Alboreto","type":"medium","is_braking_zone": True, "typical_line_note": "Long medium-speed right before pit straight; exit speed here determines entire straight speed"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Ascari T8",    "activation": "Back straight toward first chicane"},
            {"zone": 2, "detection": "Parabolica T11","activation": "Pit straight (longest straight in F1)"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Low downforce setup means less mechanical grip reliance; heavy braking into chicanes generates longitudinal rear load",
            "degradation_rating":      "low",
        },
        "overtaking_spots": [
            {"location": "Variante del Rettifilo T1", "technique": "Longest DRS run on the calendar; outbraking into T1 is the primary pass — inside line into chicane"},
            {"location": "Variante della Roggia T4",  "technique": "Secondary DRS zone, achievable from the back straight"},
        ],
        "key_engineer_notes": (
            "Monza is the fastest circuit on the calendar — low downforce means low drag, high tyre stress from braking not cornering. "
            "One-stop is the overwhelming favourite; degradation is minimal due to low downforce lateral loads. "
            "The undercut is not as powerful here because lap time delta on fresh tyres is smaller than at high-deg circuits. "
            "DRS on the main straight is decisive; a gap of under 0.5s at Parabolica detection means a pass is highly likely into T1. "
            "Safety car probability is medium — the chicanes are incident-prone, especially at the start when cars are close."
        ),
    },

    # -----------------------------------------------------------------------
    "Baku": {
        "name":           "Baku City Circuit",
        "telemetry_name": "Baku",
        "lap_length_km":  6.003,
        "corners": [
            {"number": 1,  "name": "Turn 1",     "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hard right off the start, heavy braking from high speed"},
            {"number": 3,  "name": "Castle Turn","type": "slow",   "is_braking_zone": True,  "typical_line_note": "Slow tight right; narrowest section of any F1 circuit, one line only, very high wall risk"},
            {"number": 8,  "name": "Turn 8",     "type": "fast",   "is_braking_zone": False, "typical_line_note": "High-speed sweeper, flat; wall close on exit, no margin for error"},
            {"number": 15, "name": "Turn 15/16", "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Chicane before the long main straight; traction onto the straight determines DRS run"},
            {"number": 20, "name": "Turn 20",    "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Final hairpin; walls very close, major braking reference is manhole covers in the road"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 18", "activation": "2.2km main straight (longest DRS run on calendar)"},
            {"zone": 2, "detection": "Turn 3",  "activation": "Castle straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Long straight followed by heavy braking and traction from the hairpin; castle section is gentle but tight",
            "degradation_rating":      "low",
        },
        "overtaking_spots": [
            {"location": "Turn 1",  "technique": "2.2km DRS run onto T1 — closing speed is enormous, side-by-side from mid-straight"},
            {"location": "Turn 20", "technique": "Castle straight DRS into final hairpin, secondary opportunity"},
        ],
        "key_engineer_notes": (
            "Baku's 2.2km main straight makes DRS closing speed the highest of the year — a gap of 1.5s is closeable with DRS. "
            "One-stop is standard; safety car probability is among the highest on the calendar due to walls everywhere. "
            "Always have a box call ready for any safety car — the long main straight means a lapped car loses massive time. "
            "Tyre degradation is low because the long straights give tyres recovery time between corners. "
            "The castle section forces a very specific line — any incident there triggers a safety car and a full neutralisation."
        ),
    },

    # -----------------------------------------------------------------------
    "Singapore": {
        "name":           "Marina Bay Street Circuit",
        "telemetry_name": "Singapore",
        "lap_length_km":  4.940,
        "corners": [
            {"number": 1,  "name": "Turn 1",      "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hard right, heavy braking; front-left locks easily on cold asphalt in the night race heat"},
            {"number": 5,  "name": "Anderson Bridge","type":"slow",  "is_braking_zone": True,  "typical_line_note": "Tight chicane through the bridge opening; walls within centimetres, no room for error"},
            {"number": 10, "name": "Turn 10",      "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight right, key braking zone for sector 2"},
            {"number": 14, "name": "Turn 14/15",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hairpin complex through the financial district; bumpy surface, heavy rear loading"},
            {"number": 18, "name": "Turn 18",      "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight left before the Singapore Sling; wall on inside of T18 takes cars regularly"},
            {"number": 23, "name": "Turn 23",      "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Final hairpin before pit straight; DRS detection area, heavy rear-left loading"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 21", "activation": "Pit straight toward T1"},
            {"zone": 2, "detection": "Turn 9",  "activation": "After T9 onto back section"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Maximum 18 slow corners per lap with constant traction demand; rear tyres never fully cool, thermal degradation is dominant",
            "degradation_rating":      "high",
        },
        "overtaking_spots": [
            {"location": "Turn 1",  "technique": "DRS from pit straight, outbrake on the inside; narrow circuit limits options"},
            {"location": "Turn 10", "technique": "Secondary DRS zone, difficult but possible with a strong run through sector 1"},
        ],
        "key_engineer_notes": (
            "Singapore is the hardest night race on the calendar — high heat and humidity degrade rear tyres rapidly. "
            "Two-stop is the standard due to rear degradation; push hard in the first stint then manage in the second. "
            "Safety car probability is the joint-highest on the calendar with Monaco — plan for at least one SC. "
            "Under safety car at Singapore, box immediately if tyres are over 15 laps old — the safety car window is invaluable. "
            "The circuit is too narrow to overtake easily; track position and pit timing are the only real strategy levers."
        ),
    },

    # -----------------------------------------------------------------------
    "Suzuka": {
        "name":           "Suzuka International Racing Course",
        "telemetry_name": "Suzuka",
        "lap_length_km":  5.807,
        "corners": [
            {"number": 1,  "name": "Turn 1/2",    "type": "fast",   "is_braking_zone": False, "typical_line_note": "Fast sweeping right, almost flat; front-right loaded over the entire corner"},
            {"number": 3,  "name": "S-Curves",    "type": "fast",   "is_braking_zone": False, "typical_line_note": "Iconic fast S-curves, all linked; the hardest sustained front loading of any corner sequence"},
            {"number": 7,  "name": "Dunlop",      "type": "medium", "is_braking_zone": True,  "typical_line_note": "Medium-speed right; traction zone through the overpass section"},
            {"number": 11, "name": "Hairpin",     "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Very tight hairpin; heavy braking from back straight, primary overtaking point"},
            {"number": 13, "name": "Spoon Curve", "type": "fast",   "is_braking_zone": True,  "typical_line_note": "Long double-apex right; must be in correct mid-corner position for exit onto 130R section"},
            {"number": 15, "name": "130R",        "type": "fast",   "is_braking_zone": False, "typical_line_note": "Nearly flat-out left at 300km/h; commitment corner, aerodynamic platform critical"},
            {"number": 16, "name": "Casio Triangle","type":"slow",  "is_braking_zone": True,  "typical_line_note": "Final chicane, heavy braking from 130R; traction exit determines pit straight DRS run"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Casio T16", "activation": "Pit straight toward T1"},
            {"zone": 2, "detection": "T11 Hairpin","activation": "Back straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "front",
            "reason":                  "S-curves and 130R region place the highest sustained front loads of the calendar; front-left is the critical tyre",
            "degradation_rating":      "high",
        },
        "overtaking_spots": [
            {"location": "T11 Hairpin",    "technique": "Long DRS from back straight into slowest point of lap; primary passing zone"},
            {"location": "Turn 1",         "technique": "Main straight DRS into T1; requires very close approach at detection"},
        ],
        "key_engineer_notes": (
            "Suzuka is one of the most demanding circuits on the calendar — the S-curves generate extreme sustained front loads. "
            "Two-stop is usually optimal due to front-left degradation through the S-curves and Spoon corner. "
            "The hairpin is the only overtaking point outside of DRS, so track position after sector 1 matters. "
            "Undercut window is typically laps 20-28 on a 53-lap race; front-left temperature will give you the trigger signal. "
            "In wet conditions, 130R becomes extremely dangerous and Safety Car deployment is near-certain."
        ),
    },

    # -----------------------------------------------------------------------
    "Texas": {
        "name":           "Circuit of the Americas",
        "telemetry_name": "Texas",
        "lap_length_km":  5.513,
        "corners": [
            {"number": 1,  "name": "Turn 1",      "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Slow right hander; uphill blind braking, late apex sets up the long left at Turn 2, heaviest braking of the lap"},
            {"number": 2,  "name": "Turn 2/3",    "type": "fast",   "is_braking_zone": False, "typical_line_note": "Long flowing left after T1, Maggotts-style; front-left heavily loaded over the arc"},
            {"number": 11, "name": "Turn 11",     "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hairpin at bottom of the stadium section; long back straight DRS into this point"},
            {"number": 12, "name": "Turn 12/13",  "type": "fast",   "is_braking_zone": False, "typical_line_note": "High-speed esses; similar to Becketts, high front load"},
            {"number": 15, "name": "Turn 15",     "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight hairpin before the sweeping final sector"},
            {"number": 19, "name": "Turn 19/20",  "type": "fast",   "is_braking_zone": False, "typical_line_note": "Fast sweeping left-right finale; exit speed maximised for DRS on main straight"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 10", "activation": "Back straight to T11"},
            {"zone": 2, "detection": "Turn 20", "activation": "Pit straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "front",
            "reason":                  "T2-T3 flowing left and T12-T13 esses generate Silverstone-like front loads; COTA is bumpy amplifying wear",
            "degradation_rating":      "high",
        },
        "overtaking_spots": [
            {"location": "Turn 1",  "technique": "Hardest braking zone uphill — outbraking into T1 is the signature COTA move"},
            {"location": "Turn 11", "technique": "DRS from back straight into hairpin, high closing speed"},
        ],
        "key_engineer_notes": (
            "COTA is a technically demanding circuit combining Silverstone-style high-speed corners with heavy braking zones. "
            "Front tyre degradation through T2-T3 is the key variable — similar to Silverstone in its severity. "
            "Two-stop is the strong default; on a one-stop, front wear into the final 15 laps becomes critical. "
            "The bumpy surface amplifies tyre wear versus a smooth circuit — account for 10-15% higher deg in pre-race modelling. "
            "Safety car probability is medium; T1 braking at race start is a frequent contact point."
        ),
    },

    # -----------------------------------------------------------------------
    "Mexico": {
        "name":           "Autodromo Hermanos Rodriguez",
        "telemetry_name": "Mexico",
        "lap_length_km":  4.304,
        "corners": [
            {"number": 1,  "name": "Foro Sol Esses","type": "slow", "is_braking_zone": True,  "typical_line_note": "Tight slow chicane at start; heavy braking, kerb risk high, primary overtaking point"},
            {"number": 4,  "name": "Turn 4/5",     "type": "medium","is_braking_zone": True,  "typical_line_note": "Medium-speed section; thin air means less aero drag but downforce also reduced"},
            {"number": 6,  "name": "Turn 6",       "type": "slow",  "is_braking_zone": True,  "typical_line_note": "Tight right, main traction zone through the middle section"},
            {"number": 12, "name": "Peraltada",    "type": "fast",  "is_braking_zone": False, "typical_line_note": "Long stadium right-hander; medium-speed sustained load, crowd directly trackside"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 12", "activation": "Pit straight (thin air = highest speeds)"},
            {"zone": 2, "detection": "Turn 3",  "activation": "Back straight after esses"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "High altitude reduces aerodynamic load, increasing mechanical tyre load; rear traction out of slow corners under reduced aero grip",
            "degradation_rating":      "medium",
        },
        "overtaking_spots": [
            {"location": "Foro Sol T1", "technique": "Long DRS on main straight, heavy braking into T1 esses — most likely passing point"},
        ],
        "key_engineer_notes": (
            "Mexico's 2,285m altitude means aerodynamic downforce is ~20% lower than sea level — the car behaves differently in all corners. "
            "Tyre wear is higher than expected due to reduced aero grip forcing more mechanical load; account for faster degradation in models. "
            "DRS closing speed is very high on the main straight due to thin air and reduced drag — gaps close fast. "
            "One-stop is the standard strategy; safety car probability is medium due to tight Turn 1 and limited run-off. "
            "ERS is less effective at altitude — fewer regen cycles per lap reduce deploy availability over a stint."
        ),
    },

    # -----------------------------------------------------------------------
    "Brazil": {
        "name":           "Autodromo Jose Carlos Pace (Interlagos)",
        "telemetry_name": "Brazil",
        "lap_length_km":  4.309,
        "corners": [
            {"number": 1,  "name": "Senna S",     "type": "slow",  "is_braking_zone": True,  "typical_line_note": "Tight right-left esses at the top; off-line grip is low, outbraking difficult"},
            {"number": 4,  "name": "Descida do Lago","type":"slow", "is_braking_zone": True,  "typical_line_note": "Long hairpin complex downhill; primary overtaking under DRS from back section"},
            {"number": 7,  "name": "Ferradura",   "type": "slow",  "is_braking_zone": True,  "typical_line_note": "U-bend, medium-speed; exit traction important for the infield section"},
            {"number": 12, "name": "Subida dos Boxes","type":"slow","is_braking_zone": True,  "typical_line_note": "Final chicane before pit straight; anti-clockwise circuit means T12 is a right-left sequence"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 11", "activation": "Pit straight"},
            {"zone": 2, "detection": "Turn 3",  "activation": "Back section toward T4 hairpin"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "front",
            "reason":                  "Anti-clockwise circuit loads the front-right, opposite to most circuits; Senna S places sustained load through T1-T2 on the right front",
            "degradation_rating":      "medium",
        },
        "overtaking_spots": [
            {"location": "Descida do Lago T4", "technique": "DRS from back section into the hairpin; high closing speed, late braking viable"},
            {"location": "Turn 1 Senna S",     "technique": "Main straight DRS; inside line into T1 but limited run-off makes contact likely"},
        ],
        "key_engineer_notes": (
            "Brazil is an anti-clockwise circuit — all front loading goes to the right front instead of the left. "
            "Weather is unpredictable; Sao Paulo afternoon storms are common and can change strategy completely in the final 20 laps. "
            "One-stop is standard but a safety car is very likely; always have a two-stop model ready for a lap-20-35 box call. "
            "Undercut works well here due to the two DRS zones giving a clean-air advantage. "
            "Front-right tyre life is the key metric — if it's degrading fast, you must undercut before your rival or they will pull ahead."
        ),
    },

    # -----------------------------------------------------------------------
    "Las Vegas": {
        "name":           "Las Vegas Strip Circuit",
        "telemetry_name": "Las Vegas",
        "lap_length_km":  6.201,
        "corners": [
            {"number": 1,  "name": "Turn 1",   "type": "slow",  "is_braking_zone": True,  "typical_line_note": "Hard right after the start; cold night temperatures affect tyre warm-up significantly"},
            {"number": 5,  "name": "Turn 5",   "type": "slow",  "is_braking_zone": True,  "typical_line_note": "Chicane section through the casino district; heavy braking, tight walls"},
            {"number": 12, "name": "Turn 12",  "type": "slow",  "is_braking_zone": True,  "typical_line_note": "Hairpin at end of the Strip straight; DRS into this point, primary overtaking opportunity"},
            {"number": 14, "name": "Turn 14",  "type": "slow",  "is_braking_zone": True,  "typical_line_note": "Final tight chicane before pit straight; smooth exit maximises DRS straight speed"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 10", "activation": "Las Vegas Strip straight (2km+)"},
            {"zone": 2, "detection": "Turn 14", "activation": "Pit straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Cold night temperatures mean tyres struggle to reach operating window; thermal graining is front-dominant early, rear deg dominant in steady state",
            "degradation_rating":      "low",
        },
        "overtaking_spots": [
            {"location": "Turn 12",  "technique": "Long DRS down the Strip, heavy braking into hairpin — high closing speed"},
            {"location": "Turn 1",   "technique": "Pit straight DRS, viable on inside with cold-tyre caution"},
        ],
        "key_engineer_notes": (
            "Las Vegas is a night race in cold desert conditions — tyre warm-up is the biggest challenge, especially in qualifying and early race laps. "
            "One-stop is standard due to low degradation; soft compounds often last significantly longer than models predict in the cold. "
            "The Strip DRS zone is extremely long — closing from 1.5s with DRS is achievable, so gaps evaporate quickly. "
            "Safety car probability is high — cold asphalt, barriers close to the circuit edge, and inexperienced spectator areas create incident risk. "
            "Monitor tyre temperatures actively in the first 5 laps — if they are below operating window, the driver must push harder into slow corners to generate heat."
        ),
    },

    # -----------------------------------------------------------------------
    "Losail": {
        "name":           "Lusail International Circuit",
        "telemetry_name": "Losail",
        "lap_length_km":  5.380,
        "corners": [
            {"number": 1,  "name": "Turn 1",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hard right off pit straight; DRS zone, primary overtaking point under braking"},
            {"number": 6,  "name": "Turn 6",   "type": "fast",   "is_braking_zone": False, "typical_line_note": "Long fast sweeper, similar to T3 at Suzuka; sustained front load"},
            {"number": 12, "name": "Turn 12",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight hairpin, DRS detection point, generates heavy traction demand on exit"},
            {"number": 16, "name": "Turn 16",  "type": "fast",   "is_braking_zone": False, "typical_line_note": "Final high-speed sweeper before pit straight; committed approach sets up DRS run"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 14", "activation": "Pit straight"},
            {"zone": 2, "detection": "Turn 1",  "activation": "Back straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "High traction demand out of T12 and desert sand on track increases abrasive wear across all four tyres, rear dominant",
            "degradation_rating":      "high",
        },
        "overtaking_spots": [
            {"location": "Turn 1",  "technique": "Long DRS from main straight; outbraking into T1 is the primary pass"},
            {"location": "Turn 12", "technique": "Back straight DRS, heavy braking into hairpin"},
        ],
        "key_engineer_notes": (
            "Losail has very high tyre degradation due to the abrasive desert surface and sand blown onto the circuit. "
            "Two-stop is the standard strategy; push hard in the first stint then manage degradation in the second. "
            "Sand drift can dramatically change grip levels between laps, especially in early stints — monitor lap time variance carefully. "
            "Safety car probability is medium; limited runoff in some areas and the sand contamination risk near barriers. "
            "The circuit rewards late braking at T1 — if behind on track, the undercut plus clean air advantage is the primary strategy tool."
        ),
    },

    # -----------------------------------------------------------------------
    "Abu Dhabi": {
        "name":           "Yas Marina Circuit",
        "telemetry_name": "Abu Dhabi",
        "lap_length_km":  5.281,
        "corners": [
            {"number": 1,  "name": "Turn 1",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hard right from pit straight; late braking viable with DRS advantage"},
            {"number": 5,  "name": "Turn 5",   "type": "fast",   "is_braking_zone": False, "typical_line_note": "Fast section through the hotel — high-speed sweepers, front-limited under the canopy"},
            {"number": 9,  "name": "Turn 9",   "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Hairpin, primary braking zone; DRS detection before T9, main overtaking point"},
            {"number": 11, "name": "Turn 11",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Tight chicane sequence; traction zone before the marina section"},
            {"number": 18, "name": "Turn 18",  "type": "slow",   "is_braking_zone": True,  "typical_line_note": "Final slow complex; exit speed onto main straight determines DRS run for following lap"},
        ],
        "drs_zones": [
            {"zone": 1, "detection": "Turn 7",  "activation": "After T7 toward T9 hairpin"},
            {"zone": 2, "detection": "Turn 12", "activation": "Back section straight"},
            {"zone": 3, "detection": "Turn 18", "activation": "Pit straight"},
        ],
        "tyre_characteristics": {
            "faster_degradation_axle": "rear",
            "reason":                  "Three slow hairpins with heavy traction demand each lap; rear deg amplified by cool night temperatures dropping grip",
            "degradation_rating":      "medium",
        },
        "overtaking_spots": [
            {"location": "Turn 9 hairpin", "technique": "DRS zone toward T9; heavy braking, outbraking viable on inside"},
            {"location": "Turn 1",         "technique": "Pit straight DRS, late braking into T1"},
        ],
        "key_engineer_notes": (
            "Abu Dhabi is the season finale — often a one-stop but three DRS zones make overtaking accessible. "
            "Night temperatures drop tyre performance and rear degradation is amplified by three heavy traction hairpins. "
            "Undercut works well from lap 25-35 on a 58-lap race; the multiple DRS zones mean track position is less valuable than at Monaco-type circuits. "
            "Safety car probability is low-medium; generous runoff areas contain most incidents. "
            "Fuel mapping is critical for the final race — manage to the end but if DRS is required to defend, full deploy is warranted."
        ),
    },
}


# ---------------------------------------------------------------------------
# Public helper: list all known telemetry names
# ---------------------------------------------------------------------------

def all_telemetry_names() -> list[str]:
    """Returns a sorted list of every telemetry_name in the knowledge base.

    Parameters:
        None.

    Returns:
        Sorted list of telemetry name strings.
    """
    return sorted(TRACK_DATA.keys())
