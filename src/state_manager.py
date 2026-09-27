"""
Phase 3 — Race State Manager
Responsible for: wrapping the Phase 2 parser, maintaining a full lap history,
detecting significant race events by comparing successive state snapshots, and
producing a structured engineer briefing that Phase 4 (AI brain) will consume.
No AI or Claude API calls are made here. This is the data intelligence layer.

Key concepts:
  - race_state:  the live snapshot dict updated on every packet (from parser.py)
  - lap_history: a list of end-of-lap snapshots, one entry per completed lap
  - events:      a rolling list of the last MAX_RECENT_EVENTS notable occurrences
  - briefing:    the structured dict returned by get_engineer_briefing()
"""

import os
import socket
import time
from datetime import datetime

from parser import (parse_packet, update_race_state, empty_race_state,
                    parse_session_history, PACKET_ID_SESSION_HISTORY,
                    PACKET_ID_OFFSET)
from reference_lap import ReferenceLap
from session_data import SessionDataStore
from track_mapper import get_track_data


# ---------------------------------------------------------------------------
# Network constants
# ---------------------------------------------------------------------------

# F1 25 broadcasts telemetry on this port — must match in-game UDP settings
UDP_PORT = 20777

# Largest F1 25 packet is well under 2 KB; 4096 gives comfortable headroom
BUFFER_SIZE = 4096


# ---------------------------------------------------------------------------
# Time conversion constants
# ---------------------------------------------------------------------------

# Milliseconds in one minute — used when formatting lap times
MS_PER_MINUTE = 60_000

# Milliseconds in one second — used when formatting lap times
MS_PER_SECOND = 1_000


# ---------------------------------------------------------------------------
# Delta detection thresholds
# ---------------------------------------------------------------------------

# Tyre wear increase on a single corner in one state update that triggers
# a spike event (percentage points)
TYRE_WEAR_SPIKE_THRESHOLD_PCT = 2.0

# Wear levels that trigger warning and critical tyre events (percentage)
TYRE_WARNING_THRESHOLD_PCT  = 50.0
TYRE_CRITICAL_THRESHOLD_PCT = 80.0


# ---------------------------------------------------------------------------
# Stint detection constants
# ---------------------------------------------------------------------------

# If tyre_age_laps drops by this many laps or more, assume a pit stop occurred
# and the car is now on a fresh set (handles same-compound re-fits)
STINT_AGE_DROP_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Analytics constants
# ---------------------------------------------------------------------------

# Minimum number of laps on the current set before wear rate is meaningful
WEAR_RATE_MIN_LAPS = 2

# Number of laps on each side of the pace trend comparison window
# e.g. 3 means: average of last 3 laps vs average of the 3 laps before those
PACE_TREND_COMPARISON_LAPS = 3

# Number of tyre corners on the car — used when averaging all-corner wear
CORNERS_PER_CAR = 4

# Number of tyres on each axle — used when averaging per-axle wear
CORNERS_PER_AXLE = 2


# ---------------------------------------------------------------------------
# Display constants
# ---------------------------------------------------------------------------

# Maximum recent events kept in memory at any time
MAX_RECENT_EVENTS = 5

# Seconds between briefing prints in the standalone test harness
BRIEFING_DISPLAY_INTERVAL_SECONDS = 5.0

# Width of the display separator line
DISPLAY_SEPARATOR_WIDTH = 60

# Timestamp format used on event entries
EVENT_TIMESTAMP_FORMAT = "%H:%M:%S"


# ---------------------------------------------------------------------------
# Session type name sets — used to detect qualifying-to-race transition
# ---------------------------------------------------------------------------

QUALIFYING_SESSION_TYPES = frozenset({
    "Practice 1", "Practice 2", "Practice 3", "Short Practice",
    "Q1", "Q2", "Q3", "Short Qualifying", "One-Shot Qualifying",
})

RACE_SESSION_TYPES = frozenset({"Race", "Race 2", "Race 3"})


# ---------------------------------------------------------------------------
# Fields captured in the delta snapshot before each state update.
# These are the only fields compared between consecutive updates.
# ---------------------------------------------------------------------------

DELTA_SNAPSHOT_FIELDS = (
    "tyre_wear_fl", "tyre_wear_fr", "tyre_wear_rl", "tyre_wear_rr",
    "position",
    "drs_allowed",
    "current_lap",
    "lap_time_ms",
    "sector",
    "sector1_time_ms",
    "sector2_time_ms",
    "tyre_compound",
    "tyre_age_laps",
    "session_type",
    "total_laps",
    "track_name",
    "pit_status",   # pit lane entry/exit fires engineer cycle immediately
)


# ---------------------------------------------------------------------------
# On-track proximity constants
# ---------------------------------------------------------------------------

# Safe upper-bound for track length when the circuit is not in the knowledge base.
# No F1 25 circuit exceeds 7 km; 10 km ensures cars on different laps are always
# separated correctly when computing absolute track position.
TRACK_LENGTH_FALLBACK_M = 10_000

# Minimum speed used when converting a gap in metres to milliseconds.
# Prevents division-by-zero and gives a sensible gap when the player is
# stationary (e.g. stopped at the side of the circuit).
PROXIMITY_SPEED_FLOOR_KMH = 30

# Conversion factor from km/h to m/s (1 km/h = 1000 m / 3600 s)
KMH_TO_MPS = 1.0 / 3.6


# ---------------------------------------------------------------------------
# Module-level pure helper functions
# ---------------------------------------------------------------------------

def _average_four_corner_wear(race_state: dict) -> float:
    """Returns the mean tyre wear across all four corners.

    Parameters:
        race_state: A race state dict containing the four tyre_wear_* keys.

    Returns:
        Average wear as a float rounded to one decimal place.
    """
    total = (race_state["tyre_wear_fl"]
             + race_state["tyre_wear_fr"]
             + race_state["tyre_wear_rl"]
             + race_state["tyre_wear_rr"])
    return round(total / CORNERS_PER_CAR, 1)


def _compute_sector3_time(lap_time_ms: int,
                          sector1_time_ms: int,
                          sector2_time_ms: int) -> int:
    """Derives sector 3 time from total lap time and the two known sector times.

    Returns 0 if sector 1 or sector 2 times are not yet available (still 0),
    since the subtraction would produce a meaningless result.

    Parameters:
        lap_time_ms:    Total lap time in milliseconds.
        sector1_time_ms: Sector 1 time in milliseconds (0 if not yet set).
        sector2_time_ms: Sector 2 time in milliseconds (0 if not yet set).

    Returns:
        Sector 3 time in milliseconds, or 0 if data is incomplete.
    """
    if sector1_time_ms == 0 or sector2_time_ms == 0:
        return 0
    return max(0, lap_time_ms - sector1_time_ms - sector2_time_ms)


def _format_lap_time(lap_time_ms: int) -> str:
    """Formats a lap time in milliseconds as a M:SS.mmm string.

    Parameters:
        lap_time_ms: Lap time in milliseconds, e.g. 94281.

    Returns:
        Formatted string, e.g. '1:34.281'. Returns '0:00.000' for zero values.
    """
    minutes = lap_time_ms // MS_PER_MINUTE
    remaining_ms = lap_time_ms % MS_PER_MINUTE
    seconds = remaining_ms // MS_PER_SECOND
    milliseconds = remaining_ms % MS_PER_SECOND
    return f"{minutes}:{seconds:02d}.{milliseconds:03d}"


def _format_briefing_for_display(briefing: dict) -> str:
    """Formats the engineer briefing dict as a readable multi-line string.

    Parameters:
        briefing: The dict returned by RaceStateManager.get_engineer_briefing().

    Returns:
        A formatted string ready to print to the terminal.
    """
    lines = _build_briefing_header(briefing)
    lines += _build_briefing_car_section(briefing)
    lines += _build_briefing_tyre_section(briefing)
    lines += _build_briefing_events_section(briefing)
    lines += _build_briefing_lap_history_section(briefing)
    lines.append("=" * DISPLAY_SEPARATOR_WIDTH)
    return "\n".join(lines)


def _build_briefing_header(briefing: dict) -> list:
    """Builds the header lines of the briefing display.

    Parameters:
        briefing: The full engineer briefing dict.

    Returns:
        List of formatted strings for the header section.
    """
    state = briefing["current_state"]
    separator = "=" * DISPLAY_SEPARATOR_WIDTH
    title = (f"  F1 ENGINEER BRIEFING  |  "
             f"{state['track_name']}  |  {state['session_type']}")
    lap_line = (f"  Lap {state['current_lap']} / {state['total_laps']}  |  "
                f"P{state['position']}  |  "
                f"{state['tyre_compound']} tyres  "
                f"(age: {state['tyre_age_laps']} laps  /  "
                f"stint: {briefing['stint_length']} laps)")
    return [separator, title, separator, "", lap_line, ""]


def _build_briefing_car_section(briefing: dict) -> list:
    """Builds the car performance lines of the briefing display.

    Parameters:
        briefing: The full engineer briefing dict.

    Returns:
        List of formatted strings for the car performance section.
    """
    state = briefing["current_state"]
    pace_ms = briefing["pace_trend_ms"]
    pace_text = "N/A (< 6 laps)"
    if pace_ms is not None:
        direction = "SLOWER" if pace_ms > 0 else "FASTER"
        pace_text = f"{abs(pace_ms)}ms {direction} vs prev {PACE_TREND_COMPARISON_LAPS} laps"

    lines = ["  CAR & PACE"]
    lines.append(
        f"  Speed: {state['speed_kmh']} km/h  |  Gear: {state['gear']}  |  "
        f"RPM: {state['engine_rpm']}  |  DRS: {'ON' if state['drs_active'] else 'off'}"
    )
    lines.append(
        f"  Throttle: {state['throttle_pct']}%   Brake: {state['brake_pct']}%  |  "
        f"ERS: {state['ers_store_pct']}%  |  Fuel: {state['fuel_remaining_laps']} laps"
    )
    lines.append(f"  Pace trend: {pace_text}")
    lines.append("")
    return lines


def _build_briefing_tyre_section(briefing: dict) -> list:
    """Builds the tyre wear and pit window lines of the briefing display.

    Parameters:
        briefing: The full engineer briefing dict.

    Returns:
        List of formatted strings for the tyre section.
    """
    state = briefing["current_state"]
    wear_rate = briefing["tyre_wear_rate_pct_per_lap"]
    pit_window = briefing["pit_window_estimate_laps"]

    wear_rate_text = f"{wear_rate}%/lap" if wear_rate is not None else "N/A"
    pit_window_text = f"~{pit_window} laps" if pit_window is not None else "N/A"

    lines = ["  TYRE WEAR"]
    lines.append(
        f"  FL: {state['tyre_wear_fl']:>5.1f}%    FR: {state['tyre_wear_fr']:>5.1f}%"
    )
    lines.append(
        f"  RL: {state['tyre_wear_rl']:>5.1f}%    RR: {state['tyre_wear_rr']:>5.1f}%"
    )
    lines.append(
        f"  Wear rate: {wear_rate_text}  |  Pit window: {pit_window_text}"
    )
    lines.append("")
    return lines


def _build_briefing_events_section(briefing: dict) -> list:
    """Builds the recent events lines of the briefing display.

    Parameters:
        briefing: The full engineer briefing dict.

    Returns:
        List of formatted strings for the recent events section.
    """
    lines = ["  RECENT EVENTS"]
    events = briefing["recent_events"]
    if not events:
        lines.append("  None yet.")
    else:
        for event in events:
            lines.append(
                f"  [{event['timestamp']}]  "
                f"{event['type']:<20}  {event['detail']}"
            )
    lines.append("")
    return lines


def _build_briefing_lap_history_section(briefing: dict) -> list:
    """Builds the lap history table lines of the briefing display.

    Parameters:
        briefing: The full engineer briefing dict.

    Returns:
        List of formatted strings for the lap history section.
    """
    lines = ["  LAST 5 LAPS"]
    lines.append(f"  {'Lap':>3}  {'Time':>9}  {'FL%':>5}  {'FR%':>5}  "
                 f"{'RL%':>5}  {'RR%':>5}  {'Pos':>3}")
    lines.append(f"  {'---':>3}  {'---------':>9}  {'----':>5}  {'----':>5}  "
                 f"{'----':>5}  {'----':>5}  {'---':>3}")
    history = briefing["lap_history_summary"]
    if not history:
        lines.append("  No laps completed yet.")
    else:
        for lap in reversed(history):
            lines.append(
                f"  {lap['lap_number']:>3}  "
                f"{_format_lap_time(lap['lap_time_ms']):>9}  "
                f"{lap['tyre_wear_front_left']:>5.1f}  "
                f"{lap['tyre_wear_front_right']:>5.1f}  "
                f"{lap['tyre_wear_rear_left']:>5.1f}  "
                f"{lap['tyre_wear_rear_right']:>5.1f}  "
                f"{lap['position_at_end']:>3}"
            )
    lines.append("")
    return lines


def _nearest_car_in_direction(all_cars: list, player_abs: float,
                               track_length_m: float, speed_mps: float,
                               ahead: bool) -> dict | None:
    """Returns the name and estimated time gap to the nearest car ahead or behind.

    Computes each car's absolute track position as:
        lap_number × track_length_m + lap_distance_m

    This gives a monotonically increasing value that correctly orders cars
    across lap boundaries, enabling true on-track proximity detection
    regardless of classification order.

    The distance gap is converted to milliseconds using the player's current
    speed so the dashboard can display it alongside race gaps.

    Parameters:
        all_cars:       22-car array from current_state, each entry containing
                        'name', 'lap', and 'lap_distance_m' keys.
        player_abs:     Player's absolute track position in metres.
        track_length_m: Full circuit length in metres.
        speed_mps:      Player speed (m/s) used for distance-to-time conversion.
        ahead:          True to find the nearest car ahead; False for behind.

    Returns:
        Dict with 'name' (str) and 'gap_ms' (int), or None if no valid car found.
    """
    best_gap_m = float("inf")
    best_name  = None
    for car in all_cars:
        name     = car.get("name", "")
        car_lap  = car.get("lap", 0)
        car_dist = car.get("lap_distance_m", 0.0)
        if not name or car_lap == 0 or car_dist <= 0.0:
            continue
        gap_m = car_lap * track_length_m + car_dist - player_abs
        if ahead and 0 < gap_m < best_gap_m:
            best_gap_m = gap_m
            best_name  = name
        elif not ahead and -best_gap_m < gap_m < 0:
            best_gap_m = abs(gap_m)
            best_name  = name
    if best_name is None:
        return None
    return {"name": best_name, "gap_ms": int(best_gap_m / speed_mps * 1000)}


# ---------------------------------------------------------------------------
# RaceStateManager class
# ---------------------------------------------------------------------------

class RaceStateManager:
    """Maintains live race state, lap history, and event detection.

    Wraps the Phase 2 parser to provide a higher-level view of the race.
    Call ingest() with every raw UDP packet. Call get_engineer_briefing()
    whenever the AI engineer (Phase 4) needs a snapshot.

    Attributes:
        current_state:  The live race state dict, updated on every packet.
        lap_history:    List of end-of-lap snapshot dicts, oldest first.
        recent_events:  Rolling list of the last MAX_RECENT_EVENTS notable events.
    """

    def __init__(self) -> None:
        """Initialises the manager with an empty state and clean history."""
        self.current_state = empty_race_state()
        self.lap_history: list[dict] = []
        self.recent_events: list[dict] = []

        # --- Stint tracking state ---
        self._stint_start_lap = 0
        self._stint_start_avg_wear = 0.0

        # Tracks which tyre corners have already had a warning/critical event
        # fired this stint, so the same alert is not repeated every update.
        # Keys are strings like "fl_warning" or "rr_critical".
        self._issued_wear_warnings: set[str] = set()

        # Sector times captured at the moment each sector boundary was crossed,
        # keyed by lap number then "s1"/"s2". Sector 3 is derived at lap end.
        self._sector_times_by_lap: dict[int, dict] = {}

        # Session-level best times for each sector (milliseconds; 0 = not yet set).
        self._session_best_s1: int = 0
        self._session_best_s2: int = 0
        self._session_best_s3: int = 0

        # Three-tier reference lap system (personal best / AI best / qualifying best)
        self.reference_lap = ReferenceLap()

        # Session data persistence — created fresh on every session restart
        self._session_data_store: SessionDataStore | None = None

        # On-track proximity — nearest physical car ahead and behind the player
        self._track_car_ahead:  dict | None = None
        self._track_car_behind: dict | None = None

        # Per-sector telemetry accumulation for SessionDataStore recording
        self._sector_throttle_samples: list[float] = []
        self._sector_brake_samples:    list[float] = []
        self._sector_speed_min:        float       = float("inf")

    # --- Public API ---------------------------------------------------------

    def ingest(self, raw_data: bytes) -> None:
        """Processes one raw UDP packet: parses it, updates state, runs delta checks.

        Session History packets (ID 11) are routed directly to reference lap
        handling and do not go through update_race_state, because their data
        does not belong in the live race_state schema.

        Parameters:
            raw_data: Raw bytes from the UDP socket.
        """
        if (len(raw_data) > PACKET_ID_OFFSET
                and raw_data[PACKET_ID_OFFSET] == PACKET_ID_SESSION_HISTORY):
            self._handle_session_history(raw_data)
            return

        parsed = parse_packet(raw_data)
        if parsed is None:
            return
        previous_snapshot = self._capture_delta_snapshot()
        update_race_state(self.current_state, parsed)
        self._detect_and_handle_deltas(previous_snapshot)

        if "speed_kmh" in parsed:
            self.reference_lap.record_sector(
                self.current_state["sector"],
                float(self.current_state["speed_kmh"]),
                float(self.current_state["throttle_pct"]),
                float(self.current_state["brake_pct"]),
                self.current_state["lap_distance_m"],
            )
            self._sector_throttle_samples.append(float(self.current_state["throttle_pct"]))
            self._sector_brake_samples.append(float(self.current_state["brake_pct"]))
            speed = float(self.current_state["speed_kmh"])
            if speed > 0:
                self._sector_speed_min = min(self._sector_speed_min, speed)

        self._compute_track_proximity()

    @property
    def session_data_store(self) -> SessionDataStore | None:
        """Returns the active SessionDataStore for the current session, or None."""
        return self._session_data_store

    def get_engineer_briefing(self) -> dict:
        """Returns a structured snapshot for the AI engineer to consume.

        Contains the current live state, calculated analytics, flagged events,
        and a summary of recent lap history. This is the primary interface
        between Phase 3 (data layer) and Phase 4 (AI layer).

        Returns:
            A dict with keys: current_state, stint_length, pace_trend_ms,
            tyre_wear_rate_pct_per_lap, pit_window_estimate_laps,
            recent_events, lap_history_summary.
        """
        last_five_laps = self.lap_history[-MAX_RECENT_EVENTS:]
        ref_summary    = self.reference_lap.get_briefing_summary()
        ref_summary["coaching_note"] = self._compute_reference_coaching()
        return {
            "current_state":              dict(self.current_state),
            "stint_length":               self.current_state["tyre_age_laps"],
            "pace_trend_ms":              self._calculate_pace_trend(),
            "tyre_wear_rate_pct_per_lap": self._calculate_tyre_wear_rate(),
            "pit_window_estimate_laps":   self._estimate_pit_window(),
            "recent_events":              list(self.recent_events),
            "lap_history_summary":        last_five_laps,
            "session_best_s1":            self._session_best_s1,
            "session_best_s2":            self._session_best_s2,
            "session_best_s3":            self._session_best_s3,
            "reference_lap":              ref_summary,
            "track_car_ahead":            self._track_car_ahead,
            "track_car_behind":           self._track_car_behind,
        }

    # --- Internal: delta snapshot -------------------------------------------

    def _capture_delta_snapshot(self) -> dict:
        """Captures a lightweight snapshot of only the delta-relevant fields.

        Taking a full copy of current_state on every packet (up to 60 Hz)
        is wasteful. This captures only the fields used in delta detection.

        Returns:
            Dict containing only DELTA_SNAPSHOT_FIELDS from current_state.
        """
        return {field: self.current_state[field] for field in DELTA_SNAPSHOT_FIELDS}

    # --- Internal: delta detection orchestration ----------------------------

    def _detect_and_handle_deltas(self, previous_snapshot: dict) -> None:
        """Compares current state to the previous snapshot and records any events.

        Parameters:
            previous_snapshot: The snapshot captured before the latest update.

        Returns:
            None.
        """
        if self._check_session_restart(previous_snapshot):
            return
        events = []
        self._check_sector_transition(previous_snapshot)
        events.extend(self._check_tyre_wear_spikes(previous_snapshot))
        events.extend(self._check_tyre_wear_thresholds())
        events.extend(self._check_position_change(previous_snapshot))
        events.extend(self._check_drs_change(previous_snapshot))
        events.extend(self._check_new_lap(previous_snapshot))
        for event in events:
            self._add_event(event["type"], event["detail"])

    # --- Internal: individual delta checks ----------------------------------

    def _check_session_restart(self, previous_snapshot: dict) -> bool:
        """Detects a session restart and chooses between a full or intra-session reset.

        A *full* reset (clears lap_history) fires on session_type or track_name
        changes — the player has moved to a genuinely new session.
        An *intra-session* reset (preserves lap_history) fires when current_lap
        drops back to 1 within the same session, e.g. a garage visit in practice.
        Lap count changes without a session change are also treated as intra-session
        so that accumulated lap times are not silently discarded.

        Parameters:
            previous_snapshot: Delta snapshot captured before the latest update.

        Returns:
            True if a restart was detected so the caller can skip remaining
            delta checks, which would fire spuriously against the reset state.
        """
        prev_session = previous_snapshot["session_type"]
        curr_session = self.current_state["session_type"]
        prev_track   = previous_snapshot["track_name"]
        curr_track   = self.current_state["track_name"]
        prev_lap     = previous_snapshot["current_lap"]
        curr_lap     = self.current_state["current_lap"]
        prev_total   = previous_snapshot["total_laps"]
        curr_total   = self.current_state["total_laps"]

        session_change = curr_session != prev_session and prev_session != "Unknown"
        track_change   = curr_track != prev_track and prev_track not in ("", "Unknown")
        lap_reset      = curr_lap == 1 and prev_lap > 1
        count_change   = curr_total != prev_total and prev_total > 0 and curr_total > 0

        if session_change or track_change:
            if session_change and prev_session in QUALIFYING_SESSION_TYPES and curr_session in RACE_SESSION_TYPES:
                self.reference_lap.save_qualifying_best()
            self._reset_all_state()
            return True
        if lap_reset or count_change:
            self._reset_intra_session_state()
            return True
        return False

    def _reset_all_state(self) -> None:
        """Resets all accumulated state including lap history after a new session is detected.

        Called when session_type or track_name changes — the player has moved to a
        genuinely different session so all history is invalid and must be discarded.
        Creates a fresh SessionDataStore for the new session.

        Returns:
            None.
        """
        self.lap_history.clear()
        self.recent_events.clear()
        self._stint_start_lap      = 0
        self._stint_start_avg_wear = 0.0
        self._issued_wear_warnings.clear()
        self._sector_times_by_lap.clear()
        self._session_best_s1      = 0
        self._session_best_s2      = 0
        self._session_best_s3      = 0
        self._track_car_ahead      = None
        self._track_car_behind     = None
        self.reference_lap.reset_for_new_session()
        self._sector_throttle_samples.clear()
        self._sector_brake_samples.clear()
        self._sector_speed_min     = float("inf")
        self._session_data_store   = SessionDataStore(
            track_name    = self.current_state.get("track_name", "Unknown"),
            session_type  = self.current_state.get("session_type", "Unknown"),
            tyre_compound = self.current_state.get("tyre_compound", "Unknown"),
            fuel_load     = float(self.current_state.get("fuel_remaining_laps", 0)),
        )
        print("[STATE]  Session restart detected — resetting all state")

    def _reset_intra_session_state(self) -> None:
        """Resets per-stint state after an intra-session restart, preserving lap history.

        Called when current_lap drops back to 1 within the same session (e.g. a
        garage visit in practice). Completed laps accumulated before the visit are
        kept so the dashboard can continue to show them when the player rejoins.
        Session sector bests are also retained — they remain valid across
        garage visits.

        Parameters:
            None — operates on instance state.

        Returns:
            None.
        """
        self.recent_events.clear()
        self._stint_start_lap      = 0
        self._stint_start_avg_wear = 0.0
        self._issued_wear_warnings.clear()
        self._sector_times_by_lap.clear()
        self._sector_throttle_samples.clear()
        self._sector_brake_samples.clear()
        self._sector_speed_min     = float("inf")
        self._track_car_ahead      = None
        self._track_car_behind     = None
        self._session_data_store   = SessionDataStore(
            track_name    = self.current_state.get("track_name", "Unknown"),
            session_type  = self.current_state.get("session_type", "Unknown"),
            tyre_compound = self.current_state.get("tyre_compound", "Unknown"),
            fuel_load     = float(self.current_state.get("fuel_remaining_laps", 0)),
        )
        print("[STATE]  Intra-session restart detected — lap history preserved")

    def _check_sector_transition(self, previous_snapshot: dict) -> None:
        """Stores sector times the moment each sector boundary is crossed.

        Called before _check_new_lap so that s1 and s2 are already in
        _sector_times_by_lap when _build_lap_timing_snapshot runs at lap end.
        Only handles S1→S2 and S2→S3 transitions; S3→S1 (lap end) is handled
        by _build_lap_timing_snapshot via sector3 derivation.

        Parameters:
            previous_snapshot: Delta snapshot from before the latest state update.
        """
        prev_sector = previous_snapshot["sector"]
        curr_sector = self.current_state["sector"]
        if prev_sector == curr_sector:
            return
        lap = previous_snapshot["current_lap"]
        if lap == 0:
            return
        if lap not in self._sector_times_by_lap:
            self._sector_times_by_lap[lap] = {}
        if prev_sector == 1 and curr_sector == 2:
            t = previous_snapshot["sector1_time_ms"]
            if t > 0:
                self._sector_times_by_lap[lap]["s1"] = t
            self._flush_sector_to_store(lap, 1)
        elif prev_sector == 2 and curr_sector == 3:
            t = previous_snapshot["sector2_time_ms"]
            if t > 0:
                self._sector_times_by_lap[lap]["s2"] = t
            self._flush_sector_to_store(lap, 2)

    def _check_tyre_wear_spikes(self, previous_snapshot: dict) -> list:
        """Detects any tyre corner that increased by more than TYRE_WEAR_SPIKE_THRESHOLD_PCT.

        Parameters:
            previous_snapshot: Delta snapshot from before the latest state update.

        Returns:
            List of event dicts (may be empty).
        """
        corners = {
            "fl": ("tyre_wear_fl", "Front Left"),
            "fr": ("tyre_wear_fr", "Front Right"),
            "rl": ("tyre_wear_rl", "Rear Left"),
            "rr": ("tyre_wear_rr", "Rear Right"),
        }
        events = []
        for corner_code, (state_key, corner_label) in corners.items():
            delta = self.current_state[state_key] - previous_snapshot[state_key]
            if delta >= TYRE_WEAR_SPIKE_THRESHOLD_PCT:
                detail = (f"{corner_label} wear spike: "
                          f"+{delta:.1f}% in one update "
                          f"(now {self.current_state[state_key]:.1f}%)")
                events.append({"type": "TYRE_SPIKE", "detail": detail})
        return events

    def _check_tyre_wear_thresholds(self) -> list:
        """Flags corners that have crossed the warning or critical wear levels.

        Each corner fires at most one warning and one critical event per stint.
        Once fired, the event is recorded in _issued_wear_warnings and not repeated.

        Returns:
            List of event dicts (may be empty).
        """
        corners = {
            "fl": ("tyre_wear_fl", "Front Left"),
            "fr": ("tyre_wear_fr", "Front Right"),
            "rl": ("tyre_wear_rl", "Rear Left"),
            "rr": ("tyre_wear_rr", "Rear Right"),
        }
        events = []
        for corner_code, (state_key, corner_label) in corners.items():
            events.extend(
                self._evaluate_single_corner_threshold(corner_code, state_key, corner_label)
            )
        return events

    def _evaluate_single_corner_threshold(self, corner_code: str,
                                          state_key: str,
                                          corner_label: str) -> list:
        """Checks one corner against warning and critical thresholds.

        Parameters:
            corner_code:  Short code used as the deduplication key, e.g. 'fl'.
            state_key:    Key in current_state for this corner's wear value.
            corner_label: Human-readable name for event messages, e.g. 'Front Left'.

        Returns:
            List of zero, one, or two event dicts.
        """
        wear = self.current_state[state_key]
        events = []
        critical_key = f"{corner_code}_critical"
        warning_key  = f"{corner_code}_warning"

        if wear >= TYRE_CRITICAL_THRESHOLD_PCT and critical_key not in self._issued_wear_warnings:
            self._issued_wear_warnings.add(critical_key)
            events.append({
                "type":   "TYRE_CRITICAL",
                "detail": f"{corner_label} at {wear:.1f}% — CRITICAL",
            })
        elif wear >= TYRE_WARNING_THRESHOLD_PCT and warning_key not in self._issued_wear_warnings:
            self._issued_wear_warnings.add(warning_key)
            events.append({
                "type":   "TYRE_WARNING",
                "detail": f"{corner_label} at {wear:.1f}% — warning",
            })
        return events

    def _check_position_change(self, previous_snapshot: dict) -> list:
        """Detects a change in race position since the last update.

        Parameters:
            previous_snapshot: Delta snapshot from before the latest state update.

        Returns:
            List containing one event dict if position changed, else empty.
        """
        current_position  = self.current_state["position"]
        previous_position = previous_snapshot["position"]
        if current_position == previous_position or previous_position == 0:
            return []
        if current_position < previous_position:
            detail = (f"Position gained: P{previous_position} "
                      f"-> P{current_position}")
            return [{"type": "OVERTAKE", "detail": detail}]
        detail = (f"Position lost: P{previous_position} "
                  f"-> P{current_position}")
        return [{"type": "OVERTAKEN", "detail": detail}]

    def _check_drs_change(self, previous_snapshot: dict) -> list:
        """Detects DRS availability being enabled or disabled.

        Parameters:
            previous_snapshot: Delta snapshot from before the latest state update.

        Returns:
            List containing one event dict if DRS status changed, else empty.
        """
        current_drs  = self.current_state["drs_allowed"]
        previous_drs = previous_snapshot["drs_allowed"]
        if current_drs == previous_drs:
            return []
        if current_drs:
            return [{"type": "DRS_AVAILABLE", "detail": "DRS now available"}]
        return [{"type": "DRS_UNAVAILABLE", "detail": "DRS no longer available"}]

    def _check_new_lap(self, previous_snapshot: dict) -> list:
        """Detects a lap number increment, saves a lap snapshot, and checks for a new stint.

        Parameters:
            previous_snapshot: Delta snapshot from before the latest state update.

        Returns:
            List containing one NEW_LAP event dict if the lap incremented, else empty.
        """
        current_lap  = self.current_state["current_lap"]
        previous_lap = previous_snapshot["current_lap"]
        if current_lap <= previous_lap or current_lap == 0:
            return []
        self._save_lap_snapshot(previous_snapshot)
        self._flush_lap_to_store(previous_snapshot)
        if self.lap_history:
            completed_lap = self.lap_history[-1]
            self.reference_lap.save_if_personal_best(
                previous_snapshot["lap_time_ms"],
                sector_times={
                    1: completed_lap.get("sector1_time_ms", 0),
                    2: completed_lap.get("sector2_time_ms", 0),
                    3: completed_lap.get("sector3_time_ms", 0),
                },
            )
        self._check_for_new_stint(previous_snapshot)
        detail = f"Lap {current_lap} started (P{self.current_state['position']})"
        return [{"type": "NEW_LAP", "detail": detail}]

    # --- Internal: session data store helpers --------------------------------

    def _flush_sector_to_store(self, lap_num: int, sector_num: int) -> None:
        """Records accumulated telemetry for a completed sector to the data store.

        Parameters:
            lap_num:    Lap number of the completed sector.
            sector_num: Sector number (1, 2, or 3) that just ended.
        """
        if self._session_data_store is None:
            return
        samples = len(self._sector_throttle_samples)
        throttle_avg = (sum(self._sector_throttle_samples) / samples) if samples else 0.0
        brake_avg    = (sum(self._sector_brake_samples) / samples) if samples else 0.0
        speed_min    = self._sector_speed_min if self._sector_speed_min < float("inf") else 0.0
        self._session_data_store.record_sector_inputs(
            lap_num           = lap_num,
            sector_num        = sector_num,
            throttle_avg      = throttle_avg,
            brake_avg         = brake_avg,
            steering_avg      = 0.0,
            coasting_ms       = 0,
            min_speed_kmh     = speed_min,
            max_lateral_g     = 0.0,
            max_longitudinal_g= 0.0,
        )
        self._sector_throttle_samples.clear()
        self._sector_brake_samples.clear()
        self._sector_speed_min = float("inf")

    def _flush_lap_to_store(self, previous_snapshot: dict) -> None:
        """Records the completed lap's data to the session data store.

        Parameters:
            previous_snapshot: Delta snapshot from the final frame of the
                               completed lap, containing lap time and tyre data.
        """
        if self._session_data_store is None:
            return
        lap_num  = previous_snapshot["current_lap"]
        lap_rec  = self.lap_history[-1] if self.lap_history else {}
        self._session_data_store.record_lap_complete(
            lap_num       = lap_num,
            lap_time_ms   = previous_snapshot["lap_time_ms"],
            sector_1_ms   = lap_rec.get("sector1_time_ms", 0),
            sector_2_ms   = lap_rec.get("sector2_time_ms", 0),
            sector_3_ms   = lap_rec.get("sector3_time_ms", 0),
            tyre_wear_fl  = self.current_state["tyre_wear_fl"],
            tyre_wear_fr  = self.current_state["tyre_wear_fr"],
            tyre_wear_rl  = self.current_state["tyre_wear_rl"],
            tyre_wear_rr  = self.current_state["tyre_wear_rr"],
            tyre_temp_fl  = self.current_state["tyre_temp_fl"],
            tyre_temp_fr  = self.current_state["tyre_temp_fr"],
            tyre_temp_rl  = self.current_state["tyre_temp_rl"],
            tyre_temp_rr  = self.current_state["tyre_temp_rr"],
            ers_store_avg = float(self.current_state.get("ers_store_pct", 0)),
            fuel_remaining= float(self.current_state.get("fuel_remaining_laps", 0)),
        )

    # --- Internal: stint tracking -------------------------------------------

    def _check_for_new_stint(self, previous_snapshot: dict) -> None:
        """Detects a pit stop (new tyres) and resets stint-tracking state.

        A new stint is detected when the tyre compound changes or when
        tyre_age_laps drops by more than STINT_AGE_DROP_THRESHOLD laps,
        which indicates the same compound was re-fitted.

        Parameters:
            previous_snapshot: Delta snapshot from before the latest state update.

        Returns:
            None.
        """
        compound_changed = (
            self.current_state["tyre_compound"] != previous_snapshot["tyre_compound"]
        )
        age_dropped = (
            previous_snapshot["tyre_age_laps"] - self.current_state["tyre_age_laps"]
            >= STINT_AGE_DROP_THRESHOLD
        )
        if compound_changed or age_dropped:
            self._reset_stint_tracking()

    def _reset_stint_tracking(self) -> None:
        """Resets all stint-scoped state to reflect the start of a new tyre set.

        Records the current lap and average wear as the stint baseline, and
        clears any wear warnings that were issued on the previous set.

        Parameters:
            None.

        Returns:
            None.
        """
        self._stint_start_lap = self.current_state["current_lap"]
        self._stint_start_avg_wear = _average_four_corner_wear(self.current_state)
        self._issued_wear_warnings.clear()

    # --- Internal: lap history ----------------------------------------------

    def _save_lap_snapshot(self, previous_snapshot: dict) -> None:
        """Builds an end-of-lap record and appends it to lap_history.

        Parameters:
            previous_snapshot: Delta snapshot captured just before the lap incremented.
                               This holds the timing data from the lap that just ended.

        Returns:
            None.
        """
        completed_lap_number = previous_snapshot["current_lap"]
        if completed_lap_number == 0:
            return
        wear_snapshot   = self._build_tyre_wear_snapshot()
        timing_snapshot = self._build_lap_timing_snapshot(previous_snapshot)
        lap_record = {
            "lap_number":      completed_lap_number,
            "position_at_end": previous_snapshot["position"],
            **wear_snapshot,
            **timing_snapshot,
        }
        self.lap_history.append(lap_record)

    def _build_tyre_wear_snapshot(self) -> dict:
        """Returns current per-corner tyre wear and per-axle averages.

        Returns:
            Dict with keys: tyre_wear_front_left, tyre_wear_front_right,
            tyre_wear_rear_left, tyre_wear_rear_right,
            average_front_axle_wear, average_rear_axle_wear.
        """
        front_left  = self.current_state["tyre_wear_fl"]
        front_right = self.current_state["tyre_wear_fr"]
        rear_left   = self.current_state["tyre_wear_rl"]
        rear_right  = self.current_state["tyre_wear_rr"]
        return {
            "tyre_wear_front_left":    front_left,
            "tyre_wear_front_right":   front_right,
            "tyre_wear_rear_left":     rear_left,
            "tyre_wear_rear_right":    rear_right,
            "average_front_axle_wear": round((front_left + front_right) / CORNERS_PER_AXLE, 1),
            "average_rear_axle_wear":  round((rear_left + rear_right) / CORNERS_PER_AXLE, 1),
        }

    def _build_lap_timing_snapshot(self, previous_snapshot: dict) -> dict:
        """Returns lap time and sector times for the lap that just completed.

        Prefers times captured at sector boundary crossings (_sector_times_by_lap)
        over the end-of-lap snapshot, which can arrive after the game has already
        cleared its sector time fields. Falls back to snapshot values if the
        boundary-crossing store has no entry.

        Also updates session-level sector bests in place.

        Parameters:
            previous_snapshot: Delta snapshot from the final frame of the completed lap.

        Returns:
            Dict with keys: lap_time_ms, sector1_time_ms, sector2_time_ms,
            sector3_time_ms.
        """
        lap_num = previous_snapshot["current_lap"]
        stored  = self._sector_times_by_lap.get(lap_num, {})

        sector1_time_ms = stored.get("s1") or previous_snapshot["sector1_time_ms"]
        sector2_time_ms = stored.get("s2") or previous_snapshot["sector2_time_ms"]
        sector3_time_ms = _compute_sector3_time(
            previous_snapshot["lap_time_ms"], sector1_time_ms, sector2_time_ms
        )

        if sector1_time_ms > 0 and (self._session_best_s1 == 0 or sector1_time_ms < self._session_best_s1):
            self._session_best_s1 = sector1_time_ms
        if sector2_time_ms > 0 and (self._session_best_s2 == 0 or sector2_time_ms < self._session_best_s2):
            self._session_best_s2 = sector2_time_ms
        if sector3_time_ms > 0 and (self._session_best_s3 == 0 or sector3_time_ms < self._session_best_s3):
            self._session_best_s3 = sector3_time_ms

        return {
            "lap_time_ms":     previous_snapshot["lap_time_ms"],
            "sector1_time_ms": sector1_time_ms,
            "sector2_time_ms": sector2_time_ms,
            "sector3_time_ms": sector3_time_ms,
        }

    # --- Internal: reference lap --------------------------------------------

    def _handle_session_history(self, raw_data: bytes) -> None:
        """Parses a Session History packet and updates the AI best if applicable.

        Ignores packets for the player's own car — only AI car data is useful
        as an external benchmark.

        Parameters:
            raw_data: Raw bytes from the UDP socket, pre-checked to be packet ID 11.

        Returns:
            None.
        """
        result = parse_session_history(raw_data)
        if result is None or result["is_player"]:
            return
        self.reference_lap.update_ai_best(
            result["car_index"],
            result["best_lap_ms"],
            {s: {"time_ms": ms} for s, ms in result["sector_times"].items()},
        )

    def _compute_reference_coaching(self) -> str:
        """Produces a coaching note from reference lap data for the current state.

        Tries personal-best telemetry comparison first; if unavailable, falls
        back to an AI-vs-session-best timing comparison for the current sector.

        Parameters:
            None — reads from instance state (current_state, reference_lap,
            session sector bests).

        Returns:
            A coaching note string, or an empty string if no comparison is available.
        """
        sector   = self.current_state["sector"]
        speed    = float(self.current_state["speed_kmh"])
        throttle = float(self.current_state["throttle_pct"])
        brake    = float(self.current_state["brake_pct"])

        note = self.reference_lap.get_coaching_comparison(sector, speed, throttle, brake)
        if note:
            return note

        if self.reference_lap.has_ai_best():
            return self.reference_lap.get_ai_timing_coaching(
                sector,
                (self._session_best_s1, self._session_best_s2, self._session_best_s3),
            )
        return ""

    # --- Internal: events ---------------------------------------------------

    def _add_event(self, event_type: str, detail: str) -> None:
        """Appends a new event to recent_events, capping the list at MAX_RECENT_EVENTS.

        Parameters:
            event_type: Short identifier string, e.g. 'NEW_LAP' or 'TYRE_WARNING'.
            detail:     Human-readable description of what happened.

        Returns:
            None.
        """
        event = {
            "type":      event_type,
            "detail":    detail,
            "lap":       self.current_state["current_lap"],
            "timestamp": datetime.now().strftime(EVENT_TIMESTAMP_FORMAT),
        }
        self.recent_events.append(event)
        if len(self.recent_events) > MAX_RECENT_EVENTS:
            self.recent_events.pop(0)

    # --- Internal: on-track proximity ----------------------------------------

    def _compute_track_proximity(self) -> None:
        """Computes the physically nearest car ahead and behind the player on track.

        Uses each car's current lap number and lap_distance_m to derive an
        absolute track position (lap × track_length_m + lap_distance_m). This
        correctly orders cars across lap boundaries and is independent of the
        classification order used in races, making it suitable for practice
        sessions where classification reflects best lap time, not track position.

        Results are stored in self._track_car_ahead and self._track_car_behind.
        Each is a dict with 'name' and 'gap_ms', or None if no valid car found.

        Returns:
            None.
        """
        track_info     = get_track_data(self.current_state["track_name"]) or {}
        track_length_m = (track_info.get("lap_length_km", 0) * 1000
                          or TRACK_LENGTH_FALLBACK_M)
        player_lap     = self.current_state["current_lap"]
        player_dist    = self.current_state["lap_distance_m"]
        player_abs     = player_lap * track_length_m + player_dist
        speed_mps      = (max(self.current_state["speed_kmh"], PROXIMITY_SPEED_FLOOR_KMH)
                          * KMH_TO_MPS)
        all_cars       = self.current_state["all_cars"]
        self._track_car_ahead  = _nearest_car_in_direction(
            all_cars, player_abs, track_length_m, speed_mps, ahead=True
        )
        self._track_car_behind = _nearest_car_in_direction(
            all_cars, player_abs, track_length_m, speed_mps, ahead=False
        )

    # --- Internal: analytics ------------------------------------------------

    def _calculate_pace_trend(self) -> int | None:
        """Compares average lap time over the last N laps vs the N laps before that.

        Uses PACE_TREND_COMPARISON_LAPS as N. Returns a positive number if
        pace is getting slower (delta in milliseconds).

        Returns:
            Delta in milliseconds (positive = slower, negative = faster),
            or None if there are not enough laps to compare.
        """
        required_laps = PACE_TREND_COMPARISON_LAPS * 2
        if len(self.lap_history) < required_laps:
            return None
        recent_laps = self.lap_history[-PACE_TREND_COMPARISON_LAPS:]
        earlier_laps = self.lap_history[
            -(required_laps):-PACE_TREND_COMPARISON_LAPS
        ]
        recent_average  = sum(lap["lap_time_ms"] for lap in recent_laps) / PACE_TREND_COMPARISON_LAPS
        earlier_average = sum(lap["lap_time_ms"] for lap in earlier_laps) / PACE_TREND_COMPARISON_LAPS
        return round(recent_average - earlier_average)

    def _calculate_tyre_wear_rate(self) -> float | None:
        """Calculates average tyre wear per lap over the current stint.

        Uses the four-corner average at stint start vs current,
        divided by the number of laps on the current set.

        Returns:
            Wear rate as a float (% per lap), or None if there are not
            enough laps on the current set for a reliable calculation.
        """
        tyre_age = self.current_state["tyre_age_laps"]
        if tyre_age < WEAR_RATE_MIN_LAPS:
            return None
        current_avg_wear = _average_four_corner_wear(self.current_state)
        total_wear_this_stint = current_avg_wear - self._stint_start_avg_wear
        return round(total_wear_this_stint / tyre_age, 2)

    def _estimate_pit_window(self) -> int | None:
        """Estimates laps remaining before the worst-worn corner reaches TYRE_CRITICAL_THRESHOLD_PCT.

        Based on the current wear rate. Returns 0 if the threshold is already exceeded.

        Returns:
            Estimated laps as an integer, or None if wear rate is not yet calculable.
        """
        wear_rate = self._calculate_tyre_wear_rate()
        if wear_rate is None or wear_rate <= 0:
            return None
        worst_corner_wear = max(
            self.current_state["tyre_wear_fl"],
            self.current_state["tyre_wear_fr"],
            self.current_state["tyre_wear_rl"],
            self.current_state["tyre_wear_rr"],
        )
        remaining_capacity = TYRE_CRITICAL_THRESHOLD_PCT - worst_corner_wear
        return max(0, int(remaining_capacity / wear_rate))


# ---------------------------------------------------------------------------
# Phase 3 standalone test harness
# Run: venv\Scripts\python.exe src\state_manager.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", UDP_PORT))

    manager           = RaceStateManager()
    last_display_time = 0.0
    packet_count      = 0

    print("F1 Engineer — Phase 3 Race State Manager")
    print(f"Listening on port {UDP_PORT}. Briefing refreshes every "
          f"{BRIEFING_DISPLAY_INTERVAL_SECONDS:.0f}s.")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            raw_data, _ = udp_socket.recvfrom(BUFFER_SIZE)
            packet_count += 1
            manager.ingest(raw_data)

            now = time.monotonic()
            if now - last_display_time >= BRIEFING_DISPLAY_INTERVAL_SECONDS:
                briefing = manager.get_engineer_briefing()
                os.system("cls" if os.name == "nt" else "clear")
                print(f"[{packet_count} packets received]\n")
                print(_format_briefing_for_display(briefing))
                last_display_time = now

    except KeyboardInterrupt:
        print("\nState manager stopped.")
    finally:
        udp_socket.close()
