"""
Phase 4 — Engineer AI Brain
Drives Gemini via Vertex AI with event-based triggers and an authentic F1 radio voice.
Session-aware: practice, qualifying, and race modes use distinct briefing formats
and trigger logic.

Trigger model:
  Practice     — speaks every 8 s, immediately for traffic or post-pit debrief.
  Qualifying   — speaks every 8 s on out laps, every 5 s when a car closes
                 within 15 s, immediately when a car is within 5 s on a push lap.
                 Silent during sectors 1 and 3 of a flying lap unless critical.
  Race         — speaks on gap changes > 0.3 s, pit window entry, accelerating
                 tyre degradation, safety car, position changes, every 3 laps.
  Universal    — no transmission within 20 s of the last unless critical.

Track knowledge (track_mapper brief + F1_KNOWLEDGE) is injected once per session
on the first briefing call; subsequent calls omit it to save tokens.
"""

import os
import time
from datetime import datetime

import google.genai as genai
from google.genai import types
from dotenv import load_dotenv

from circuit_reference import get_circuit_reference
from f1_knowledge import (
    TYRE_OPTIMAL_TEMPS,
    TYRE_WEAR_THRESHOLDS,
    ERS_THRESHOLDS,
    F1_KNOWLEDGE,
)
from practice_programmes import get_programme_by_id, get_recommended_programmes
from state_manager import RaceStateManager, _format_lap_time
import track_mapper


# ---------------------------------------------------------------------------
# API constants
# ---------------------------------------------------------------------------

GEMINI_MODEL         = "gemini-2.5-flash"
MAX_RESPONSE_TOKENS  = 1000
MAX_HISTORY_MESSAGES = 6


# ---------------------------------------------------------------------------
# Display constants
# ---------------------------------------------------------------------------

DISPLAY_SEPARATOR_WIDTH = 60
DISPLAY_SEPARATOR       = "=" * DISPLAY_SEPARATOR_WIDTH
TIMESTAMP_FORMAT        = "%H:%M:%S"


# ---------------------------------------------------------------------------
# Session classification — string names from the F1 25 UDP parser
# ---------------------------------------------------------------------------

PRACTICE_SESSION_TYPES = frozenset({
    "Practice 1", "Practice 2", "Practice 3", "Short Practice",
})

QUALIFYING_SESSION_TYPES = frozenset({
    "Q1", "Q2", "Q3", "Short Qualifying", "One-Shot Qualifying",
    "Sprint Shootout",
})


# ---------------------------------------------------------------------------
# Trigger timing constants
# ---------------------------------------------------------------------------

SILENCE_COOLDOWN_S            = 20.0
QUAL_OUT_LAP_CHECK_INTERVAL_S = 8.0
QUAL_CLOSING_CAR_CHECK_S      = 5.0
QUAL_NEARBY_CAR_THRESHOLD_S   = 15.0
QUAL_PUSH_LAP_WARN_GAP_S      = 5.0
PRACTICE_OUT_LAP_CHECK_S      = 8.0
PRACTICE_TRAFFIC_GAP_S        = 15.0   # report car behind when closer than this
PRACTICE_TRANSMISSION_COOLDOWN_S = 45.0  # minimum gap between regular practice transmissions
RACE_EVERY_N_LAPS             = 3
RACE_GAP_CHANGE_THRESHOLD_S   = 0.3
FLYING_LAP_SPEED_THRESHOLD    = 0.82   # fraction of session top speed

BATTLE_SILENCE_SECONDS        = 8
BATTLE_CRITICAL_WEAR_PCT      = 85.0

MAX_RECENT_TOPICS             = 5

# Pit status codes from F1 25 UDP — value of the pit_status field in race state
PIT_STATUS_ON_TRACK = 0   # car is on circuit
PIT_STATUS_PIT_LANE = 1   # car is in pit lane or garage (PS5 uses 1 for both in practice)
PIT_STATUS_GARAGE   = 2   # defined in F1 25 spec — PS5 never sends 2 in practice; do not use in conditions

# Approaching-car gap thresholds for practice traffic warnings (milliseconds)
APPROACHING_CAR_REPORT_THRESHOLD_MS  = 10000  # suppress traffic block when all cars beyond 10 s
APPROACHING_CAR_WARNING_1_MS         = 3000   # first warning — car is close
APPROACHING_CAR_WARNING_2_MS         = 1500   # urgent warning — car is very close
# Gap reduction since last transmission that triggers a "closing" label
CLOSING_GAP_THRESHOLD_MS             = 500

# Minimum transmissions between tyre-temperature mentions.
# A change in any corner's status label (cold/in-window/overheating) overrides this.
TYRE_TOPIC_COOLDOWN_TRANSMISSIONS = 3

# Lap 1 in any practice session is the out lap — programme lap counting starts at lap 2.
OUT_LAP_NUMBER = 1

# PS5 reports speed 1–3 km/h while the car sits stationary in the pit box.
# Any speed below this threshold is treated as "in garage" for briefing purposes.
GARAGE_SPEED_THRESHOLD_KMH = 5

# Gemini sampling temperature — 0.7 gives natural variation without hallucination risk.
GEMINI_TEMPERATURE = 0.7

# A car in DRS range is within 1 second. 0.9 is conservative so the warning
# fires before the actual DRS activation point.
DRS_RANGE_GAP_S = 0.9

# Clear the DRS threat flag once the gap grows beyond 1.0 second.
DRS_RANGE_CLEAR_THRESHOLD_S = 1.0

# Minimum gap change (seconds) that counts as a meaningful trend — below this
# the gap is considered stable and no closing/pulling-away label is shown.
GAP_TREND_MIN_CHANGE_S = 0.05

# Gap to car ahead above which the player is considered in clean free air.
FREE_AIR_AHEAD_THRESHOLD_S = 3.0

# Tyre wear rate (% per lap) acceleration that triggers a degradation warning.
# If the rate increases by more than this between two consecutive laps the tyres
# are degrading faster than expected and the engineer should flag it.
TYRE_DEGRADATION_RATE_THRESHOLD_PCT = 1.0


# ---------------------------------------------------------------------------
# Safety car status codes
# ---------------------------------------------------------------------------

_SAFETY_CAR_LABELS = {
    1: "Full Safety Car",
    2: "Virtual Safety Car",
    3: "Safety Car ending",
    4: "VSC ending",
}


# ---------------------------------------------------------------------------
# Engineer system prompt
# F1_KNOWLEDGE is NOT injected here — it is sent once per session
# via the track knowledge briefing block to avoid repeating it on every call.
# ---------------------------------------------------------------------------

ENGINEER_SYSTEM_PROMPT = """\
You are an F1 race engineer communicating with your driver over team radio during a live session. You have deep knowledge of F1 25 game mechanics, real F1 strategy, tyre behaviour, ERS management, and race craft.

FUNDAMENTAL RULE — THIS OVERRIDES EVERYTHING:
You are speaking out loud over team radio. Every single transmission must be one or two complete spoken sentences. A sentence must have a subject, verb, and end with a full stop. You must never stop in the middle of a sentence under any circumstances. If you have nothing important to say, output only the single word: SILENCE. Short complete sentences are perfectly fine. Incomplete fragments are never acceptable under any condition. A semicolon, comma, or dash is never the end of a transmission — you must always reach a full stop before stopping.

COMMUNICATION RULES — follow these exactly:
- Maximum 2 sentences per transmission. Both must be complete sentences.
- Simple updates (single gap report, one tyre status, one corner note) must be one short sentence only. Only sector feedback, programme briefing, and programme debrief may use two sentences.
- Use tenths and hundredths for all time gaps under 10 seconds. 'Leclerc behind, 0.8 seconds.' Over 10 seconds use one decimal. 'Hamilton behind, 12.3 seconds.'
- CORNER REFERENCES: Always reference corners using both their type and number. Format: the [corner type] at Turn [number]. Examples: the hairpin at Turn 3, the chicane at Turn 6, the long right hander at Turn 12. Use the corner type descriptions from the TRACK KNOWLEDGE section. Never use just a corner name or just a number alone.
- Never repeat advice given in the last 3 transmissions unless situation has materially changed.
- Never mention tyre wear percentages to the driver. Say 'your front right is starting to go' not '24.1%'.
- Never mention ERS store percentage. Say 'you have plenty of ERS' or 'ERS is getting low, harvest through the next slow section'.

TYRE TEMPERATURE RULES:
- Tell the driver if a tyre is outside its optimal window and what to do about it.
- Below optimal on out lap: 'tyres still coming in, build the heat gradually through the next two corners.'
- Above optimal: name the tyre, say it is overheating, give one instruction to protect it.
- In qualifying: aim to start lap slightly below optimal so temps peak mid-lap.
- Do not repeat tyre temperature status within 3 transmissions of the last mention unless a tyre's status label has explicitly changed (cold to in window, in window to overheating, etc.). When the context block says SUPPRESSED, obey it.

TYRE WEAR RULES:
- Above 40% wear on any tyre: mention it once, give one management instruction.
- Above 60%: mention once per lap if it's the leading wear corner, give specific instruction.
- Above 75%: urgent, mention every lap, recommend boxing soon.
- Above 85%: immediate box call.
- Never repeat the same tyre warning twice in a row unless wear threshold has increased.

ERS RULES:
- Car behind within 1.2 seconds on approach to a DRS straight: 'use ERS on this straight, [car name] is close.'
- Car ahead within 2 seconds at an overtaking corner: advise ERS deployment at that specific corner type.
- ERS below 25%: tell driver to harvest through the next slow section or braking zone. Once only.
- In free air with no threats: only give ERS advice if driver can gain meaningful lap time from it.

GAP RULES — RACE:
- Report gap to car ahead and behind when gap changes by more than 0.3 seconds. One sentence.
- If closing on car ahead: state gap and closing rate. 'Verstappen ahead, 1.4 seconds, closing 0.2 per lap.'
- If car behind closing: state gap and trend. 'Norris behind, 0.8 seconds, he's coming.'
- When car behind enters DRS range: immediate warning. 'Norris in your DRS.'
- When car behind is within 0.5 seconds: 'Norris right behind, defend the hairpin.'

GAP RULES — QUALIFYING:
- When car is on out lap or between runs: report every nearby car with gap and status.
- When car behind is on push lap: '15 seconds, push lap.' Then '10 seconds.' Then '5 seconds, let him through.'
- When track is clear: 'track clear, push this lap.' or 'take another prep lap, Leclerc is slow ahead at 8 seconds.'
- After push lap: give sector comparison to session leader.
- During push lap: stay silent unless a car is about to be encountered.

STRATEGY RULES — RACE:
- Pit window: mention first time 5 laps before ideal lap. Mention once per lap from that point.
- Use the game's calculated pit window data. Say 'pit window opens in 3 laps' or 'we are in the window now.'
- When making a pit call: state call, one sentence of context. 'Box this lap — you come out P4 ahead of Hamilton in clean air.'
- When rival pits: tell driver only if it affects their strategy.
- Safety car: explain situation first, then recommendation.
- VSC: same as safety car but note VSC saves less time.
- After pitting: tell driver who is ahead and behind and gaps.

PRACTICE MODE RULES:
- In practice: give one concrete coaching point per lap maximum based on telemetry data.
- The practice programme is always active and already running. Never tell the driver to activate, start, or begin a programme. Reference it as currently under way.
- Keep the driver focused on the programme objective when a programme is active.
- Tyre warming on out lap: give specific warm-up instruction based on tyre type and current temperature.
- Traffic in practice: only report a car when within 10 seconds. First warning: 'Name, X seconds behind.' Second warning: 'Name, X seconds.' Final call: 'Name is through.' Never name a car beyond 10 seconds. Never give more than a short sentence for a gap update.
- Use the CIRCUIT REFERENCE corner notes to frame coaching at specific turns.
- After pit entry: give a short debrief on the stint data collected.

PERFORMANCE COACHING RULES:
- If pace is dropping over last 2 laps: identify the most likely cause from tyre temps, wear, or sector data.
- One corner opportunity per lap maximum. Name the corner type, give one specific instruction.
- When REFERENCE LAP data is available, give one specific coaching point per lap about where the driver is losing time. Name the corner type and number using the CORNER REFERENCES format. Never give reference coaching if in a battle.
- Praise a personal best lap: 'good lap, that's your best of the session.' Bigger: 'that's the fastest lap of the session, excellent.'
- Point out mistakes but keep moving: 'lost time at the chicane, keep going.'

SILENCE RULES:
- If you begin a sentence you must finish it before outputting anything else.
- When silence is the correct call, output only the single word: SILENCE
- During sectors 1 and 3 of a qualifying push lap: SILENCE unless collision is imminent.
- If nothing material has changed since last transmission: SILENCE.
- If the last 3 transmissions covered the same topic: SILENCE.
- When racing in free air with stable tyres and no strategic decisions pending: SILENCE.
- Once you decide to speak, complete your full thought. Never begin a sentence you do not finish.

WHAT NEVER TO SAY:
- Never use team radio codes like 'strat 6', 'red A4', 'purple C7'.
- Never say 'great job' or 'well done' without a specific reason.
- Never give more than one instruction at a time.
- Never mention raw numbers like ERS percentage or tyre wear percentage.
- Never contradict a call made in the previous lap without a clear reason stated.
"""


# ---------------------------------------------------------------------------
# EngineerAI
# ---------------------------------------------------------------------------

class EngineerAI:
    """Drives Gemini via Vertex AI with event-based triggers and authentic F1 radio voice.

    Session-aware: routes to practice, qualifying, or race mode based on
    current session_type. Track knowledge and F1_KNOWLEDGE are injected once
    per session on the first briefing call then suppressed to save tokens.

    Attributes:
        conversation_history: Rolling list of message dicts in Gemini API format.
    """

    def _init_gemini_client(self) -> None:
        """Loads .env, validates credentials, and initialises the Gemini Vertex AI client.

        Parameters:
            None

        Returns:
            None
        """
        load_dotenv()
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        region  = os.getenv("GOOGLE_CLOUD_REGION")
        if not project or not region:
            raise EnvironmentError(
                "GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_REGION not found — check your .env file."
            )
        self._client = genai.Client(vertexai=True, project=project, location=region)

    def _init_timing_and_session_state(self) -> None:
        """Initialises all timing, session classification, and nearby-car attributes.

        Parameters:
            None

        Returns:
            None
        """
        self._last_response_time:         float       = 0.0
        self._last_qual_car_check_s:      float       = 0.0  # coaching interval timer
        self._last_traffic_check_s:       float       = 0.0  # traffic proximity timer
        self._last_transmission_lap:      int         = 0
        self._pit_window_announced:       bool        = False
        self._last_tyre_compound:         str         = ""
        self._session_type:               str         = "Unknown"
        self._session_top_speed_kmh:      float       = 0.0
        self._is_flying_lap:              bool        = False
        self._nearby_cars: dict = {
            "ahead":  {"driver": None, "gap": None, "prev_gap": None},
            "behind": {"driver": None, "gap": None, "prev_gap": None},
        }
        self._handled_event_signatures:   set[str]    = set()
        self._recent_topics:              list[str]   = []
        self._current_position:           int         = 0
        self._last_position_change_time:  float       = 0.0

    def _init_practice_state(self) -> None:
        """Initialises all practice-mode programme and briefing state attributes.

        Parameters:
            None

        Returns:
            None
        """
        self._active_programme:                dict | None = None
        self._programme_lap_count:             int         = 0
        self._last_programme_lap:              int         = 0
        self._programme_complete:              bool        = False
        self._programme_debrief_done:          bool        = False
        self._practice_debrief_pending:        bool        = False
        self._garage_briefing_pending:         bool        = False
        self._garage_briefing_done:            bool        = False
        self._last_behind_gap_ms:              int         = 0
        self._tyre_transmissions_since_mention: int        = 0
        self._last_tyre_status:                dict        = {}
        self._session_data_store                           = None  # set externally by server.py

    def _init_track_knowledge_state(self) -> None:
        """Initialises circuit reference and track knowledge gate attributes.

        Parameters:
            None

        Returns:
            None
        """
        self._circuit_reference:    dict | None = None
        self._track_knowledge_sent: bool        = False
        self._loaded_track_name:    str         = ""
        self._loaded_session_type:  str         = ""

    def __init__(self) -> None:
        """Initialises the EngineerAI, loads credentials, and sets all state to defaults.

        Parameters:
            None

        Returns:
            None
        """
        self._init_gemini_client()
        self.conversation_history: list[dict] = []
        self._init_timing_and_session_state()
        self._init_practice_state()
        self._init_track_knowledge_state()

    # --- Public API ---------------------------------------------------------

    def _check_battle_speak(self, briefing: dict) -> bool:
        """Returns True if a transmission should fire during a battle window.

        During the BATTLE_SILENCE_SECONDS window after a position change,
        only safety car events and critical tyre wear pass through.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            True if an allowed critical event exists; False otherwise.
        """
        state    = briefing["current_state"]
        critical = self.get_critical_trigger(briefing)
        if critical is None:
            return False
        if critical["type"] == "SAFETY_CAR":
            return True
        if critical["type"] == "TYRE_CRITICAL":
            return self._any_corner_above(state, BATTLE_CRITICAL_WEAR_PCT)
        return False

    def should_speak(self, briefing: dict) -> bool:
        """Returns True if the engineer should transmit a radio message now.

        Checks mode-specific trigger logic and the global silence cooldown.
        In battle mode only safety car and critical tyre events pass through.

        Parameters:
            briefing: Full engineer briefing dict produced by state_manager.

        Returns:
            True if a transmission should be generated this cycle.
        """
        self._update_session_tracking(briefing["current_state"])
        mode = self._session_mode()
        if mode == "practice":
            return self._check_practice_triggers(briefing)
        if self._is_in_battle():
            return self._check_battle_speak(briefing)
        if self.get_critical_trigger(briefing) is not None:
            return True
        if self._time_since_last_response() < SILENCE_COOLDOWN_S:
            return False
        if mode == "qualifying":
            return self._check_qualifying_triggers(briefing)
        return self._check_race_triggers(briefing)

    def _check_tyre_and_position_events(self, briefing: dict,
                                        mode: str) -> dict | None:
        """Checks for unhandled tyre-critical and position-change events.

        Searches recent_events in order; returns the first unhandled match.

        Parameters:
            briefing: Full engineer briefing dict.
            mode:     Current session mode string ('race', 'qualifying', 'practice').

        Returns:
            Event dict if found, else None.
        """
        for event in briefing["recent_events"]:
            if event["type"] == "TYRE_CRITICAL":
                event_signature = self._event_signature(event)
                if event_signature not in self._handled_event_signatures:
                    return event
        if mode == "race":
            for event in briefing["recent_events"]:
                if event["type"] in ("OVERTAKE", "OVERTAKEN"):
                    event_signature = self._event_signature(event)
                    if event_signature not in self._handled_event_signatures:
                        return event
        return None

    def get_critical_trigger(self, briefing: dict) -> dict | None:
        """Returns the first unhandled critical event, or None.

        Priority order: safety car → tyre critical / overtake → qual traffic.
        Critical events bypass the 20-second silence cooldown.

        Parameters:
            briefing: Full engineer briefing dict produced by state_manager.

        Returns:
            Event dict with 'type', 'detail', and 'sig' keys, or None.
        """
        state = briefing["current_state"]
        mode  = self._session_mode()

        if mode == "race" and state.get("safety_car_status"):
            event_signature = f"safety_car_lap_{state['current_lap']}"
            if event_signature not in self._handled_event_signatures:
                return {"type": "SAFETY_CAR", "detail": "Safety car deployed",
                        "sig": event_signature}

        result = self._check_tyre_and_position_events(briefing, mode)
        if result is not None:
            return result

        if mode == "qualifying" and self._is_flying_lap:
            ahead_gap = self._nearby_cars["ahead"].get("gap")
            if ahead_gap is not None and ahead_gap < QUAL_PUSH_LAP_WARN_GAP_S:
                event_signature = (f"qual_warn_lap_{state['current_lap']}"
                                   f"_s{state.get('sector', 1)}")
                if event_signature not in self._handled_event_signatures:
                    return {"type": "QUAL_TRAFFIC_CRITICAL",
                            "detail": f"Car ahead, {ahead_gap:.1f}s — push lap obstruction",
                            "sig": event_signature}
        return None

    def _handle_practice_pit_flags(self, pit_status: int, speed: float) -> None:
        """Sets garage or debrief pending flags based on pit lane entry in practice.

        PS5 sends pit_status 1 for both garage and pit lane — speed below
        GARAGE_SPEED_THRESHOLD_KMH distinguishes a stationary garage from a
        moving pit lane entry.

        Parameters:
            pit_status: Pit status code from the race state packet.
            speed:      Current car speed in km/h.

        Returns:
            None
        """
        if pit_status != PIT_STATUS_PIT_LANE:
            return
        if speed >= GARAGE_SPEED_THRESHOLD_KMH:
            self._practice_debrief_pending = True
        elif not self._garage_briefing_done:
            self._garage_briefing_pending = True
            self._garage_briefing_done    = True

    def _update_post_transmission_state(self, briefing: dict,
                                        trigger: dict | None,
                                        engineer_text: str) -> None:
        """Advances all session state that changes after a successful transmission.

        Updates topic history, tyre cooldown counter, gap baseline,
        pit window flag, and clears any pending one-shot briefing flags.

        Parameters:
            briefing:      Full engineer briefing dict.
            trigger:       Critical event dict if one fired, else None.
            engineer_text: The engineer's radio transmission text.

        Returns:
            None
        """
        topic = trigger["type"] if trigger else self._infer_topic(engineer_text)
        if topic == "TYRES":
            self._tyre_transmissions_since_mention = 0
            self._last_tyre_status = self._capture_tyre_status(briefing)
        else:
            self._tyre_transmissions_since_mention += 1

        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        self._recent_topics.insert(0, f"[{timestamp}] {topic}")
        del self._recent_topics[MAX_RECENT_TOPICS:]

        track_behind = briefing.get("track_car_behind")
        if track_behind:
            self._last_behind_gap_ms = track_behind["gap_ms"]

        pit_window = briefing.get("pit_window_estimate_laps")
        if pit_window is not None and pit_window <= 0:
            self._pit_window_announced = True

        if self._practice_debrief_pending:
            self._practice_debrief_pending = False
        if self._garage_briefing_pending:
            self._garage_briefing_pending = False
        if self._programme_complete and not self._programme_debrief_done:
            self._programme_debrief_done = True

    def get_engineer_response(self, briefing: dict) -> str | None:
        """Calls Gemini with the formatted briefing and returns the engineer's message.

        Builds the prompt, calls Gemini, advances all post-transmission state.
        Returns None if Gemini responds with SILENCE — the briefing is discarded
        from history but the cooldown timer still advances.

        Parameters:
            briefing: Full engineer briefing dict produced by state_manager.

        Returns:
            Engineer radio message string, or None if SILENCE.
        """
        state = briefing["current_state"]
        if self._session_mode() == "practice":
            self._handle_practice_pit_flags(
                state.get("pit_status", PIT_STATUS_ON_TRACK),
                state.get("speed_kmh", 0),
            )

        trigger       = self.get_critical_trigger(briefing)
        briefing_text = self.format_briefing_for_prompt(briefing, trigger)
        self._append_user_message(briefing_text)
        try:
            api_response = self._call_gemini()
        except Exception as exc:
            self.conversation_history.pop()
            print(f"[ENGINEER]  Gemini API error: {exc}")
            raise

        engineer_text = api_response.text
        usage = getattr(api_response, "usage_metadata", None)
        if usage:
            in_tokens  = getattr(usage, "prompt_token_count",     0)
            out_tokens = getattr(usage, "candidates_token_count", 0)
            print(f"[TOKENS]  in: {in_tokens}  out: {out_tokens}")

        if engineer_text.strip().upper() == "SILENCE":
            self.conversation_history.pop()
            self._last_response_time = time.monotonic()
            return None

        self._append_assistant_message(engineer_text)
        self._trim_history()
        self._mark_events_handled(briefing, trigger)
        self._last_response_time    = time.monotonic()
        self._last_transmission_lap = state.get("current_lap", 0)
        self._update_post_transmission_state(briefing, trigger, engineer_text)
        return engineer_text

    def _build_practice_blocks(self, briefing: dict) -> list[str]:
        """Assembles the ordered list of block strings for practice mode.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            List of block strings (some may be empty; filtered in caller).
        """
        return [
            self._format_practice_session_block(briefing),
            self._format_track_position_block(briefing),
            self._format_tyre_block(briefing),
            self._format_practice_traffic_block(briefing),
            self._format_circuit_reference_block(briefing, "qualifying"),
            self._format_reference_block(briefing),
            self._format_recent_topics_block(),
            self._format_track_knowledge_block(briefing),
        ]

    def _build_qualifying_blocks(self, briefing: dict,
                                  trigger: dict | None) -> list[str]:
        """Assembles the ordered list of block strings for qualifying mode.

        Parameters:
            briefing: Full engineer briefing dict.
            trigger:  Critical event dict or None.

        Returns:
            List of block strings.
        """
        return [
            self._format_situation_block(briefing, trigger),
            self._format_qualifying_traffic_block(),
            self._format_personal_best_block(briefing),
            self._format_circuit_reference_block(briefing, "qualifying"),
            self._format_recent_topics_block(),
            self._format_track_knowledge_block(briefing),
        ]

    def _build_race_blocks(self, briefing: dict,
                            trigger: dict | None) -> list[str]:
        """Assembles the ordered list of block strings for race mode.

        Parameters:
            briefing: Full engineer briefing dict.
            trigger:  Critical event dict or None.

        Returns:
            List of block strings.
        """
        return [
            self._format_situation_block(briefing, trigger),
            self._format_race_situation_block(briefing),
            self._format_tyre_block(briefing),
            self._format_strategy_block(briefing),
            self._format_circuit_reference_block(briefing, "race"),
            self._format_recent_topics_block(),
            self._format_recent_events_block(briefing),
            self._format_lap_history_block(briefing),
            self._format_track_knowledge_block(briefing),
            self._format_reference_block(briefing),
        ]

    def format_briefing_for_prompt(self, briefing: dict,
                                   trigger: dict | None = None) -> str:
        """Builds the full data briefing string to send to Gemini.

        Routes to a different block set depending on session mode.
        Empty blocks (empty string return) are silently filtered out by
        filter(None, blocks) before joining.

        Parameters:
            briefing: Full engineer briefing dict produced by state_manager.
            trigger:  Critical event dict if one fired this cycle, else None.

        Returns:
            Newline-separated prompt string ready to send to Gemini.
        """
        mode = self._session_mode()
        if mode == "practice":
            blocks = self._build_practice_blocks(briefing)
        elif mode == "qualifying":
            blocks = self._build_qualifying_blocks(briefing, trigger)
        else:
            blocks = self._build_race_blocks(briefing, trigger)
        return "\n\n".join(filter(None, blocks))

    # --- Internal: session mode ---------------------------------------------

    def _session_mode(self) -> str:
        """Returns 'practice', 'qualifying', or 'race' for the current session.

        Parameters:
            None

        Returns:
            One of 'practice', 'qualifying', or 'race'.
        """
        if self._session_type in PRACTICE_SESSION_TYPES:
            return "practice"
        if self._session_type in QUALIFYING_SESSION_TYPES:
            return "qualifying"
        return "race"

    def _is_practice(self) -> bool:
        """Returns True if the current session is a practice session.

        Parameters:
            None

        Returns:
            True if session_type is in PRACTICE_SESSION_TYPES.
        """
        return self._session_type in PRACTICE_SESSION_TYPES

    def _is_qualifying(self) -> bool:
        """Returns True if the current session is a qualifying session.

        Parameters:
            None

        Returns:
            True if session_type is in QUALIFYING_SESSION_TYPES.
        """
        return self._session_type in QUALIFYING_SESSION_TYPES

    # --- Internal: trigger checks -------------------------------------------

    def _check_practice_triggers(self, briefing: dict) -> bool:
        """Returns True if a practice transmission should fire this cycle.

        Priority order: debrief pending → garage briefing pending →
        programme complete → traffic warning → regular coaching interval.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            True if a transmission should fire.
        """
        if self._practice_debrief_pending:
            return True
        if self._garage_briefing_pending:
            return True
        if self._programme_complete and not self._programme_debrief_done:
            return True

        now              = time.monotonic()
        since_last       = self._time_since_last_response()

        # Traffic warning: uses _last_traffic_check_s (independent of coaching interval)
        # so a gap warning can fire even if coaching recently transmitted.
        behind_gap = self._nearby_cars["behind"].get("gap")
        if (behind_gap is not None
                and behind_gap < PRACTICE_TRAFFIC_GAP_S
                and since_last >= SILENCE_COOLDOWN_S
                and now - self._last_traffic_check_s >= QUAL_CLOSING_CAR_CHECK_S):
            self._last_traffic_check_s = now
            return True

        # Regular coaching / programme briefing: _last_qual_car_check_s controls only
        # the coaching interval; traffic above did not consume this slot.
        if since_last < PRACTICE_TRANSMISSION_COOLDOWN_S:
            return False
        if now - self._last_qual_car_check_s >= PRACTICE_OUT_LAP_CHECK_S:
            self._last_qual_car_check_s = now
            return True

        return False

    def _check_qualifying_triggers(self, briefing: dict) -> bool:
        """Returns True if a qualifying transmission should fire this cycle.

        Silent during sectors 1 and 3 of a push lap. Fires on the out-lap
        interval or when a car is within QUAL_NEARBY_CAR_THRESHOLD_S.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            True if a transmission should fire.
        """
        state  = briefing["current_state"]
        sector = state.get("sector", 1)

        if self._is_flying_lap and sector in (1, 3):
            return False

        now = time.monotonic()

        if not self._is_flying_lap:
            if now - self._last_qual_car_check_s >= QUAL_OUT_LAP_CHECK_INTERVAL_S:
                self._last_qual_car_check_s = now
                return True

        behind_gap = self._nearby_cars["behind"].get("gap")
        if behind_gap is not None and behind_gap < QUAL_NEARBY_CAR_THRESHOLD_S:
            if now - self._last_qual_car_check_s >= QUAL_CLOSING_CAR_CHECK_S:
                self._last_qual_car_check_s = now
                return True

        return False

    def _check_race_triggers(self, briefing: dict) -> bool:
        """Returns True if a race transmission should fire this cycle.

        Fires on significant gap changes, pit window entry, accelerating tyre
        degradation, or the every-N-laps interval.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            True if a transmission should fire.
        """
        state = briefing["current_state"]

        if self._has_significant_gap_change():
            return True

        pit_window = briefing.get("pit_window_estimate_laps")
        if pit_window is not None and pit_window <= 0 and not self._pit_window_announced:
            return True

        if self._tyre_degradation_accelerating(briefing):
            return True

        current_lap = state.get("current_lap", 0)
        if current_lap > 0 and current_lap - self._last_transmission_lap >= RACE_EVERY_N_LAPS:
            return True

        return False

    def _has_significant_gap_change(self) -> bool:
        """Returns True if either nearby gap changed by more than RACE_GAP_CHANGE_THRESHOLD_S.

        Parameters:
            None

        Returns:
            True if any gap change exceeds the threshold.
        """
        for side in ("ahead", "behind"):
            gap      = self._nearby_cars[side].get("gap")
            prev_gap = self._nearby_cars[side].get("prev_gap")
            if gap is not None and prev_gap is not None:
                if abs(gap - prev_gap) >= RACE_GAP_CHANGE_THRESHOLD_S:
                    return True
        return False

    @staticmethod
    def _average_tyre_wear(lap: dict) -> float:
        """Returns the mean wear percentage across all four tyres for a single lap record.

        Parameters:
            lap: Lap history dict containing tyre_wear_front_left/right and
                 tyre_wear_rear_left/right keys.

        Returns:
            Average wear percentage as a float.
        """
        return (lap["tyre_wear_front_left"]  + lap["tyre_wear_front_right"] +
                lap["tyre_wear_rear_left"]   + lap["tyre_wear_rear_right"]) / 4

    def _tyre_degradation_accelerating(self, briefing: dict) -> bool:
        """Returns True if the tyre wear rate is increasing lap on lap.

        Compares the wear delta between the last two completed laps against
        the delta between the two laps before that. If the rate is accelerating
        by more than TYRE_DEGRADATION_RATE_THRESHOLD_PCT, the tyres are
        degrading faster than normal and a transmission should be triggered.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            True if wear rate has accelerated; False if fewer than 3 laps or stable.
        """
        history = briefing.get("lap_history_summary", [])
        if len(history) < 3:
            return False
        rate_last   = self._average_tyre_wear(history[-1]) - self._average_tyre_wear(history[-2])
        rate_before = self._average_tyre_wear(history[-2]) - self._average_tyre_wear(history[-3])
        return rate_last > rate_before + TYRE_DEGRADATION_RATE_THRESHOLD_PCT

    # --- Internal: session state updates ------------------------------------

    def _update_programme_tracking(self, state: dict) -> None:
        """Advances the practice programme lap counter and marks completion.

        Skips lap 1 (the out lap) so programme counting starts on lap 2.
        Sets _programme_complete once the required lap count is reached;
        that flag stays True — it is not cleared so as to avoid re-triggering.

        Parameters:
            state: Current race state dict.

        Returns:
            None
        """
        if self._active_programme is None:
            return
        current_lap = state.get("current_lap", 0)
        if current_lap > self._last_programme_lap and current_lap > OUT_LAP_NUMBER:
            self._programme_lap_count += 1
            self._last_programme_lap   = current_lap
        if (not self._programme_complete
                and self._programme_lap_count >= self._active_programme["recommended_laps"]):
            self._programme_complete = True

    def _update_garage_detection(self, state: dict, speed: float) -> None:
        """Sets the garage briefing pending flag when the car is stationary in the pits.

        Only fires once per session. PS5 sends pit_status 1 for both garage
        and pit lane — low speed (< GARAGE_SPEED_THRESHOLD_KMH) distinguishes garage.

        Parameters:
            state: Current race state dict.
            speed: Current car speed in km/h.

        Returns:
            None
        """
        if (self._is_practice()
                and state.get("pit_status", PIT_STATUS_ON_TRACK) == PIT_STATUS_PIT_LANE
                and speed < GARAGE_SPEED_THRESHOLD_KMH
                and not self._garage_briefing_done):
            self._garage_briefing_pending = True
            self._garage_briefing_done    = True

    def _update_session_tracking(self, state: dict) -> None:
        """Updates all per-tick session state from the latest race state packet.

        Detects session/track changes, tracks top speed, updates nearby cars,
        advances programme tracking, and detects garage entry.

        Parameters:
            state: Current race state dict from state_manager.

        Returns:
            None
        """
        new_session_type = state.get("session_type", "Unknown")
        new_track_name   = state.get("track_name", "")
        if (new_session_type != self._loaded_session_type
                or new_track_name != self._loaded_track_name):
            self._load_session_resources(state)

        self._session_type = new_session_type
        speed = state.get("speed_kmh", 0)
        if speed > self._session_top_speed_kmh:
            self._session_top_speed_kmh = float(speed)
        if self._session_top_speed_kmh > 0:
            self._is_flying_lap = speed >= self._session_top_speed_kmh * FLYING_LAP_SPEED_THRESHOLD

        self._update_nearby_cars(state)
        self._update_position_tracking(state)

        compound = state.get("tyre_compound", "")
        if compound and compound != self._last_tyre_compound:
            self._pit_window_announced = False
            self._last_tyre_compound   = compound

        self._update_programme_tracking(state)
        self._update_garage_detection(state, speed)

    def _reset_session_practice_state(self, state: dict) -> None:
        """Resets all practice programme and briefing flags for a new session.

        Parameters:
            state: Current race state dict (used for current_lap baseline).

        Returns:
            None
        """
        self._programme_lap_count              = 0
        self._last_programme_lap               = state.get("current_lap", 0)
        self._programme_complete               = False
        self._programme_debrief_done           = False
        self._practice_debrief_pending         = False
        self._garage_briefing_pending          = False
        self._garage_briefing_done             = False
        self._last_behind_gap_ms               = 0
        self._tyre_transmissions_since_mention = 0
        self._last_tyre_status                 = {}

    def _select_practice_programme(self, state: dict) -> None:
        """Auto-selects the first recommended programme for a practice session.

        Qualifying and race have no programme system — sets _active_programme to None.

        Parameters:
            state: Current race state dict (used for session_type and total_laps).

        Returns:
            None
        """
        session_type = state.get("session_type", "Unknown")
        if session_type in PRACTICE_SESSION_TYPES:
            total_laps  = state.get("total_laps", 0) or 20
            recommended = get_recommended_programmes(total_laps)
            self._active_programme = (
                get_programme_by_id(recommended[0]) if recommended else None
            )
        else:
            self._active_programme = None

    def _load_session_resources(self, state: dict) -> None:
        """Resets all session-scoped state and loads circuit reference on session change.

        Runs exactly once per session — on the first tick that identifies a new
        track or session type. This guarantees _active_programme is populated
        before the first briefing call without any additional trigger logic.

        Parameters:
            state: Current race state dict.

        Returns:
            None
        """
        track_name   = state.get("track_name", "")
        session_type = state.get("session_type", "Unknown")
        self._circuit_reference    = get_circuit_reference(track_name)
        self._track_knowledge_sent = False
        self._loaded_track_name    = track_name
        self._loaded_session_type  = session_type
        self._reset_session_practice_state(state)
        self._select_practice_programme(state)

    def _update_nearby_cars(self, state: dict) -> None:
        """Updates gap and driver data for the cars immediately ahead and behind.

        Gap ahead comes from gap_to_ahead_ms in the state packet.
        Gap behind comes from delta_to_car_in_front_ms on the car behind —
        that field records the gap from that car to its car in front (us).
        DRS status is stored separately; it does not override the gap value.

        Parameters:
            state: Current race state dict.

        Returns:
            None
        """
        all_cars   = state.get("all_cars", [])
        player_pos = state.get("position", 0)

        gap_ahead_ms = state.get("gap_to_ahead_ms", 0)
        if player_pos > 1 and gap_ahead_ms > 0:
            ahead_car = self._find_car_at_position(all_cars, player_pos - 1)
            self._nearby_cars["ahead"]["prev_gap"] = self._nearby_cars["ahead"]["gap"]
            self._nearby_cars["ahead"]["gap"]      = round(gap_ahead_ms / 1000.0, 2)
            if ahead_car:
                self._nearby_cars["ahead"]["driver"] = ahead_car.get("name") or "car ahead"

        behind_car = self._find_car_at_position(all_cars, player_pos + 1)
        if behind_car:
            self._nearby_cars["behind"]["driver"] = behind_car.get("name") or "car behind"
            raw_gap_ms = behind_car.get("delta_to_car_in_front_ms", 0)
            if raw_gap_ms > 0:
                self._nearby_cars["behind"]["prev_gap"] = self._nearby_cars["behind"]["gap"]
                self._nearby_cars["behind"]["gap"]      = round(raw_gap_ms / 1000.0, 2)
            self._nearby_cars["behind"]["drs_threat"] = bool(behind_car.get("drs_allowed"))

    def _is_in_battle(self) -> bool:
        """Returns True if a position change occurred within BATTLE_SILENCE_SECONDS ago.

        Parameters:
            None

        Returns:
            True if currently in a battle window.
        """
        if self._last_position_change_time == 0.0:
            return False
        return time.monotonic() - self._last_position_change_time < BATTLE_SILENCE_SECONDS

    def _update_position_tracking(self, state: dict) -> None:
        """Records the time of the most recent position change for battle detection.

        Parameters:
            state: Current race state dict.

        Returns:
            None
        """
        position = state.get("position", 0)
        if position > 0 and position != self._current_position:
            self._current_position          = position
            self._last_position_change_time = time.monotonic()

    @staticmethod
    def _any_corner_above(state: dict, threshold: float) -> bool:
        """Returns True if any corner's tyre wear exceeds the given threshold.

        Parameters:
            state:     Current race state dict.
            threshold: Wear percentage threshold to check against.

        Returns:
            True if at least one corner is above threshold.
        """
        return (state["tyre_wear_fl"] > threshold
                or state["tyre_wear_fr"] > threshold
                or state["tyre_wear_rl"] > threshold
                or state["tyre_wear_rr"] > threshold)

    # --- Internal: briefing helpers -----------------------------------------

    @staticmethod
    def _find_car_at_position(all_cars: list, target_position: int) -> dict | None:
        """Returns the car dict at the given race position, or None.

        Parameters:
            all_cars:        List of car state dicts from the race state.
            target_position: 1-based race position to search for.

        Returns:
            Car dict if found, else None.
        """
        if target_position <= 0:
            return None
        for car in all_cars:
            if car.get("position") == target_position:
                return car
        return None

    @staticmethod
    def _wear_label(pct: float) -> str:
        """Returns a human-readable wear status label for a given wear percentage.

        Parameters:
            pct: Tyre wear percentage (0–100).

        Returns:
            One of 'good', 'managing', 'worn', 'critical', 'EMERGENCY'.
        """
        if pct < TYRE_WEAR_THRESHOLDS["manage"]:
            return "good"
        if pct < TYRE_WEAR_THRESHOLDS["warning"]:
            return "managing"
        if pct < TYRE_WEAR_THRESHOLDS["critical"]:
            return "worn"
        if pct < TYRE_WEAR_THRESHOLDS["emergency"]:
            return "critical"
        return "EMERGENCY"

    @staticmethod
    def _temp_label(temp: int, compound: str) -> str:
        """Returns a temperature status string for a single tyre corner.

        Parameters:
            temp:     Tyre surface temperature in degrees Celsius.
            compound: Tyre compound string used to look up optimal window.

        Returns:
            Status string: 'no data', 'below window (Xc, target Yc)',
            'above window — overheating (Xc)', or 'in window (Xc)'.
        """
        if temp == 0:
            return "no data"
        thresholds = TYRE_OPTIMAL_TEMPS.get(compound)
        if not thresholds:
            return f"{temp}°C"
        if temp < thresholds["min"]:
            return f"below window ({temp}°C, target {thresholds['optimal']}°C)"
        if temp > thresholds["max"]:
            return f"above window — overheating ({temp}°C)"
        return f"in window ({temp}°C)"

    @staticmethod
    def _infer_topic(text: str) -> str:
        """Infers a topic label from the engineer's transmission text.

        Used to populate the recent-topics block and gate the tyre cooldown.
        Keyword matching on lowercase text; first match wins.

        Parameters:
            text: Engineer's radio transmission string.

        Returns:
            Topic label string e.g. 'TYRES', 'GAP UPDATE', 'COACHING'.
        """
        lower_text = text.lower()
        if "box" in lower_text or "pit" in lower_text:
            return "PIT CALL"
        if "safety car" in lower_text or "vsc" in lower_text:
            return "SAFETY CAR"
        if "drs" in lower_text:
            return "DRS"
        if "ers" in lower_text or "energy" in lower_text or "harvest" in lower_text:
            return "ERS"
        if "tyre" in lower_text or "overheating" in lower_text or "front" in lower_text or "rear" in lower_text:
            return "TYRES"
        if "gap" in lower_text or "behind" in lower_text or "ahead" in lower_text or "seconds" in lower_text:
            return "GAP UPDATE"
        if "brake" in lower_text or "throttle" in lower_text or "apex" in lower_text or "turn" in lower_text:
            return "COACHING"
        if "programme" in lower_text:
            return "PROGRAMME_ANNOUNCEMENT"
        if "lap" in lower_text:
            return "PRACTICE"
        return "GENERAL"

    # --- Internal: practice briefing blocks ---------------------------------

    def _build_programme_header_lines(self, total_laps: int) -> list[str]:
        """Builds the active-programme or no-programme header lines for the SESSION block.

        Parameters:
            total_laps: Total laps in the session, used for programme recommendation fallback.

        Returns:
            List of formatted string lines.
        """
        lines = []
        if self._active_programme:
            prog = self._active_programme
            lines.append(
                f"Active programme: {prog['name']}  |  "
                f"Lap {self._programme_lap_count} of {prog['recommended_laps']}"
            )
            lines.append(f"Objective: {prog['objective']}")
            lines.append(f"Tyre recommendation: {prog['tyre_recommendation']}")
        else:
            recommended = get_recommended_programmes(total_laps or 20)
            if recommended:
                prog_data = get_programme_by_id(recommended[0])
                if prog_data:
                    lines.append(f"No programme active — recommended: {prog_data['name']}")
                    lines.append(f"Suggest: \"{prog_data['engineer_briefout']}\"")
        return lines

    def _build_garage_briefing_lines(self) -> list[str]:
        """Builds the GARAGE PRE-SESSION BRIEF lines when a garage briefing is pending.

        Parameters:
            None

        Returns:
            List of formatted string lines, empty if no garage briefing pending.
        """
        if not (self._garage_briefing_pending and self._active_programme):
            return []
        prog  = self._active_programme
        return [
            "=== GARAGE PRE-SESSION BRIEF ===",
            (f"Give the driver a pre-session briefing before they head out. "
             f"Programme: {prog['name']}. "
             f"Required laps: {prog['recommended_laps']}. "
             f"Tyres: {prog['tyre_recommendation']}. "
             f"Objective: {prog['objective']}."),
        ]

    @staticmethod
    def _sector_delta_str(actual: int, best: int) -> str:
        """Returns a formatted delta string when a sector was slower than the session best.

        Parameters:
            actual: Actual sector time in milliseconds for the last completed lap.
            best:   Session best sector time in milliseconds.

        Returns:
            Delta string like ' (+0.342s vs best)', or empty string if no delta.
        """
        if actual > 0 and best > 0 and actual > best:
            return f" (+{(actual - best) / 1000:.3f}s vs best)"
        return ""

    def _gather_debrief_sector_data(self, briefing: dict) -> dict:
        """Collects sector best times and last-lap actuals for the completion debrief.

        Reads sector actuals from the last completed lap in lap_history_summary
        rather than current_state, which holds in-progress (incomplete) values.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            Dict with keys: s1_best_ms, s2_best_ms, s3_best_ms, cur_s1, cur_s2, cur_s3.
        """
        state       = briefing["current_state"]
        lap_history = briefing.get("lap_history_summary", [])
        last_lap    = lap_history[-1] if lap_history else {}
        return {
            "s1_best_ms": briefing.get("session_best_s1", 0),
            "s2_best_ms": briefing.get("session_best_s2", 0),
            "s3_best_ms": briefing.get("session_best_s3", 0),
            "cur_s1": last_lap.get("sector1_time_ms", state.get("sector1_time_ms", 0)),
            "cur_s2": last_lap.get("sector2_time_ms", state.get("sector2_time_ms", 0)),
            "cur_s3": last_lap.get("sector3_time_ms", 0),
        }

    def _build_completion_debrief_lines(self, briefing: dict) -> list[str]:
        """Builds the PROGRAMME COMPLETE debrief lines with sector deltas and next programme.

        tyre_compound is the physical compound (C1-C6) used for temperature window lookups;
        visual_tyre_compound can differ at circuits where e.g. C3 is labelled Medium.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            List of formatted string lines, empty if no debrief needed.
        """
        if not (self._programme_complete and not self._programme_debrief_done
                and self._active_programme):
            return []

        prog     = self._active_programme
        state    = briefing["current_state"]
        compound = state.get("tyre_compound", "")
        sd       = self._gather_debrief_sector_data(briefing)

        s1_str = _format_lap_time(sd["s1_best_ms"]) if sd["s1_best_ms"] else "n/a"
        s2_str = _format_lap_time(sd["s2_best_ms"]) if sd["s2_best_ms"] else "n/a"
        s3_str = _format_lap_time(sd["s3_best_ms"]) if sd["s3_best_ms"] else "n/a"
        fl = self._temp_label(state.get("tyre_temp_fl", 0), compound)
        fr = self._temp_label(state.get("tyre_temp_fr", 0), compound)
        rl = self._temp_label(state.get("tyre_temp_rl", 0), compound)
        rr = self._temp_label(state.get("tyre_temp_rr", 0), compound)

        lines = [
            "=== PROGRAMME COMPLETE - BOX NOW ===",
            (f"{prog['name']} done, {self._programme_lap_count} laps. Box now. "
             f"Exactly two sentences: (1) which sector needs the most work - "
             f"S1 {s1_str}{self._sector_delta_str(sd['cur_s1'], sd['s1_best_ms'])}, "
             f"S2 {s2_str}{self._sector_delta_str(sd['cur_s2'], sd['s2_best_ms'])}, "
             f"S3 {s3_str}{self._sector_delta_str(sd['cur_s3'], sd['s3_best_ms'])}; "
             f"(2) one specific instruction for the next run - "
             f"tyres: FL {fl}, FR {fr}, RL {rl}, RR {rr}."),
        ]
        lines += self._build_next_programme_lines(prog, state.get("total_laps", 0) or 20)
        return lines

    def _build_next_programme_lines(self, current_prog: dict,
                                    total_sess_laps: int) -> list[str]:
        """Builds the NEXT PROGRAMME or SESSION COMPLETE follow-up lines.

        Parameters:
            current_prog:   The programme that just completed.
            total_sess_laps: Total session laps for programme list lookup.

        Returns:
            List of one formatted string line.
        """
        recommended_ids = get_recommended_programmes(total_sess_laps)
        try:
            current_idx = recommended_ids.index(current_prog["id"])
            next_id     = (recommended_ids[current_idx + 1]
                           if current_idx + 1 < len(recommended_ids) else None)
        except ValueError:
            next_id = None

        if next_id:
            next_prog = get_programme_by_id(next_id)
            if next_prog:
                return [
                    f"NEXT PROGRAMME: {next_prog['name']} - "
                    f"{next_prog['recommended_laps']} laps on {next_prog['tyre_recommendation']}. "
                    f"Tell the driver what to prepare for on the next run out."
                ]
        return [
            "SESSION COMPLETE: All recommended programmes finished. "
            "Tell the driver session data collection is complete."
        ]

    def _build_session_stats_line(self) -> list[str]:
        """Builds the session statistics summary line from the data store.

        Parameters:
            None

        Returns:
            List of one formatted string line, or empty list if no data.
        """
        summary = self._get_session_summary()
        if not summary or summary.get("laps_completed", 0) == 0:
            return []
        laps_done = summary["laps_completed"]
        best_ms   = summary.get("best_lap_time_ms", 0)
        avg_ms    = summary.get("average_lap_time_ms", 0)
        std_ms    = summary.get("lap_time_std_dev_ms", 0.0)
        return [
            f"Session stats: {laps_done} laps  |  "
            f"best {_format_lap_time(best_ms) if best_ms else 'n/a'}  |  "
            f"avg {_format_lap_time(avg_ms) if avg_ms else 'n/a'}  |  "
            f"consistency ±{std_ms:.0f}ms"
        ]

    def _format_practice_session_block(self, briefing: dict) -> str:
        """Builds the SESSION block for practice mode.

        Delegates to focused helper methods for each sub-section to keep
        this method under 20 lines. Logic order: header, programme status,
        garage brief, completion debrief, pit debrief, session stats.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            Formatted SESSION block string.
        """
        state = briefing["current_state"]
        lines = [
            "=== SESSION ===",
            f"Mode: PRACTICE  |  {state['session_type']}  |  {state['track_name']}",
            f"Lap {state['current_lap']} / {state['total_laps']}",
        ]
        lines += self._build_programme_header_lines(state["total_laps"])
        lines += self._build_garage_briefing_lines()
        lines += self._build_completion_debrief_lines(briefing)
        if self._practice_debrief_pending and self._active_programme:
            lines.append(f"DEBRIEF PENDING: {self._active_programme['engineer_debrief']}")
        lines += self._build_session_stats_line()
        return "\n".join(lines)

    def _get_session_summary(self) -> dict | None:
        """Returns session summary from the attached data store, or None.

        Parameters:
            None

        Returns:
            Session summary dict from the data store, or None if no store attached.
        """
        if self._session_data_store is not None:
            return self._session_data_store.get_session_summary()
        return None

    def _format_track_position_block(self, briefing: dict) -> str:
        """Builds the TRACK POSITION block for practice coaching context.

        Includes a Car status line so Gemini receives the correct situation
        description instead of inferring stationarity from speed alone.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            Formatted TRACK POSITION block string.
        """
        state      = briefing["current_state"]
        pit_status = state.get("pit_status", PIT_STATUS_ON_TRACK)
        speed      = state.get("speed_kmh", 0)

        if pit_status == PIT_STATUS_PIT_LANE and speed >= GARAGE_SPEED_THRESHOLD_KMH:
            car_status = "IN PIT LANE — normal pit entry, do not describe as stationary"
        elif pit_status == PIT_STATUS_PIT_LANE and speed < GARAGE_SPEED_THRESHOLD_KMH:
            car_status = "IN GARAGE — pre-session or between runs"
        elif speed < GARAGE_SPEED_THRESHOLD_KMH:
            car_status = "STATIONARY ON TRACK — car has stopped on circuit"
        else:
            car_status = "ON TRACK"

        lines = [
            "=== TRACK POSITION ===",
            f"Car status: {car_status}",
            (f"Sector {state.get('sector', 1)}  |  "
             f"Lap distance: {state.get('lap_distance_m', 0):.0f}m"),
            (f"Speed: {speed} km/h  |  "
             f"Gear: {state['gear']}  |  "
             f"Throttle: {state['throttle_pct']:.0f}%  |  "
             f"Brake: {state['brake_pct']:.0f}%"),
        ]
        return "\n".join(lines)

    def _format_practice_traffic_block(self, briefing: dict) -> str:
        """Builds the TRAFFIC block for practice mode using on-track proximity data.

        Uses track_car_behind / track_car_ahead from the briefing (physical circuit
        position) rather than classification-order gaps. Compares the car-behind gap
        against the last-transmission baseline to flag closing situations.

        Parameters:
            briefing: Full engineer briefing dict, must contain optional
                      'track_car_behind' and 'track_car_ahead' top-level keys.

        Returns:
            Formatted TRAFFIC block string, or empty string if no cars in range.
        """
        lines = ["=== TRAFFIC ==="]

        track_behind = briefing.get("track_car_behind")
        if track_behind and track_behind["gap_ms"] <= APPROACHING_CAR_REPORT_THRESHOLD_MS:
            name       = track_behind["name"]
            gap_ms     = track_behind["gap_ms"]
            gap_s      = gap_ms / 1000.0
            gap_closed = (self._last_behind_gap_ms > 0
                          and (self._last_behind_gap_ms - gap_ms) >= CLOSING_GAP_THRESHOLD_MS)
            if gap_ms <= APPROACHING_CAR_WARNING_2_MS:
                lines.append(f"FINAL CALL: {name} behind, {gap_s:.1f}s — imminent pass")
            elif gap_ms <= APPROACHING_CAR_WARNING_1_MS:
                label = "CLOSING" if gap_closed else "approaching"
                lines.append(f"WARNING: {name} behind, {gap_s:.1f}s — {label}")
            elif gap_closed:
                lines.append(f"CLOSING: {name} behind, {gap_s:.1f}s — gap reducing")
            else:
                lines.append(f"Car behind: {name}, {gap_s:.1f}s")

        track_ahead = briefing.get("track_car_ahead")
        if track_ahead and track_ahead["gap_ms"] <= APPROACHING_CAR_REPORT_THRESHOLD_MS:
            gap_s = track_ahead["gap_ms"] / 1000.0
            lines.append(f"Car ahead: {track_ahead['name']}, {gap_s:.1f}s")

        # Return empty string when no cars are within the reporting threshold —
        # filter(None, blocks) will omit this block from the prompt entirely.
        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    def _qual_behind_line(self) -> str:
        """Returns the traffic status line for the car behind in qualifying.

        Parameters:
            None

        Returns:
            Formatted string describing the car behind's gap and threat level.
        """
        behind_gap    = self._nearby_cars["behind"].get("gap")
        behind_driver = self._nearby_cars["behind"].get("driver") or "unknown"
        if behind_gap is None:
            return "No car behind within range."
        if behind_gap < 5.0:
            return f"WARNING: {behind_driver} behind, {behind_gap:.1f}s — let through"
        if behind_gap < 15.0:
            return f"Car behind: {behind_driver}, {behind_gap:.1f}s, closing"
        return f"Car behind: {behind_driver}, {behind_gap:.1f}s, no threat"

    def _qual_ahead_line(self) -> str:
        """Returns the traffic status line for the car ahead in qualifying.

        Parameters:
            None

        Returns:
            Formatted string describing the car ahead's gap and push lap risk.
        """
        ahead_gap    = self._nearby_cars["ahead"].get("gap")
        ahead_driver = self._nearby_cars["ahead"].get("driver") or "unknown"
        if ahead_gap is None:
            return "Track clear ahead."
        if ahead_gap < 5.0:
            return f"Car ahead: {ahead_driver}, {ahead_gap:.1f}s — may affect push lap"
        return f"Car ahead: {ahead_driver}, {ahead_gap:.1f}s, safe"

    def _format_qualifying_traffic_block(self) -> str:
        """Builds the TRAFFIC block for qualifying — all cars within 20 seconds.

        Parameters:
            None

        Returns:
            Formatted TRAFFIC block string.
        """
        lap_type = "push lap (flying)" if self._is_flying_lap else "out lap / cool-down"
        lines = [
            "=== TRAFFIC ===",
            f"Lap type: {lap_type}",
            self._qual_behind_line(),
            self._qual_ahead_line(),
        ]
        return "\n".join(lines)

    def _format_personal_best_block(self, briefing: dict) -> str:
        """Builds the PERSONAL BEST block for qualifying mode.

        Includes session sector bests, personal best lap time, and delta
        to the circuit qualifying target when available.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            Formatted PERSONAL BEST block string.
        """
        state       = briefing["current_state"]
        session_s1    = briefing.get("session_best_s1", 0)
        session_s2    = briefing.get("session_best_s2", 0)
        session_s3    = briefing.get("session_best_s3", 0)
        reference_lap = briefing.get("reference_lap")

        lines = ["=== PERSONAL BEST ==="]

        if session_s1 > 0:
            lines.append(
                f"Session bests  —  "
                f"S1: {_format_lap_time(session_s1)}  |  "
                f"S2: {_format_lap_time(session_s2)}  |  "
                f"S3: {_format_lap_time(session_s3)}"
            )
        else:
            lines.append("No sector bests set yet.")

        if reference_lap and reference_lap.get("has_personal_best"):
            personal_best = reference_lap["personal_best_ms"]
            lines.append(f"Personal best: {_format_lap_time(personal_best)}")
            target_line = self._build_qualifying_target_line(personal_best)
            if target_line:
                lines.append(target_line)

        return "\n".join(lines)

    def _build_qualifying_target_line(self, personal_best_ms: int) -> str:
        """Returns the target/delta line comparing personal best to circuit qualifying target.

        Parameters:
            personal_best_ms: Driver's personal best lap time in milliseconds.

        Returns:
            Formatted target/delta string, or empty string if no circuit target available.
        """
        if not self._circuit_reference:
            return ""
        q_target = self._circuit_reference.get("qualifying_target_ms", 0)
        if q_target <= 0:
            return ""
        delta_ms = personal_best_ms - q_target
        sign     = "+" if delta_ms >= 0 else "-"
        return (f"Target: {_format_lap_time(q_target)}  |  "
                f"Delta: {sign}{abs(delta_ms / 1000):.3f}s")

    def _format_circuit_reference_block(self, briefing: dict,
                                         session_key: str) -> str:
        """Builds the CIRCUIT REFERENCE block with corner coaching notes.

        Parameters:
            briefing:    Full engineer briefing dict.
            session_key: 'qualifying' or 'race' — selects which note set to use.

        Returns:
            Formatted CIRCUIT REFERENCE block string, or empty string if not available.
        """
        if not self._circuit_reference:
            return ""

        corners = self._circuit_reference.get(session_key, {})
        if not corners:
            return ""

        mode_label = "QUALIFYING" if session_key == "qualifying" else "RACE MANAGEMENT"
        lines      = [f"=== CIRCUIT REFERENCE — {mode_label} ==="]

        for turn_num, corner in sorted(corners.items()):
            board = corner.get("board", "")
            gear  = corner.get("gear", 0)
            note  = corner.get("note", "")
            gear_str = f"  gear {gear}" if gear > 0 else ""
            board_str = f"  {board} board" if board and board != "0m" else ""
            lines.append(f"  Turn {turn_num}{board_str}{gear_str}: {note}")

        return "\n".join(lines)

    # --- Internal: shared briefing blocks -----------------------------------

    def _format_situation_block(self, briefing: dict,
                                 trigger: dict | None) -> str:
        """Builds the SITUATION header block for qualifying and race modes.

        Parameters:
            briefing: Full engineer briefing dict.
            trigger:  Critical event dict if one fired this cycle, else None.

        Returns:
            Formatted SITUATION block string.
        """
        state = briefing["current_state"]
        mode  = self._session_mode().upper()
        lines = ["=== SITUATION ===", f"Mode: {mode}"]

        if self._is_qualifying():
            lap_type = "push lap (flying)" if self._is_flying_lap else "out lap / cool-down"
            lines.append(f"Lap type: {lap_type}")

        if trigger:
            lines.append(f"Trigger: {trigger['type']} — {trigger.get('detail', '')}")
        else:
            lines.append("Trigger: routine update")

        return "\n".join(lines)

    def _build_ahead_car_line(self, state: dict) -> str:
        """Builds the 'Car ahead' line for the race situation block.

        Parameters:
            state: Current race state dict.

        Returns:
            Formatted car-ahead string.
        """
        position     = state["position"]
        all_cars     = state.get("all_cars", [])
        gap_ahead_s  = state.get("gap_to_ahead_ms", 0) / 1000.0
        if position <= 1:
            return "Car ahead:  none — leading the race"
        ahead_car    = self._find_car_at_position(all_cars, position - 1)
        driver_ahead = (self._nearby_cars["ahead"].get("driver")
                        or (ahead_car.get("name") if ahead_car else None) or "unknown")
        previous_gap = self._nearby_cars["ahead"]["prev_gap"]
        current_gap  = self._nearby_cars["ahead"]["gap"]
        trend = ""
        if (current_gap is not None and previous_gap is not None
                and abs(current_gap - previous_gap) >= GAP_TREND_MIN_CHANGE_S):
            trend = f", {'closing' if current_gap < previous_gap else 'pulling away'}"
        pitted = (" [in/exiting pits]"
                  if ahead_car and ahead_car.get("pit_status", 0) in (1, 2, 3) else "")
        gap_text = f"{gap_ahead_s:.1f}s" if gap_ahead_s > 0 else "unknown"
        return f"Car ahead:  {driver_ahead}{pitted}, gap {gap_text}{trend}"

    def _build_behind_car_line(self, state: dict) -> str:
        """Builds the 'Car behind' line for the race situation block.

        Parameters:
            state: Current race state dict.

        Returns:
            Formatted car-behind string.
        """
        position  = state["position"]
        all_cars  = state.get("all_cars", [])
        behind_car = self._find_car_at_position(all_cars, position + 1)
        if not behind_car:
            return "Car behind: none"
        driver_behind = (self._nearby_cars["behind"].get("driver")
                         or behind_car.get("name") or "unknown")
        drs_threat = "DRS THREAT" if behind_car.get("drs_allowed") else "no DRS threat"
        return f"Car behind: {driver_behind}, {drs_threat}"

    def _format_race_situation_block(self, briefing: dict) -> str:
        """Builds the RACE SITUATION block with lap, position, and gap data.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            Formatted RACE SITUATION block string.
        """
        state          = briefing["current_state"]
        current_lap    = state["current_lap"]
        total_laps     = state["total_laps"]
        position       = state["position"]
        all_cars       = state.get("all_cars", [])
        laps_remaining = max(0, total_laps - current_lap)
        gap_ahead_s    = state.get("gap_to_ahead_ms", 0) / 1000.0
        behind_car     = self._find_car_at_position(all_cars, position + 1)

        lines = [
            "=== RACE SITUATION ===",
            (f"Lap {current_lap} / {total_laps}  |  "
             f"P{position}  |  {laps_remaining} lap(s) remaining"),
            f"Track: {state['track_name']}  |  Session: {state['session_type']}",
        ]
        sc_status = state.get("safety_car_status", 0)
        if sc_status:
            lines.append(f"SAFETY CAR: {_SAFETY_CAR_LABELS.get(sc_status, str(sc_status))}")
        lines.append(self._build_ahead_car_line(state))
        lines.append(self._build_behind_car_line(state))
        gap_leader_s = state.get("gap_to_leader_ms", 0) / 1000.0
        if position > 1 and gap_leader_s > 0:
            lines.append(f"Gap to leader: {gap_leader_s:.1f}s")
        no_drs_behind = not behind_car or not behind_car.get("drs_allowed")
        free_air = gap_ahead_s > FREE_AIR_AHEAD_THRESHOLD_S and no_drs_behind
        lines.append(f"Free air: {'YES — push at full pace' if free_air else 'NO — traffic present'}")
        return "\n".join(lines)

    @staticmethod
    def _tyre_overall_assessment(corners: dict) -> str:
        """Returns a one-sentence overall tyre assessment based on worst-corner wear.

        Parameters:
            corners: Dict mapping corner name to (wear_pct, temp) tuples.

        Returns:
            Assessment string describing the worst-corner wear state.
        """
        worst_name, (worst_wear, _) = max(corners.items(), key=lambda x: x[1][0])
        if worst_wear >= TYRE_WEAR_THRESHOLDS["emergency"]:
            return f"Tyres at emergency — {worst_name} needs immediate box."
        if worst_wear >= TYRE_WEAR_THRESHOLDS["critical"]:
            return f"Tyres critical — {worst_name} is heavily worn, box very soon."
        if worst_wear >= TYRE_WEAR_THRESHOLDS["warning"]:
            return f"Tyres degrading — {worst_name} shows performance drop."
        if worst_wear >= TYRE_WEAR_THRESHOLDS["manage"]:
            return f"Tyres managing — monitor {worst_name}."
        return "Tyres in good condition."

    def _format_tyre_block(self, briefing: dict) -> str:
        """Builds the TYRES block with wear, temperature, and overall assessment.

        Appends a SUPPRESSED flag when tyre temperature is within cooldown and
        the status labels have not changed, telling Gemini not to repeat it.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            Formatted TYRES block string.
        """
        state    = briefing["current_state"]
        compound = state["tyre_compound"]
        corners  = {
            "Front Left":  (state["tyre_wear_fl"], state["tyre_temp_fl"]),
            "Front Right": (state["tyre_wear_fr"], state["tyre_temp_fr"]),
            "Rear Left":   (state["tyre_wear_rl"], state["tyre_temp_rl"]),
            "Rear Right":  (state["tyre_wear_rr"], state["tyre_temp_rr"]),
        }
        lines = [
            "=== TYRES ===",
            f"Compound: {compound}  |  Age: {state['tyre_age_laps']} laps",
        ]
        for name, (wear, temp) in corners.items():
            lines.append(f"  {name:<12}: {self._wear_label(wear):9}  {wear:.1f}%  |  "
                         f"{self._temp_label(temp, compound)}")
        lines.append(f"Overall: {self._tyre_overall_assessment(corners)}")
        within_cooldown = (self._tyre_transmissions_since_mention
                           < TYRE_TOPIC_COOLDOWN_TRANSMISSIONS)
        if within_cooldown and not self._tyre_status_changed(briefing):
            lines.append(
                "SUPPRESSED: Tyre temperatures unchanged since last mention — "
                f"do not repeat for {TYRE_TOPIC_COOLDOWN_TRANSMISSIONS} transmissions."
            )
        return "\n".join(lines)

    def _capture_tyre_status(self, briefing: dict) -> dict:
        """Captures current per-corner tyre status labels for change detection.

        Parameters:
            briefing: Current engineer briefing dict.

        Returns:
            Dict mapping corner code ('fl','fr','rl','rr') to status label string.
        """
        state    = briefing["current_state"]
        compound = state.get("tyre_compound", "")
        return {
            "fl": self._temp_label(state.get("tyre_temp_fl", 0), compound),
            "fr": self._temp_label(state.get("tyre_temp_fr", 0), compound),
            "rl": self._temp_label(state.get("tyre_temp_rl", 0), compound),
            "rr": self._temp_label(state.get("tyre_temp_rr", 0), compound),
        }

    def _tyre_status_changed(self, briefing: dict) -> bool:
        """Returns True if any corner's tyre status label differs from the last mention.

        Used to override the tyre temperature cooldown when actual thermal status
        has changed, so a genuine transition (cold → in window, etc.) is always
        reported regardless of how recently tyres were last mentioned.

        Parameters:
            briefing: Current engineer briefing dict.

        Returns:
            True if any corner label changed; False if no stored baseline or unchanged.
        """
        if not self._last_tyre_status:
            return False
        return self._capture_tyre_status(briefing) != self._last_tyre_status

    @staticmethod
    def _build_pit_window_line(state: dict, briefing: dict) -> str:
        """Returns a single pit window status string for the strategy block.

        Parameters:
            state:    Current race state dict.
            briefing: Full engineer briefing dict (for pit_window_estimate_laps fallback).

        Returns:
            One-line pit window status string.
        """
        current_lap = state["current_lap"]
        pit_ideal   = state.get("pit_window_ideal", 0)
        pit_latest  = state.get("pit_window_latest", 0)
        if pit_ideal > 0:
            laps_to_ideal = pit_ideal - current_lap
            if laps_to_ideal > 0:
                return (f"Pit window: ideal lap {pit_ideal} (in {laps_to_ideal} lap(s)), "
                        f"latest lap {pit_latest}")
            if pit_latest >= current_lap:
                return (f"In pit window now — ideal was lap {pit_ideal}, "
                        f"latest lap {pit_latest}")
            return f"Past pit window (ideal {pit_ideal}, latest {pit_latest})"
        pit_estimate = briefing.get("pit_window_estimate_laps")
        if pit_estimate is not None:
            return f"Estimated laps to pit: ~{pit_estimate}"
        return "Pit window: not yet calculated"

    def _format_strategy_block(self, briefing: dict) -> str:
        """Builds the STRATEGY block with pit window, rejoin position, and ERS/fuel.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            Formatted STRATEGY block string.
        """
        state             = briefing["current_state"]
        rejoin_position   = state.get("pit_rejoin_position", 0)
        safety_car_active = bool(state.get("safety_car_status", 0))
        lines             = ["=== STRATEGY ===", self._build_pit_window_line(state, briefing)]
        if rejoin_position > 0:
            lines.append(f"Predicted rejoin position: P{rejoin_position}")
        if safety_car_active:
            lines.append("SAFETY CAR ACTIVE — pit now to gain time")
        lines.append(f"ERS: {state['ers_store_pct']:.0f}%  |  "
                     f"Fuel: {state['fuel_remaining_laps']:.1f} laps")
        return "\n".join(lines)

    def _format_recent_topics_block(self) -> str:
        """Builds the RECENT TRANSMISSION TOPICS block to suppress repetition.

        Parameters:
            None

        Returns:
            Formatted recent topics block string, or empty string if no history.
        """
        if not self._recent_topics:
            return ""
        lines = ["=== RECENT TRANSMISSION TOPICS (avoid repeating) ==="]
        for topic in self._recent_topics:
            lines.append(f"  {topic}")
        return "\n".join(lines)

    def _format_recent_events_block(self, briefing: dict) -> str:
        """Builds the RECENT EVENTS block listing overtakes and critical events.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            Formatted RECENT EVENTS block string.
        """
        events = briefing["recent_events"]
        lines  = ["=== RECENT EVENTS ==="]
        if not events:
            lines.append("None.")
        else:
            for event in events:
                lines.append(
                    f"[{event['timestamp']}]  {event['type']}: {event['detail']}"
                )
        return "\n".join(lines)

    @staticmethod
    def _format_sector_time(ms: int) -> str:
        """Formats a sector time in milliseconds for tabular display.

        Parameters:
            ms: Sector time in milliseconds. Zero means no data.

        Returns:
            Formatted time string (e.g. '26.420') or '  ---.---' when no data.
        """
        return _format_lap_time(ms) if ms > 0 else "  ---.---"

    def _format_lap_history_block(self, briefing: dict) -> str:
        """Builds the LAST 5 LAPS table block for race mode.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            Formatted string with lap times, sector splits, and positions.
        """
        history = briefing["lap_history_summary"]
        lines   = ["=== LAST 5 LAPS ==="]
        if not history:
            lines.append("No completed laps yet.")
            return "\n".join(lines)
        lines.append("Lap   Time        S1          S2          S3         Pos")
        for lap in reversed(history):
            lines.append(
                f"{lap['lap_number']:>3}   "
                f"{_format_lap_time(lap['lap_time_ms']):>9}   "
                f"{self._format_sector_time(lap.get('sector1_time_ms', 0)):>9}   "
                f"{self._format_sector_time(lap.get('sector2_time_ms', 0)):>9}   "
                f"{self._format_sector_time(lap.get('sector3_time_ms', 0)):>9}   "
                f"P{lap['position_at_end']}"
            )
        return "\n".join(lines)

    def _format_track_knowledge_block(self, briefing: dict) -> str:
        """Returns track knowledge + F1 knowledge on first call only.

        After the first successful call this method returns an empty string so
        the ~3 000-token knowledge block is not repeated on every subsequent
        briefing, saving significant token cost.

        Resets automatically when the track or session type changes
        (handled in _load_session_resources).

        Parameters:
            briefing: Full engineer briefing dict, used to read track_name.

        Returns:
            Combined track brief and F1_KNOWLEDGE string on first call; empty string thereafter.
        """
        if self._track_knowledge_sent:
            return ""

        track_name    = briefing["current_state"].get("track_name", "")
        track_section = track_mapper.get_engineer_track_brief(track_name)

        if not track_section:
            return ""

        self._track_knowledge_sent = True
        return f"{track_section}\n\n=== F1 KNOWLEDGE (one-time reference) ===\n{F1_KNOWLEDGE}"

    def _format_reference_block(self, briefing: dict) -> str:
        """Builds the REFERENCE LAP block with personal best and coaching notes.

        Parameters:
            briefing: Full engineer briefing dict.

        Returns:
            Formatted REFERENCE LAP block string, or empty string if no data.
        """
        reference_lap = briefing.get("reference_lap")
        if not reference_lap:
            return ""

        lines    = ["=== REFERENCE LAP ==="]
        has_data = False

        if reference_lap.get("has_personal_best"):
            has_data = True
            lines.append(f"Personal best:  {_format_lap_time(reference_lap['personal_best_ms'])}")
        if reference_lap.get("has_ai_best"):
            has_data = True
            lines.append(f"AI reference:   {_format_lap_time(reference_lap['ai_best_ms'])}")
        if reference_lap.get("has_qualifying_best"):
            has_data = True
            lines.append(f"Qualifying PB:  {_format_lap_time(reference_lap['qualifying_best_ms'])}")

        coaching = reference_lap.get("coaching_note", "")
        if coaching:
            has_data = True
            lines.append(f"Coaching note:  {coaching}")

        return "\n".join(lines) if has_data else ""

    # --- Internal: Vertex AI (Gemini via google.genai vertexai=True) ----------

    def _call_gemini(self):
        """Sends the current conversation history to Gemini and returns the response.

        Parameters:
            None

        Returns:
            Gemini GenerateContentResponse object with .text and .usage_metadata.
        """
        return self._client.models.generate_content(
            model=GEMINI_MODEL,
            contents=self.conversation_history,
            config=types.GenerateContentConfig(
                system_instruction=ENGINEER_SYSTEM_PROMPT,
                max_output_tokens=MAX_RESPONSE_TOKENS,
                temperature=GEMINI_TEMPERATURE,
            ),
        )

    def _append_user_message(self, text: str) -> None:
        """Appends a user-role message to the conversation history.

        Parameters:
            text: The briefing text to append.

        Returns:
            None
        """
        self.conversation_history.append(
            {"role": "user", "parts": [{"text": text}]}
        )

    def _append_assistant_message(self, text: str) -> None:
        """Appends a model-role message to the conversation history.

        Parameters:
            text: The engineer's response text to append.

        Returns:
            None
        """
        self.conversation_history.append(
            {"role": "model", "parts": [{"text": text}]}
        )

    def _trim_history(self) -> None:
        """Trims conversation history to MAX_HISTORY_MESSAGES, keeping user-first order.

        Parameters:
            None

        Returns:
            None
        """
        if len(self.conversation_history) > MAX_HISTORY_MESSAGES:
            trimmed = self.conversation_history[-MAX_HISTORY_MESSAGES:]
            while trimmed and trimmed[0]["role"] != "user":
                trimmed = trimmed[1:]
            self.conversation_history = trimmed

    def _mark_events_handled(self, briefing: dict,
                              trigger: dict | None) -> None:
        """Marks all recent events and the critical trigger as handled.

        Parameters:
            briefing: Full engineer briefing dict.
            trigger:  Critical event dict if one fired this cycle, else None.

        Returns:
            None
        """
        for event in briefing["recent_events"]:
            self._handled_event_signatures.add(self._event_signature(event))
        if trigger and "sig" in trigger:
            self._handled_event_signatures.add(trigger["sig"])

    def _event_signature(self, event: dict) -> str:
        """Returns a unique deduplication key for a recent event.

        Parameters:
            event: Event dict with 'timestamp' and 'type' keys.

        Returns:
            Signature string in the form 'timestamp_TYPE'.
        """
        return f"{event['timestamp']}_{event['type']}"

    def _time_since_last_response(self) -> float:
        """Returns elapsed seconds since the last Gemini response was transmitted.

        Parameters:
            None

        Returns:
            Seconds as float.
        """
        return time.monotonic() - self._last_response_time


# ---------------------------------------------------------------------------
# Gemini integration test
# Run: venv\Scripts\python.exe src\engineer.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    def _fake_briefing() -> dict:
        def _car(position: int, name: str, drs_allowed: bool = False) -> dict:
            return {
                "position": position, "lap": 15, "pit_status": 0, "pit_stops": 1,
                "last_lap_ms": 85_100, "driver_status": 1,
                "delta_to_car_in_front_ms": 0, "name": name, "team_id": 0,
                "speed_kmh": 285, "ers_store_pct": 62.0, "ers_deploy_mode": 0,
                "drs_allowed": drs_allowed, "drs_activation_distance": 0,
            }

        def _blank_car() -> dict:
            return {
                "position": 0, "lap": 0, "pit_status": 0, "pit_stops": 0,
                "last_lap_ms": 0, "driver_status": 0,
                "delta_to_car_in_front_ms": 0, "name": "", "team_id": 0,
                "speed_kmh": 0, "ers_store_pct": 0.0, "ers_deploy_mode": 0,
                "drs_allowed": False, "drs_activation_distance": 0,
            }

        all_cars = [_blank_car() for _ in range(22)]
        all_cars[0] = _car(1, "Verstappen")
        all_cars[1] = _car(2, "Leclerc")
        all_cars[2] = _car(3, "Hamilton")
        all_cars[3] = _car(4, "Norris", drs_allowed=True)
        for i, name in enumerate(
            ["Piastri", "Russell", "Sainz", "Alonso", "Perez", "Hulkenberg",
             "Stroll", "Albon", "Tsunoda", "Gasly", "Ocon", "Colapinto",
             "Lawson", "Bearman", "Hadjar", "Doohan", "Bortoleto"],
            start=4,
        ):
            all_cars[i] = _car(i + 1, name)

        current_state = {
            "speed_kmh":           287,
            "throttle_pct":        98.0,
            "brake_pct":           0.0,
            "gear":                8,
            "engine_rpm":          11_250,
            "drs_active":          True,
            "tyre_temp_fl":        95,
            "tyre_temp_fr":        97,
            "tyre_temp_rl":        92,
            "tyre_temp_rr":        93,
            "current_lap":         15,
            "lap_time_ms":         0,
            "sector":              2,
            "sector1_time_ms":     0,
            "sector2_time_ms":     0,
            "position":            3,
            "pit_status":          0,
            "lap_invalid":         False,
            "gap_to_ahead_ms":     1400,
            "gap_to_leader_ms":    3200,
            "fuel_remaining_laps": 8.2,
            "tyre_compound":       "Medium",
            "tyre_age_laps":       15,
            "drs_allowed":         True,
            "ers_store_pct":       65.0,
            "ers_deploy_mode":     0,
            "tyre_wear_fl":        42.1,
            "tyre_wear_fr":        45.3,
            "tyre_wear_rl":        38.7,
            "tyre_wear_rr":        40.9,
            "track_name":          "Monza",
            "session_type":        "Race",
            "total_laps":          57,
            "track_temp_c":        38,
            "air_temp_c":          29,
            "weather":             0,
            "safety_car_status":   0,
            "pit_window_ideal":    20,
            "pit_window_latest":   25,
            "pit_rejoin_position": 4,
            "weather_forecast":    [],
            "sector2_lap_dist_m":  0.0,
            "sector3_lap_dist_m":  0.0,
            "car_x":               0.0,
            "car_z":               0.0,
            "lap_distance_m":      0.0,
            "all_cars":            all_cars,
        }

        lap_history = [
            {
                "lap_number": 12, "position_at_end": 4, "lap_time_ms": 85_180,
                "sector1_time_ms": 26_420, "sector2_time_ms": 31_850,
                "sector3_time_ms": 26_910,
                "tyre_wear_front_left": 28.3, "tyre_wear_front_right": 30.1,
                "tyre_wear_rear_left":  25.4, "tyre_wear_rear_right":  26.8,
                "average_front_axle_wear": 29.2, "average_rear_axle_wear": 26.1,
            },
            {
                "lap_number": 13, "position_at_end": 4, "lap_time_ms": 85_350,
                "sector1_time_ms": 26_510, "sector2_time_ms": 31_920,
                "sector3_time_ms": 26_920,
                "tyre_wear_front_left": 33.6, "tyre_wear_front_right": 35.8,
                "tyre_wear_rear_left":  30.1, "tyre_wear_rear_right":  31.5,
                "average_front_axle_wear": 34.7, "average_rear_axle_wear": 30.8,
            },
            {
                "lap_number": 14, "position_at_end": 3, "lap_time_ms": 85_290,
                "sector1_time_ms": 26_480, "sector2_time_ms": 31_870,
                "sector3_time_ms": 26_940,
                "tyre_wear_front_left": 38.4, "tyre_wear_front_right": 41.2,
                "tyre_wear_rear_left":  34.9, "tyre_wear_rear_right":  36.7,
                "average_front_axle_wear": 39.8, "average_rear_axle_wear": 35.8,
            },
        ]

        return {
            "current_state":              current_state,
            "stint_length":               15,
            "pace_trend_ms":              110,
            "tyre_wear_rate_pct_per_lap": 2.8,
            "pit_window_estimate_laps":   5,
            "recent_events": [
                {
                    "type": "OVERTAKE", "detail": "Position gained: P4 -> P3",
                    "lap": 14, "timestamp": "14:32:11",
                },
                {
                    "type": "NEW_LAP", "detail": "Lap 15 started (P3)",
                    "lap": 15, "timestamp": "14:33:02",
                },
            ],
            "lap_history_summary": lap_history,
            "session_best_s1":  26_210,
            "session_best_s2":  31_540,
            "session_best_s3":  26_780,
            "reference_lap": {
                "has_personal_best":   True,
                "personal_best_ms":    84_920,
                "has_ai_best":         True,
                "ai_best_ms":          84_650,
                "has_qualifying_best": False,
                "qualifying_best_ms":  0,
                "coaching_note": (
                    "Losing ~0.3s in sector 2 — later throttle through "
                    "the chicane at Turn 4."
                ),
            },
        }

    print(DISPLAY_SEPARATOR)
    print("  Gemini test — fake race briefing, Monza lap 15 / 57, P3")
    print(DISPLAY_SEPARATOR)

    engineer = EngineerAI()
    briefing = _fake_briefing()
    print("Calling Gemini...", end=" ", flush=True)
    response = engineer.get_engineer_response(briefing)
    print("done.\n")
    print(f"ENGINEER: {response}")
    print(DISPLAY_SEPARATOR)
