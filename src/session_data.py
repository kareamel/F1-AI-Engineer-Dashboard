"""
Session Data Store — telemetry data persistence for practice sessions.

Saves per-lap and per-sector data to a JSON file for each session so that
the garage dashboard and post-session analysis can access it later.
The file is written after every completed lap and when the session ends.

No AI calls are made here — this is pure data capture and serialisation.
"""

import json
import math
import os
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Storage constants
# ---------------------------------------------------------------------------

SESSION_DATA_DIR = "data/sessions"   # relative to project root
MAX_LAPS_STORED  = 100               # discard oldest laps beyond this limit


# ---------------------------------------------------------------------------
# SessionDataStore
# ---------------------------------------------------------------------------

class SessionDataStore:
    """Stores and persists telemetry data captured during a practice session.

    Creates a JSON file on disk named by date, track, and session type.
    Call record_sector_inputs() during each lap, record_lap_complete() when
    the lap timer ticks over, and record_wheelspin_event() when a slip is
    detected. The file is updated automatically after each lap.

    Attributes:
        track:        Canonical track name string.
        session_type: Human-readable session type, e.g. 'Practice 1'.
        filename:     Absolute path to the JSON output file.
    """

    def __init__(self, track_name: str, session_type: str,
                 tyre_compound: str, fuel_load: float) -> None:
        """Initialises storage for a new session.

        Creates the output directory if it does not exist.

        Parameters:
            track_name:    Track name from race_state (e.g. 'Monza').
            session_type:  Session type string (e.g. 'Practice 1').
            tyre_compound: Starting tyre compound.
            fuel_load:     Starting fuel in kg.
        """
        self.track        = track_name
        self.session_type = session_type

        output_dir = Path(SESSION_DATA_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_track   = track_name.replace(" ", "_")
        safe_session = session_type.replace(" ", "_")
        today        = date.today().isoformat()
        self.filename = output_dir / f"{today}_{safe_track}_{safe_session}.json"

        self._session_info: dict = {
            "date":         today,
            "track":        track_name,
            "session_type": session_type,
            "tyre_compound": tyre_compound,
            "fuel_load":    fuel_load,
        }
        self._laps:             list[dict] = []
        self._current_lap_data: dict       = {}
        self._wheelspin_log:    list[dict] = []

    # --- Public API ---------------------------------------------------------

    def record_sector_inputs(
        self,
        lap_num:           int,
        sector_num:        int,
        throttle_avg:      float,
        brake_avg:         float,
        steering_avg:      float,
        coasting_ms:       int,
        min_speed_kmh:     float,
        max_lateral_g:     float,
        max_longitudinal_g: float,
    ) -> None:
        """Stores averaged driving inputs for one sector of a lap.

        Parameters:
            lap_num:            Lap number (1-indexed).
            sector_num:         Sector number 1, 2, or 3.
            throttle_avg:       Average throttle % over the sector.
            brake_avg:          Average brake % over the sector.
            steering_avg:       Average steering angle magnitude over the sector.
            coasting_ms:        Total time in milliseconds with throttle = 0 and brake = 0.
            min_speed_kmh:      Minimum speed recorded in the sector.
            max_lateral_g:      Peak lateral G-force in the sector.
            max_longitudinal_g: Peak longitudinal G-force in the sector.
        """
        key = f"lap_{lap_num}"
        if key not in self._current_lap_data:
            self._current_lap_data[key] = {"sectors": {}}
        self._current_lap_data[key]["sectors"][f"s{sector_num}"] = {
            "throttle_avg":       round(throttle_avg, 1),
            "brake_avg":          round(brake_avg, 1),
            "steering_avg":       round(steering_avg, 1),
            "coasting_ms":        coasting_ms,
            "min_speed_kmh":      round(min_speed_kmh, 1),
            "max_lateral_g":      round(max_lateral_g, 2),
            "max_longitudinal_g": round(max_longitudinal_g, 2),
        }

    def record_lap_complete(
        self,
        lap_num:      int,
        lap_time_ms:  int,
        sector_1_ms:  int,
        sector_2_ms:  int,
        sector_3_ms:  int,
        tyre_wear_fl: float,
        tyre_wear_fr: float,
        tyre_wear_rl: float,
        tyre_wear_rr: float,
        tyre_temp_fl: int,
        tyre_temp_fr: int,
        tyre_temp_rl: int,
        tyre_temp_rr: int,
        ers_store_avg: float,
        fuel_remaining: float,
    ) -> None:
        """Stores complete lap data when the lap timer advances.

        Merges with any sector input data already recorded for this lap,
        appends to the lap list, and writes the file.

        Parameters:
            lap_num:         Completed lap number.
            lap_time_ms:     Total lap time in milliseconds.
            sector_1_ms:     Sector 1 time in milliseconds (0 if not available).
            sector_2_ms:     Sector 2 time in milliseconds.
            sector_3_ms:     Sector 3 time in milliseconds.
            tyre_wear_fl/fr/rl/rr: Per-corner tyre wear percentages.
            tyre_temp_fl/fr/rl/rr: Per-corner tyre surface temperatures.
            ers_store_avg:   Average ERS state of charge over the lap.
            fuel_remaining:  Fuel remaining in laps at lap end.
        """
        key        = f"lap_{lap_num}"
        sector_data = self._current_lap_data.pop(key, {}).get("sectors", {})

        lap_record: dict = {
            "lap_num":    lap_num,
            "lap_time_ms": lap_time_ms,
            "sectors": {
                "s1": {"time_ms": sector_1_ms},
                "s2": {"time_ms": sector_2_ms},
                "s3": {"time_ms": sector_3_ms},
            },
            "tyre_wear": {
                "fl": round(tyre_wear_fl, 1),
                "fr": round(tyre_wear_fr, 1),
                "rl": round(tyre_wear_rl, 1),
                "rr": round(tyre_wear_rr, 1),
            },
            "tyre_temps": {
                "fl": tyre_temp_fl,
                "fr": tyre_temp_fr,
                "rl": tyre_temp_rl,
                "rr": tyre_temp_rr,
            },
            "ers_store_avg":  round(ers_store_avg, 1),
            "fuel_remaining": round(fuel_remaining, 1),
        }

        # Merge sector driving input averages if available
        for sector_key, sector_inputs in sector_data.items():
            lap_record["sectors"].setdefault(sector_key, {}).update(sector_inputs)

        self._laps.append(lap_record)
        if len(self._laps) > MAX_LAPS_STORED:
            self._laps.pop(0)

        self.save_to_file()

    def record_wheelspin_event(self, lap_num: int, sector_num: int,
                               severity: float) -> None:
        """Logs a wheelspin event for coaching analysis.

        Parameters:
            lap_num:    Lap on which the event occurred.
            sector_num: Sector in which it occurred (1, 2, or 3).
            severity:   Slip ratio magnitude at the moment of detection.
        """
        self._wheelspin_log.append({
            "lap":      lap_num,
            "sector":   sector_num,
            "severity": round(severity, 3),
        })

    def save_to_file(self) -> None:
        """Writes all stored data to the session JSON file.

        Called automatically after each completed lap and should be called
        once more when the session ends to capture the final state.
        """
        payload = {
            "session_info":      self._session_info,
            "laps":              self._laps,
            "wheelspin_events":  self._wheelspin_log,
            "session_summary":   self.get_session_summary(),
        }
        with open(self.filename, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

    def get_lap_summary(self, lap_num: int) -> dict | None:
        """Returns the stored data record for a specific lap number.

        Parameters:
            lap_num: The lap number to look up (1-indexed).

        Returns:
            Lap record dict or None if the lap has not been recorded yet.
        """
        for lap in self._laps:
            if lap["lap_num"] == lap_num:
                return lap
        return None

    def get_session_summary(self) -> dict:
        """Returns aggregated statistics for the session so far.

        Includes laps completed, best lap time, average lap time, average
        tyre wear rate per lap, average fuel consumption per lap, and a
        consistency score (standard deviation of lap times in milliseconds).

        Returns:
            Dict with summary statistics. All values are 0 / 0.0 if fewer
            than two laps have been completed.
        """
        lap_count = len(self._laps)
        if lap_count == 0:
            return {
                "laps_completed":        0,
                "best_lap_time_ms":      0,
                "average_lap_time_ms":   0,
                "tyre_wear_rate_pct_lap": 0.0,
                "fuel_consumption_per_lap": 0.0,
                "lap_time_std_dev_ms":   0.0,
            }

        times     = [lap["lap_time_ms"] for lap in self._laps if lap["lap_time_ms"] > 0]
        best_time = min(times) if times else 0
        avg_time  = round(sum(times) / len(times)) if times else 0

        std_dev = 0.0
        if len(times) > 1:
            mean    = sum(times) / len(times)
            variance = sum((t - mean) ** 2 for t in times) / len(times)
            std_dev  = round(math.sqrt(variance))

        # Tyre wear rate: average FL+FR+RL+RR wear divided by laps
        wear_rate = 0.0
        if lap_count >= 2:
            first_lap = self._laps[0]["tyre_wear"]
            last_lap  = self._laps[-1]["tyre_wear"]
            avg_first = sum(first_lap.values()) / 4
            avg_last  = sum(last_lap.values()) / 4
            wear_rate = round((avg_last - avg_first) / lap_count, 2)

        # Fuel consumption per lap
        fuel_rate = 0.0
        if lap_count >= 2:
            first_fuel = self._laps[0].get("fuel_remaining", 0)
            last_fuel  = self._laps[-1].get("fuel_remaining", 0)
            if first_fuel > last_fuel:
                fuel_rate = round((first_fuel - last_fuel) / lap_count, 2)

        return {
            "laps_completed":           lap_count,
            "best_lap_time_ms":         best_time,
            "average_lap_time_ms":      avg_time,
            "tyre_wear_rate_pct_lap":   wear_rate,
            "fuel_consumption_per_lap": fuel_rate,
            "lap_time_std_dev_ms":      std_dev,
        }
