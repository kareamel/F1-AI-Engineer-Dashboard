"""
Phase 2 — Packet Parser
Responsible for: taking raw UDP bytes from F1 25 and returning a clean
dictionary of extracted values for the player's own car. Also maintains the
shape of the canonical race_state dictionary used throughout the project.
No AI logic, no history, no side effects — pure data extraction.
The race_state dict produced here is the single source of truth that
Phase 3 (state manager) and Phase 4 (AI brain) will read.
"""

import os
import socket
import time

from f1 import packets


# ---------------------------------------------------------------------------
# Network constants
# ---------------------------------------------------------------------------

UDP_PORT    = 20777
BUFFER_SIZE = 4096


# ---------------------------------------------------------------------------
# Parsing constants
# ---------------------------------------------------------------------------

PACKET_ID_OFFSET      = 6
SECTOR_MINUTES_TO_MS  = 60_000
ERS_MAX_JOULES        = 4_000_000
DISPLAY_INTERVAL_SECONDS = 2.0


# ---------------------------------------------------------------------------
# Tyre array index constants  (order defined by F1 25 spec: RL, RR, FL, FR)
# ---------------------------------------------------------------------------

TYRE_ARRAY_RL = 0
TYRE_ARRAY_RR = 1
TYRE_ARRAY_FL = 2
TYRE_ARRAY_FR = 3


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

TRACKS = packets.TRACKS

SESSION_TYPES = {
    0:  "Unknown",
    1:  "Practice 1",
    2:  "Practice 2",
    3:  "Practice 3",
    4:  "Short Practice",
    5:  "Q1",
    6:  "Q2",
    7:  "Q3",
    8:  "Short Qualifying",
    9:  "One-Shot Qualifying",
    10: "Race",
    11: "Race 2",
    12: "Race 3",
    13: "Time Trial",
}

TYRE_COMPOUNDS = {
    16: "C1", 17: "C2", 18: "C3", 19: "C4", 20: "C5", 21: "C6",
    7:  "Inter",
    8:  "Wet",
}

# Visual compound is the tyre colour shown on screen and to the pit wall (Soft/Medium/Hard).
# It differs from the actual compound at circuits where e.g. C3 is branded as Medium.
# Use actual_tyre_compound for temperature-window lookups; use visual for display only.
VISUAL_TYRE_COMPOUNDS = {
    16: "Soft",
    17: "Medium",
    18: "Hard",
    7:  "Inter",
    8:  "Wet",
}


# ---------------------------------------------------------------------------
# Packet ID constants  (only the types we parse)
# ---------------------------------------------------------------------------

PACKET_ID_MOTION           = 0
PACKET_ID_SESSION          = 1
PACKET_ID_LAP_DATA         = 2
PACKET_ID_PARTICIPANTS     = 4
PACKET_ID_TELEMETRY        = 6
PACKET_ID_CAR_STATUS       = 7
PACKET_ID_CAR_DAMAGE       = 10
PACKET_ID_SESSION_HISTORY  = 11
PACKET_ID_TYRE_SETS        = 12

HANDLED_PACKET_IDS = {
    PACKET_ID_MOTION,
    PACKET_ID_SESSION,
    PACKET_ID_LAP_DATA,
    PACKET_ID_PARTICIPANTS,
    PACKET_ID_TELEMETRY,
    PACKET_ID_CAR_STATUS,
    PACKET_ID_CAR_DAMAGE,
    PACKET_ID_TYRE_SETS,
    # PACKET_ID_SESSION_HISTORY is intentionally excluded here — it is parsed
    # separately via parse_session_history() because its data does not merge
    # into race_state the same way as other packet types.
}


# ---------------------------------------------------------------------------
# Default race state
# ---------------------------------------------------------------------------

def _default_car_entry() -> dict:
    """Returns a zeroed per-car dict used to initialise all_cars.

    Returns:
        Dict with all per-car keys set to zero/False/empty defaults,
        matching the shape merged into all_cars by update_race_state().
    """
    return {
        "position":                0,
        "lap":                     0,
        "pit_status":              0,
        "pit_stops":               0,
        "last_lap_ms":             0,
        "driver_status":           0,
        "delta_to_car_in_front_ms": 0,
        "name":                    "",
        "team_id":                 0,
        "speed_kmh":               0,
        "ers_store_pct":           0.0,
        "ers_deploy_mode":         0,
        "drs_allowed":             False,
        "drs_activation_distance": 0,
    }


def empty_race_state() -> dict:
    """Returns a fully zeroed race state dictionary.

    This defines the canonical shape of the race state used across all phases.
    Call this once at startup and then pass it to update_race_state() as new
    packets arrive.

    Returns:
        A dict with all expected keys set to safe zero/default values.
    """
    return {
        # -- Car Telemetry (arrives at ~60 Hz) --
        "speed_kmh":           0,
        "throttle_pct":        0.0,
        "brake_pct":           0.0,
        "gear":                0,
        "engine_rpm":          0,
        "drs_active":          False,

        # -- Tyre surface temperatures (from PacketCarTelemetryData, ~60 Hz) --
        "tyre_temp_fl":        0,
        "tyre_temp_fr":        0,
        "tyre_temp_rl":        0,
        "tyre_temp_rr":        0,

        # -- Lap Data (arrives at ~60 Hz) --
        "current_lap":         0,
        "lap_time_ms":         0,
        "sector":              1,
        "sector1_time_ms":     0,
        "sector2_time_ms":     0,
        "position":            0,
        "pit_status":          0,
        "lap_invalid":         False,

        # -- Player gap data (from LapData, ~60 Hz) --
        "gap_to_ahead_ms":     0,
        "gap_to_leader_ms":    0,

        # -- Car Status (arrives at ~2 Hz) --
        "fuel_remaining_laps":   0.0,
        "tyre_compound":         "Unknown",   # actual compound: C1-C6, Inter, Wet
        "visual_tyre_compound":  "Unknown",   # visual compound: Soft/Medium/Hard/Inter/Wet
        "tyre_age_laps":         0,
        "drs_allowed":         False,
        "ers_store_pct":       0.0,
        "ers_deploy_mode":     0,

        # -- Tyre wear per corner (from Car Damage packet, ~10 Hz) --
        "tyre_wear_fl":        0.0,
        "tyre_wear_fr":        0.0,
        "tyre_wear_rl":        0.0,
        "tyre_wear_rr":        0.0,

        # -- Session info (arrives at ~1 Hz) --
        "track_name":          "Unknown",
        "session_type":        "Unknown",
        "total_laps":          0,
        "track_temp_c":        0,
        "air_temp_c":          0,
        "weather":             0,
        "safety_car_status":   0,

        # -- Session strategy (from Session packet) --
        "pit_window_ideal":    0,
        "pit_window_latest":   0,
        "pit_rejoin_position": 0,
        "weather_forecast":    [],
        "sector2_lap_dist_m":  0.0,
        "sector3_lap_dist_m":  0.0,

        # -- Motion (arrives at ~60 Hz) --
        "car_x":               0.0,
        "car_z":               0.0,

        # -- Lap distance (from LapData, ~60 Hz) --
        "lap_distance_m":      0.0,

        # -- All-car data (merged from Lap Data, Participants, Car Status, Telemetry) --
        "all_cars":            [_default_car_entry() for _ in range(22)],
    }


# ---------------------------------------------------------------------------
# Per-packet extractors  (private — called only through parse_packet)
# ---------------------------------------------------------------------------

def _parse_telemetry(packet: packets.PacketCarTelemetryData,
                     player_index: int) -> dict:
    """Extracts driver inputs, engine state, and tyre temps for the player's car.
    Also extracts speed for all 22 cars into all_cars.

    Parameters:
        packet:       The unpacked PacketCarTelemetryData from the f1 library.
        player_index: Index into the 22-car array for the player's own car.

    Returns:
        Dict with keys: speed_kmh, throttle_pct, brake_pct, gear, engine_rpm,
        drs_active, tyre_temp_fl/fr/rl/rr, all_cars (speed_kmh per car).
    """
    player_car = packet.car_telemetry_data[player_index]
    all_cars = [{"speed_kmh": car.speed} for car in packet.car_telemetry_data]
    return {
        "speed_kmh":    player_car.speed,
        "throttle_pct": round(player_car.throttle * 100, 1),
        "brake_pct":    round(player_car.brake * 100, 1),
        "gear":         player_car.gear,
        "engine_rpm":   player_car.engine_rpm,
        "drs_active":   bool(player_car.drs),
        "tyre_temp_fl": int(player_car.tyres_surface_temperature[TYRE_ARRAY_FL]),
        "tyre_temp_fr": int(player_car.tyres_surface_temperature[TYRE_ARRAY_FR]),
        "tyre_temp_rl": int(player_car.tyres_surface_temperature[TYRE_ARRAY_RL]),
        "tyre_temp_rr": int(player_car.tyres_surface_temperature[TYRE_ARRAY_RR]),
        "all_cars":     all_cars,
    }


def _parse_lap_data(packet: packets.PacketLapData, player_index: int) -> dict:
    """Extracts lap timing, gaps, and race data for all 22 cars.

    Sector times are 0 until that sector has been completed in the current lap.
    Gap fields are only meaningful for the player car.

    Parameters:
        packet:       The unpacked PacketLapData from the f1 library.
        player_index: Index into the 22-car array for the player's own car.

    Returns:
        Dict with player-specific keys (current_lap, lap_time_ms, etc.),
        player gap keys (gap_to_ahead_ms, gap_to_leader_ms), and
        all_cars list of 22 dicts (position, lap, pit_status, pit_stops,
        last_lap_ms, driver_status, delta_to_car_in_front_ms,
        lap_distance_m).
    """
    player_lap = packet.lap_data[player_index]

    sector1_time_ms = (player_lap.sector1_time_minutes_part * SECTOR_MINUTES_TO_MS
                       + player_lap.sector1_time_ms_part)
    sector2_time_ms = (player_lap.sector2_time_minutes_part * SECTOR_MINUTES_TO_MS
                       + player_lap.sector2_time_ms_part)
    gap_to_ahead_ms = (player_lap.delta_to_car_in_front_minutes_part * SECTOR_MINUTES_TO_MS
                       + player_lap.delta_to_car_in_front_ms_part)
    gap_to_leader_ms = (player_lap.delta_to_race_leader_minutes_part * SECTOR_MINUTES_TO_MS
                        + player_lap.delta_to_race_leader_ms_part)

    all_cars = [
        {
            "position":                  car.car_position,
            "lap":                       car.current_lap_num,
            "pit_status":                car.pit_status,
            "pit_stops":                 car.num_pit_stops,
            "last_lap_ms":               car.last_lap_time_in_ms,
            "driver_status":             car.driver_status,
            "delta_to_car_in_front_ms":  (car.delta_to_car_in_front_minutes_part
                                          * SECTOR_MINUTES_TO_MS
                                          + car.delta_to_car_in_front_ms_part),
            "lap_distance_m":            round(max(0.0, float(car.lap_distance)), 1),
        }
        for car in packet.lap_data
    ]

    return {
        "current_lap":      player_lap.current_lap_num,
        "lap_time_ms":      player_lap.current_lap_time_in_ms,
        "sector":           player_lap.sector + 1,
        "sector1_time_ms":  sector1_time_ms,
        "sector2_time_ms":  sector2_time_ms,
        "position":         player_lap.car_position,
        "pit_status":       player_lap.pit_status,
        "lap_invalid":      bool(player_lap.current_lap_invalid),
        "lap_distance_m":   round(max(0.0, float(player_lap.lap_distance)), 1),
        "gap_to_ahead_ms":  gap_to_ahead_ms,
        "gap_to_leader_ms": gap_to_leader_ms,
        "all_cars":         all_cars,
    }


def _parse_car_status(packet: packets.PacketCarStatusData,
                      player_index: int) -> dict:
    """Extracts fuel load, tyre compound and age, DRS, and ERS for all 22 cars.

    Player-specific fields are promoted to top-level race_state keys.
    Per-car ERS and DRS data is stored in all_cars for every car.

    Parameters:
        packet:       The unpacked PacketCarStatusData from the f1 library.
        player_index: Index into the 22-car array for the player's own car.

    Returns:
        Dict with player keys (fuel_remaining_laps, tyre_compound, etc.) and
        all_cars list of 22 dicts (ers_store_pct, ers_deploy_mode, drs_allowed,
        drs_activation_distance).
    """
    player_car           = packet.car_status_data[player_index]
    compound_name        = TYRE_COMPOUNDS.get(
        player_car.actual_tyre_compound, f"ID:{player_car.actual_tyre_compound}"
    )
    visual_compound_name = VISUAL_TYRE_COMPOUNDS.get(
        player_car.visual_tyre_compound, f"ID:{player_car.visual_tyre_compound}"
    )
    ers_store_pct = round((player_car.ers_store_energy / ERS_MAX_JOULES) * 100, 1)

    all_cars = [
        {
            "ers_store_pct":           round((car.ers_store_energy / ERS_MAX_JOULES) * 100, 1),
            "ers_deploy_mode":         car.ers_deploy_mode,
            "drs_allowed":             bool(car.drs_allowed),
            "drs_activation_distance": car.drs_activation_distance,
        }
        for car in packet.car_status_data
    ]

    return {
        "fuel_remaining_laps":  round(player_car.fuel_remaining_laps, 2),
        "tyre_compound":        compound_name,
        "visual_tyre_compound": visual_compound_name,
        "tyre_age_laps":        player_car.tyres_age_laps,
        "drs_allowed":          bool(player_car.drs_allowed),
        "ers_store_pct":        ers_store_pct,
        "ers_deploy_mode":      player_car.ers_deploy_mode,
        "all_cars":             all_cars,
    }


def _parse_car_damage(packet: packets.PacketCarDamageData,
                      player_index: int) -> dict:
    """Extracts per-corner tyre wear (0–100%) for the player's car.

    Parameters:
        packet:       The unpacked PacketCarDamageData from the f1 library.
        player_index: Index into the 22-car array for the player's own car.

    Returns:
        Dict with keys: tyre_wear_fl, tyre_wear_fr, tyre_wear_rl, tyre_wear_rr.
    """
    player_car = packet.car_damage_data[player_index]
    return {
        "tyre_wear_fl": round(player_car.tyres_wear[TYRE_ARRAY_FL], 1),
        "tyre_wear_fr": round(player_car.tyres_wear[TYRE_ARRAY_FR], 1),
        "tyre_wear_rl": round(player_car.tyres_wear[TYRE_ARRAY_RL], 1),
        "tyre_wear_rr": round(player_car.tyres_wear[TYRE_ARRAY_RR], 1),
    }


def _parse_tyre_sets(packet: packets.PacketTyreSetsData,
                     player_index: int) -> dict | None:
    """Extracts the compound of the currently fitted tyre set for the player.

    TyreSets packets are broadcast once per car (not as a 22-element array),
    so packets not addressed to the player's car are ignored.

    Parameters:
        packet:       The unpacked PacketTyreSetsData from the f1 library.
        player_index: The player's car index from the packet header.

    Returns:
        Dict with key: tyre_compound.
        Returns None if this packet is for a different car.
    """
    if packet.car_idx != player_index:
        return None
    fitted_set           = packet.tyre_set_data[packet.fitted_idx]
    compound_name        = TYRE_COMPOUNDS.get(
        fitted_set.actual_tyre_compound, f"ID:{fitted_set.actual_tyre_compound}"
    )
    visual_compound_name = VISUAL_TYRE_COMPOUNDS.get(
        fitted_set.visual_tyre_compound, f"ID:{fitted_set.visual_tyre_compound}"
    )
    return {
        "tyre_compound":        compound_name,
        "visual_tyre_compound": visual_compound_name,
    }


def _parse_motion(packet: packets.PacketMotionData, player_index: int) -> dict:
    """Extracts world X/Z position for the player's car.

    Parameters:
        packet:       The unpacked PacketMotionData from the f1 library.
        player_index: Index into the 22-car array for the player's own car.

    Returns:
        Dict with keys: car_x, car_z.
    """
    player_car = packet.car_motion_data[player_index]
    return {
        "car_x": round(float(player_car.world_position_x), 1),
        "car_z": round(float(player_car.world_position_z), 1),
    }


def _parse_session(packet: packets.PacketSessionData) -> dict:
    """Extracts track identity, session type, weather, strategy, and sector data.

    Parameters:
        packet: The unpacked PacketSessionData from the f1 library.

    Returns:
        Dict with keys: track_name, session_type, total_laps, track_temp_c,
        air_temp_c, weather, safety_car_status, pit_window_ideal,
        pit_window_latest, pit_rejoin_position, weather_forecast (first 3
        samples), sector2_lap_dist_m, sector3_lap_dist_m.
    """
    track_name   = TRACKS.get(packet.track_id, f"Track {packet.track_id}")
    session_type = SESSION_TYPES.get(packet.session_type, f"Type {packet.session_type}")

    num_samples = min(3, packet.num_weather_forecast_samples)
    forecast = [
        {
            "time_offset": packet.weather_forecast_samples[i].time_offset,
            "weather":     packet.weather_forecast_samples[i].weather,
            "rain_pct":    packet.weather_forecast_samples[i].rain_percentage,
        }
        for i in range(num_samples)
    ]

    return {
        "track_name":          track_name,
        "session_type":        session_type,
        "total_laps":          packet.total_laps,
        "track_temp_c":        packet.track_temperature,
        "air_temp_c":          packet.air_temperature,
        "weather":             packet.weather,
        "safety_car_status":   packet.safety_car_status,
        "pit_window_ideal":    packet.pit_stop_window_ideal_lap,
        "pit_window_latest":   packet.pit_stop_window_latest_lap,
        "pit_rejoin_position": packet.pit_stop_rejoin_position,
        "weather_forecast":    forecast,
        "sector2_lap_dist_m":  round(float(packet.sector2_lap_distance_start), 1),
        "sector3_lap_dist_m":  round(float(packet.sector3_lap_distance_start), 1),
    }


def _parse_participants(packet: packets.PacketParticipantsData) -> dict:
    """Extracts driver name and team ID for all 22 cars.

    Called once at session start (and when the game re-broadcasts participants).
    Stores results into all_cars so names are available for the engineer briefing.

    Parameters:
        packet: The unpacked PacketParticipantsData from the f1 library.

    Returns:
        Dict with key all_cars: list of 22 dicts (name, team_id).
    """
    all_cars = [
        {
            "name":    p.name.decode("utf-8", errors="replace"),
            "team_id": p.team_id,
        }
        for p in packet.participants
    ]
    return {"all_cars": all_cars}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_packet(raw_data: bytes) -> dict | None:
    """Parses raw UDP bytes from F1 25 into a dict of extracted values.

    Only processes the packet types defined in HANDLED_PACKET_IDS.
    All unpack errors are caught so the caller never needs to handle exceptions.

    Parameters:
        raw_data: Raw bytes received from the UDP socket.

    Returns:
        A dict of extracted values if the packet type is handled,
        or None if the packet is ignored, too short, or fails to unpack.
    """
    if len(raw_data) <= PACKET_ID_OFFSET:
        return None

    packet_id = raw_data[PACKET_ID_OFFSET]
    if packet_id not in HANDLED_PACKET_IDS:
        return None

    try:
        packet = packets.resolve(raw_data)
    except Exception:
        return None

    player_index = packet.header.player_car_index

    if packet_id == PACKET_ID_MOTION:
        return _parse_motion(packet, player_index)
    if packet_id == PACKET_ID_TELEMETRY:
        return _parse_telemetry(packet, player_index)
    if packet_id == PACKET_ID_LAP_DATA:
        return _parse_lap_data(packet, player_index)
    if packet_id == PACKET_ID_CAR_STATUS:
        return _parse_car_status(packet, player_index)
    if packet_id == PACKET_ID_CAR_DAMAGE:
        return _parse_car_damage(packet, player_index)
    if packet_id == PACKET_ID_TYRE_SETS:
        return _parse_tyre_sets(packet, player_index)
    if packet_id == PACKET_ID_SESSION:
        return _parse_session(packet)
    if packet_id == PACKET_ID_PARTICIPANTS:
        return _parse_participants(packet)

    return None


def parse_session_history(raw_data: bytes) -> dict | None:
    """Parses a Session History packet and extracts the best lap and sector times.

    Only processes packets with PACKET_ID_SESSION_HISTORY. Returns the best
    lap time and per-sector times for the car identified in the packet, along
    with a flag indicating whether the packet is for the player's own car.

    Intended to be called from state_manager when the packet ID check shows
    ID 11 — this path is separate from parse_packet / update_race_state.

    Parameters:
        raw_data: Raw bytes from the UDP socket.

    Returns:
        Dict with keys: car_index, is_player, best_lap_ms, sector_times
        ({1: ms, 2: ms, 3: ms}), or None if the packet cannot be parsed or
        contains no valid best lap.
    """
    if len(raw_data) <= PACKET_ID_OFFSET:
        return None
    if raw_data[PACKET_ID_OFFSET] != PACKET_ID_SESSION_HISTORY:
        return None
    try:
        packet = packets.resolve(raw_data)
    except Exception:
        return None

    car_idx      = packet.car_idx
    player_index = packet.header.player_car_index
    best_lap_num = packet.best_lap_time_lap_num

    if best_lap_num == 0 or best_lap_num > packet.num_laps:
        return None

    best_lap    = packet.lap_history_data[best_lap_num - 1]   # 1-indexed → 0-indexed
    lap_time_ms = best_lap.lap_time_in_ms
    if lap_time_ms == 0:
        return None

    s1_ms = (best_lap.sector1_time_minutes_part * SECTOR_MINUTES_TO_MS
             + best_lap.sector1_time_ms_part)
    s2_ms = (best_lap.sector2_time_minutes_part * SECTOR_MINUTES_TO_MS
             + best_lap.sector2_time_ms_part)
    s3_ms = (best_lap.sector3_time_minutes_part * SECTOR_MINUTES_TO_MS
             + best_lap.sector3_time_ms_part)

    return {
        "car_index":    car_idx,
        "is_player":    car_idx == player_index,
        "best_lap_ms":  lap_time_ms,
        "sector_times": {1: s1_ms, 2: s2_ms, 3: s3_ms},
    }


def update_race_state(race_state: dict, parsed: dict | None) -> dict:
    """Merges freshly parsed values into the race state dictionary.

    For most keys, the parsed value replaces the existing value directly.
    For all_cars, parsed dicts are merged per-car so that different packet
    types (Lap Data, Participants, Car Status, Telemetry) can each contribute
    their own fields without wiping contributions from other sources.

    Parameters:
        race_state: The current race state dict (from empty_race_state or prior update).
        parsed:     A parsed packet dict from parse_packet(), or None to no-op.

    Returns:
        The updated race_state dict (same object, mutated in place).
    """
    if not parsed:
        return race_state
    for key, val in parsed.items():
        if key == "all_cars" and isinstance(val, list):
            target = race_state["all_cars"]
            for i, car_update in enumerate(val):
                if i < len(target):
                    target[i].update(car_update)
        else:
            race_state[key] = val
    return race_state


# ---------------------------------------------------------------------------
# Phase 2 standalone test harness
# Run: venv\Scripts\python.exe src\parser.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pprint  # only needed by this test harness, not by production callers
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", UDP_PORT))

    race_state    = empty_race_state()
    last_print    = 0.0
    packet_count  = 0
    parsed_count  = 0

    print("F1 Engineer — Phase 2 Parser")
    print(f"Listening on port {UDP_PORT}. Race state refreshes every "
          f"{DISPLAY_INTERVAL_SECONDS:.0f}s.")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            raw_data, _ = udp_socket.recvfrom(BUFFER_SIZE)
            packet_count += 1

            parsed = parse_packet(raw_data)
            if parsed:
                parsed_count += 1
                update_race_state(race_state, parsed)

            now = time.monotonic()
            if now - last_print >= DISPLAY_INTERVAL_SECONDS:
                os.system("cls" if os.name == "nt" else "clear")
                print(f"=== F1 RACE STATE  "
                      f"[{packet_count} received / {parsed_count} parsed] ===\n")
                pprint.pprint(race_state, sort_dicts=False)
                last_print = now

    except KeyboardInterrupt:
        print("\nParser stopped.")
    finally:
        udp_socket.close()
