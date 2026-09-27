"""
Reference lap system — tracks personal best, AI best, and qualifying best for
coaching comparisons during a session.

No API calls, no network access — pure data storage and comparison.
Three tiers:
  - Personal best: player's fastest lap this session, with sector-level
    telemetry averages (speed, throttle, brake) and sector times.
  - AI best: fastest AI lap from Session History packets, sector times only.
  - Qualifying best: personal best promoted at the qualifying-to-race
    transition so it survives the session reset.
"""


# ---------------------------------------------------------------------------
# Comparison thresholds
# ---------------------------------------------------------------------------

# Minimum speed delta (km/h) worth reporting in a personal-best comparison
SPEED_DELTA_THRESHOLD_KMH    = 5

# Minimum throttle / brake delta (%) worth reporting
THROTTLE_DELTA_THRESHOLD_PCT = 8
BRAKE_DELTA_THRESHOLD_PCT    = 8

# Minimum AI sector time advantage (ms) worth reporting when no personal best
AI_TIME_DELTA_THRESHOLD_MS   = 200


# ---------------------------------------------------------------------------
# ReferenceLap
# ---------------------------------------------------------------------------

class ReferenceLap:
    """Stores and compares personal best, AI best, and qualifying best lap data.

    Personal best sector_data format:
        {sector_num: {avg_speed_kmh, avg_throttle_pct, avg_brake_pct, time_ms}}
    AI best / qualifying best sector_data format:
        {sector_num: {time_ms}}
    """

    def __init__(self) -> None:
        self._personal_best: dict | None   = None
        self._personal_best_time_ms: int   = 0
        self._ai_best: dict | None         = None
        self._ai_best_time_ms: int         = 0
        self._qualifying_best: dict | None = None
        self._qualifying_best_time_ms: int = 0

        # Running accumulators for the current lap; reset at each lap end
        self._sector_accumulator: dict[int, dict] = {
            1: {"count": 0, "speed_sum": 0.0, "throttle_sum": 0.0, "brake_sum": 0.0},
            2: {"count": 0, "speed_sum": 0.0, "throttle_sum": 0.0, "brake_sum": 0.0},
            3: {"count": 0, "speed_sum": 0.0, "throttle_sum": 0.0, "brake_sum": 0.0},
        }

    # --- Public API ---------------------------------------------------------

    def record_sector(self, sector_num: int, speed_kmh: float,
                      throttle_pct: float, brake_pct: float,
                      lap_distance_m: float) -> None:
        """Accumulates telemetry into the running average for the active sector.

        Called on every telemetry update (~60 Hz). Finalised at lap end by
        save_if_personal_best, which resets the accumulators for the next lap.
        lap_distance_m is accepted to satisfy the interface but not used in
        the average — sector identity is the grouping key.
        """
        if sector_num not in self._sector_accumulator:
            return
        acc = self._sector_accumulator[sector_num]
        acc["count"]        += 1
        acc["speed_sum"]    += speed_kmh
        acc["throttle_sum"] += throttle_pct
        acc["brake_sum"]    += brake_pct

    def save_if_personal_best(self, lap_time_ms: int,
                               sector_times: dict[int, int]) -> bool:
        """Saves the completed lap as the new personal best if it is faster.

        Finalises sector averages from the current accumulators and attaches
        sector times. Resets accumulators regardless of whether a PB was set,
        so the next lap starts from zero.

        Parameters:
            lap_time_ms:   Total lap time in milliseconds.
            sector_times:  {sector_num: time_ms} for the completed lap.

        Returns:
            True if a new personal best was set.
        """
        is_pb = (lap_time_ms > 0
                 and (self._personal_best_time_ms == 0
                      or lap_time_ms < self._personal_best_time_ms))
        if is_pb:
            self._personal_best_time_ms = lap_time_ms
            self._personal_best         = self._finalise_sector_averages(sector_times)
            print(f"[REF]  New personal best: {lap_time_ms} ms")
        self._reset_accumulators()
        return is_pb

    def update_ai_best(self, car_index: int, lap_time_ms: int,
                       sector_data: dict) -> None:
        """Records a faster AI lap if it beats the stored AI best.

        The player's car index must never be passed here — caller is responsible
        for filtering. sector_data format: {sector_num: {"time_ms": int}}.
        """
        if lap_time_ms <= 0:
            return
        if self._ai_best_time_ms == 0 or lap_time_ms < self._ai_best_time_ms:
            self._ai_best_time_ms = lap_time_ms
            self._ai_best         = sector_data

    def save_qualifying_best(self) -> None:
        """Promotes the current personal best to the qualifying reference.

        Must be called before reset_for_new_session so the personal best is
        captured before the session reset clears it.
        """
        if self._personal_best is not None:
            self._qualifying_best_time_ms = self._personal_best_time_ms
            self._qualifying_best         = dict(self._personal_best)

    def reset_for_new_session(self) -> None:
        """Clears personal best and AI best for a new session.

        Qualifying best is intentionally preserved — it was promoted by
        save_qualifying_best and must remain available throughout the race.
        """
        self._personal_best         = None
        self._personal_best_time_ms = 0
        self._ai_best               = None
        self._ai_best_time_ms       = 0
        self._reset_accumulators()

    def has_personal_best(self) -> bool:
        return self._personal_best is not None

    def has_ai_best(self) -> bool:
        return self._ai_best is not None

    def get_coaching_comparison(self, sector_num: int, current_speed: float,
                                current_throttle: float,
                                current_brake: float) -> str:
        """Returns a coaching string comparing current telemetry to the best reference.

        Uses personal best if available; falls back to AI best. Returns an
        empty string if no reference exists or no delta clears the threshold.
        AI-best coaching (no personal best) is purely qualitative because
        telemetry is not available for AI cars.
        """
        if self.has_personal_best():
            return self._compare_to_personal(
                sector_num, current_speed, current_throttle, current_brake
            )
        return ""

    def get_ai_timing_coaching(self, sector_num: int,
                                session_bests: tuple[int, int, int]) -> str:
        """Returns a timing-based coaching note comparing the AI best to the player's
        session best sector time for the given sector.

        Called by state_manager when no personal best telemetry comparison is
        possible. session_bests is (s1_ms, s2_ms, s3_ms).
        """
        if not self.has_ai_best():
            return ""
        sector = self._ai_best.get(sector_num)
        if not sector:
            return ""
        ai_time_ms = sector.get("time_ms", 0)
        if ai_time_ms <= 0:
            return ""
        player_best_ms = session_bests[sector_num - 1]
        if player_best_ms > 0:
            delta_ms = player_best_ms - ai_time_ms
            if delta_ms > AI_TIME_DELTA_THRESHOLD_MS:
                return (f"AI reference is {delta_ms / 1000:.1f}s faster through "
                        f"this sector — carrying more minimum speed through the exit")
        return ""

    def get_briefing_summary(self) -> dict:
        """Returns stored reference lap times for the briefing dict.

        coaching_note is added by the caller (state_manager) which has access
        to both this object and the session sector bests needed for AI timing.
        """
        return {
            "personal_best_ms":    self._personal_best_time_ms,
            "has_personal_best":   self.has_personal_best(),
            "ai_best_ms":          self._ai_best_time_ms,
            "has_ai_best":         self.has_ai_best(),
            "qualifying_best_ms":  self._qualifying_best_time_ms,
            "has_qualifying_best": self._qualifying_best is not None,
        }

    # --- Internal -----------------------------------------------------------

    def _finalise_sector_averages(self, sector_times: dict[int, int]) -> dict:
        result = {}
        for sector_num, acc in self._sector_accumulator.items():
            count = acc["count"]
            result[sector_num] = {
                "avg_speed_kmh":    round(acc["speed_sum"]    / count, 1) if count else 0.0,
                "avg_throttle_pct": round(acc["throttle_sum"] / count, 1) if count else 0.0,
                "avg_brake_pct":    round(acc["brake_sum"]    / count, 1) if count else 0.0,
                "time_ms":          sector_times.get(sector_num, 0),
            }
        return result

    def _reset_accumulators(self) -> None:
        for acc in self._sector_accumulator.values():
            acc["count"]        = 0
            acc["speed_sum"]    = 0.0
            acc["throttle_sum"] = 0.0
            acc["brake_sum"]    = 0.0

    def _compare_to_personal(self, sector_num: int, current_speed: float,
                              current_throttle: float, current_brake: float) -> str:
        sector = self._personal_best.get(sector_num)
        if not sector:
            return ""
        speed_delta    = sector["avg_speed_kmh"]    - current_speed
        throttle_delta = sector["avg_throttle_pct"] - current_throttle
        brake_delta    = sector["avg_brake_pct"]    - current_brake

        if abs(speed_delta) >= SPEED_DELTA_THRESHOLD_KMH:
            direction = "slower" if speed_delta > 0 else "faster"
            return (f"You are {abs(speed_delta):.0f} km/h {direction} through "
                    f"this sector than your best lap")
        if abs(throttle_delta) >= THROTTLE_DELTA_THRESHOLD_PCT:
            direction = "lower" if throttle_delta > 0 else "higher"
            return (f"Throttle pickup is {abs(throttle_delta):.0f}% {direction} "
                    f"than your best here")
        if abs(brake_delta) >= BRAKE_DELTA_THRESHOLD_PCT:
            direction = "braking later" if brake_delta > 0 else "braking earlier"
            return f"You are {direction} than your best lap through this sector"
        return ""
