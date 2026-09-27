"""
Practice Programmes — six telemetry-driven session plans for F1 25.

Each programme defines an objective, recommended lap count, tyre suggestion,
telemetry targets, coaching focus areas, and engineer script lines for
briefout (when starting) and debrief (when returning to pit).

These programmes translate the Telemetry Practice Framework into structured
data that the engineer AI uses to frame advice during practice sessions.
No AI calls are made here — this is pure data and selection logic.
"""


# ---------------------------------------------------------------------------
# Session length thresholds for programme recommendation
# ---------------------------------------------------------------------------

SHORT_SESSION_MAX_LAPS   = 14   # sessions with ≤ this many laps
MEDIUM_SESSION_MAX_LAPS  = 30   # sessions with ≤ this many laps (above short)


# ---------------------------------------------------------------------------
# Programme definitions
# ---------------------------------------------------------------------------

PROGRAMMES: list[dict] = [

    {
        "id":                 "track_baseline",
        "name":               "Track Baseline and Line Consistency",
        "objective":          "Establish consistent geometric line and apex speed benchmarks across all corners.",
        "session_type":       "both",
        "recommended_laps":   3,
        "tyre_recommendation":"Medium compound",
        "telemetry_targets":  [
            "steering_angle",
            "minimum_apex_speed",
            "lap_distance",
            "speed_trace",
        ],
        "coaching_focus":     [
            "smoother_steering",
            "hit_apex",
            "avoid_mid_corner_correction",
            "consistent_braking_point",
        ],
        "engineer_briefout": (
            "Going out on the track baseline programme. "
            "Three laps on the medium. "
            "Focus on smooth steering inputs and hitting the same apex every lap. "
            "I am tracking your minimum speed at each corner and your steering consistency."
        ),
        "engineer_debrief": (
            "Good run. "
            "I have your baseline geometric data. "
            "I will now compare your apex speeds corner by corner and identify where "
            "you are losing the most time against reference."
        ),
        "data_to_store":      [
            "steering_angle_per_sector",
            "minimum_corner_speed",
            "lap_time_ms",
            "sector_times",
            "tyre_compound",
        ],
    },

    {
        "id":                 "tyre_degradation",
        "name":               "Tyre Degradation and Slip Control",
        "objective":          "Map thermal degradation curve and identify slip ratio spikes for race strategy.",
        "session_type":       "race_prep",
        "recommended_laps":   8,
        "tyre_recommendation":"Race compound — same as expected race start tyre",
        "telemetry_targets":  [
            "tyre_surface_temp",
            "tyre_inner_temp",
            "wheel_slip",
            "throttle_pct",
            "tyre_wear",
        ],
        "coaching_focus":     [
            "progressive_throttle",
            "reduce_wheelspin",
            "tyre_warming",
            "reduce_steering_lock",
            "trail_braking",
        ],
        "engineer_briefout": (
            "Tyre degradation programme. "
            "Eight laps on the race compound. "
            "Drive at 95 percent. "
            "I need a consistent rhythm — no outlier laps. "
            "I am building your degradation curve and tracking thermal spikes from wheelspin."
        ),
        "engineer_debrief": (
            "Stint data collected. "
            "I have your degradation slope and thermal profile. "
            "I will use this to calculate your race pit window."
        ),
        "data_to_store":      [
            "tyre_wear_per_lap",
            "tyre_temp_per_lap",
            "lap_time_ms",
            "sector_times",
            "throttle_trace_avg",
            "wheelspin_events",
            "tyre_compound",
            "fuel_load",
        ],
    },

    {
        "id":                 "fuel_optimisation",
        "name":               "Fuel Consumption Optimisation",
        "objective":          "Map optimal lift-and-coast points to minimise fuel consumption without losing pace.",
        "session_type":       "race_prep",
        "recommended_laps":   5,
        "tyre_recommendation":"Hard compound",
        "telemetry_targets":  [
            "fuel_remaining_laps",
            "throttle_pct",
            "brake_pct",
            "speed_trace",
            "coasting_time",
        ],
        "coaching_focus":     [
            "lift_earlier",
            "coast_before_braking",
            "short_shift",
            "fuel_saving_technique",
        ],
        "engineer_briefout": (
            "Fuel optimisation programme. "
            "Five laps on the hard. "
            "I need you to lift completely off the throttle 50 to 100 metres before "
            "each hard braking zone. "
            "I am identifying the best lift and coast points on this circuit."
        ),
        "engineer_debrief": (
            "Fuel map complete. "
            "I now have your optimal lift and coast points per corner. "
            "This data will feed into race fuel strategy."
        ),
        "data_to_store":      [
            "fuel_consumed_per_lap",
            "coasting_time_per_sector",
            "throttle_trace_avg",
            "brake_trace_avg",
            "lap_time_ms",
            "sector_times",
        ],
    },

    {
        "id":                 "ers_mapping",
        "name":               "ERS Mapping",
        "objective":          "Map ERS deployment and harvesting efficiency across all straight and corner combinations.",
        "session_type":       "both",
        "recommended_laps":   4,
        "tyre_recommendation":"Medium compound",
        "telemetry_targets":  [
            "ers_store_pct",
            "ers_deploy_mode",
            "speed_at_traps",
            "throttle_pct",
        ],
        "coaching_focus":     [
            "ers_on_straight",
            "ers_on_exit",
            "harvest_before_braking",
            "deploy_timing",
        ],
        "engineer_briefout": (
            "ERS mapping programme. "
            "Four laps. "
            "I need you to manually engage overtake mode once the car settles "
            "straight in 3rd or 4th gear on each straight. "
            "Deactivate before braking to allow maximum harvesting under deceleration."
        ),
        "engineer_debrief": (
            "ERS map complete. "
            "I have your deployment and harvesting profile. "
            "I will identify if you are deploying too early in high drag zones."
        ),
        "data_to_store":      [
            "ers_store_per_sector",
            "ers_deploy_mode_per_sector",
            "speed_trap_readings",
            "lap_time_ms",
            "sector_times",
        ],
    },

    {
        "id":                 "peak_performance",
        "name":               "Single Lap Peak Performance",
        "objective":          "Simulate qualifying attack lap to establish single lap pace benchmark.",
        "session_type":       "quali_prep",
        "recommended_laps":   2,
        "tyre_recommendation":"Softest available compound",
        "telemetry_targets":  [
            "throttle_pct",
            "brake_pct",
            "minimum_corner_speed",
            "sector_times",
            "lap_time_ms",
        ],
        "coaching_focus":     [
            "brake_later",
            "throttle_earlier",
            "hit_kerbs",
            "hit_apex",
            "maximum_attack",
        ],
        "engineer_briefout": (
            "Peak performance programme. "
            "Two flying laps on the soft. "
            "Maximum attack. "
            "Heavy kerb utilisation, rapid brake pressure, immediate throttle pickup. "
            "I am comparing your inputs against the qualifying reference for this circuit."
        ),
        "engineer_debrief": (
            "Qualifying simulation complete. "
            "Lap time logged. "
            "I will now compare your sector splits against the reference and "
            "identify your biggest time losses."
        ),
        "data_to_store":      [
            "lap_time_ms",
            "sector_times",
            "throttle_trace_avg",
            "brake_trace_avg",
            "minimum_corner_speed",
            "steering_angle_per_sector",
            "tyre_compound",
        ],
    },

    {
        "id":                 "stint_consistency",
        "name":               "Stint Consistency and Strategy Validation",
        "objective":          "Build a long run degradation curve and validate pit window strategy.",
        "session_type":       "race_prep",
        "recommended_laps":   12,
        "tyre_recommendation":"Race compound",
        "telemetry_targets":  [
            "lap_time_ms",
            "sector_times",
            "tyre_wear",
            "tyre_temp",
            "fuel_remaining_laps",
        ],
        "coaching_focus":     [
            "consistent_rhythm",
            "avoid_outlier_laps",
            "progressive_throttle",
            "tyre_preservation",
        ],
        "engineer_briefout": (
            "Stint consistency programme. "
            "Twelve laps at 95 percent pace. "
            "Lock down a repeatable rhythm. "
            "No aggressive corrections or outlier laps. "
            "I am plotting your degradation curve to calculate the exact lap "
            "where pit window crossover triggers."
        ),
        "engineer_debrief": (
            "Long run complete. "
            "Degradation curve built. "
            "I now have enough data to set your race pit window. "
            "Lap time standard deviation and tyre wear slope logged."
        ),
        "data_to_store":      [
            "lap_time_ms",
            "sector_times",
            "tyre_wear_per_lap",
            "tyre_temp_per_lap",
            "fuel_remaining_per_lap",
            "lap_time_std_deviation",
            "tyre_compound",
            "fuel_load",
        ],
    },
]


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_programme_by_id(programme_id: str) -> dict | None:
    """Returns the programme dict matching the given id, or None.

    Parameters:
        programme_id: Unique identifier string, e.g. 'track_baseline'.

    Returns:
        Programme dict or None if not found.
    """
    for programme in PROGRAMMES:
        if programme["id"] == programme_id:
            return programme
    return None


def get_recommended_programmes(session_length_laps: int) -> list[str]:
    """Returns a list of programme ids suitable for the available lap count.

    Short session (≤ SHORT_SESSION_MAX_LAPS): baseline, peak performance, ERS mapping.
    Medium session (≤ MEDIUM_SESSION_MAX_LAPS): adds degradation and fuel optimisation.
    Long session (> MEDIUM_SESSION_MAX_LAPS): all six programmes.

    Parameters:
        session_length_laps: Total laps available in the session.

    Returns:
        Ordered list of programme id strings, highest priority first.
    """
    if session_length_laps <= SHORT_SESSION_MAX_LAPS:
        return ["track_baseline", "peak_performance", "ers_mapping"]
    if session_length_laps <= MEDIUM_SESSION_MAX_LAPS:
        return [
            "track_baseline",
            "tyre_degradation",
            "fuel_optimisation",
            "peak_performance",
            "ers_mapping",
        ]
    return [p["id"] for p in PROGRAMMES]
