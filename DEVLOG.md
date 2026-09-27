# F1 Engineer — Development Log

## Project Overview

A real-time AI race engineer that connects to F1 25 UDP telemetry broadcast by a PS5 (source IP 192.168.1.39, port 20777) and provides live coaching, strategy calls, and gap information via a browser dashboard. The system ingests 60 Hz telemetry, maintains a full lap history and event log, then drives Gemini 2.5 Flash via Google Cloud Vertex AI to generate authentic F1 radio transmissions in session-appropriate modes (practice, qualifying, race). A WebSocket server pushes a 30 Hz JSON snapshot to a single-file HTML dashboard that displays speed, tyre wear and temperature, sector times, lap history, the gaps panel, pit window, safety car status, and a live GPS track map with the car's position and sector colouring.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Telemetry source | F1 25 (PS5) — UDP broadcast at 60 Hz, port 20777 |
| UDP packet decoding | `f1-packets` library (`from f1 import packets`) |
| Backend runtime | Python 3.12, asyncio |
| AI model | `gemini-2.5-flash` via `google-genai==2.3.0`, Vertex AI (`vertexai=True`) |
| Credentials | Google Cloud ADC (`gcloud auth application-default login`) + `.env` |
| WebSocket server | `websockets` library, port 8765 |
| Dashboard | Vanilla HTML/CSS/JS (`dashboard/index.html`), no build step |
| Session persistence | JSON files written to `data/sessions/` per session |
| Track shapes | JSON files written to `data/tracks/` — one per circuit |
| Env management | `python-dotenv` |
| Virtual environment | `venv\Scripts\python.exe` |

---

## Session Log

---

### ~2026-05-14 — Phase 0: Project Setup

**Worked on:** Created the project directory and virtual environment. Installed core dependencies including `f1-packets`, `google-genai`, `websockets`, and `python-dotenv`. Set up `.env` file with GCP project, region, and API keys.

**Tested:** Import of `f1-packets`. Discovered that the package installs under the `f1` namespace, not `f1_packets`. Correct import is `from f1 import packets`.

**Result:** Import resolved. This became a permanent note in the README and memory. All subsequent modules use the correct namespace.

**Pending at end of session:** Phase 1 — UDP listener.

---

### ~2026-05-14 — Phase 1: UDP Listener

**Worked on:** `src/listener.py` — standalone diagnostic script. Opens a UDP socket on port 20777, binds to all interfaces, and prints a timestamped one-line summary for each arriving packet. Includes a `PACKET_NAMES` lookup table covering all 16 F1 25 packet IDs. Uses `get_local_ip()` to display the machine's LAN IP at startup.

**Tested:** Ran `venv\Scripts\python.exe src\listener.py` with F1 25 running on the PS5. Confirmed all expected packet types arriving: Motion, Session, Lap Data, Event, Participants, Car Setups, Car Telemetry, Car Status, Final Classification, Car Damage, Session History, Tyre Sets.

**Result:** PS5 confirmed broadcasting at approximately 60 fps from 192.168.1.39. Packet ID offset confirmed at byte 6.

**Pending at end of session:** Phase 2 — parse the raw bytes into meaningful data.

---

### ~2026-05-14 — Phase 2: Packet Parser

**Worked on:** `src/parser.py`. Defines `empty_race_state()` (the canonical 22-car race state dict), `parse_packet()` (routes raw bytes to the correct sub-extractor), and `update_race_state()` (merges partial updates per-car without overwriting unrelated fields).

Packet types parsed:
- **Motion** — world X/Z position for the player's car
- **Session** — track name, session type, total laps, temperatures, weather, safety car status, pit window ideal/latest/rejoin, sector boundary distances
- **Lap Data** — all 22 cars: position, lap number, pit status, pit stops, last lap ms, driver status, delta to car in front, `lap_distance_m`; player: current lap, lap time, sector, sector times, gap to ahead/behind
- **Participants** — driver name and team ID for all 22 cars
- **Car Telemetry** — speed, throttle, brake, gear, RPM, DRS active, tyre surface temperatures (FL/FR/RL/RR), speed for all 22 cars
- **Car Status** — fuel remaining laps, tyre compound, tyre age, DRS allowed, ERS store %, ERS deploy mode for all 22 cars
- **Car Damage** — per-corner tyre wear (FL/FR/RL/RR) for the player
- **Tyre Sets** — compound of the currently fitted tyre set (player only, addressed by car index)
- **Session History** — separated into `parse_session_history()` because it carries AI car lap history, not live state

Constants defined: `PACKET_ID_OFFSET = 6`, `ERS_MAX_JOULES = 4_000_000`, `SECTOR_MINUTES_TO_MS = 60_000`, tyre array index constants (RL=0, RR=1, FL=2, FR=3 per F1 25 spec).

**Tested:** Standalone harness (`if __name__ == "__main__"`) listens live and calls `pprint.pprint(race_state)` every 2 seconds. Confirmed all fields populating from live PS5 packets.

**Result:** Full race state dict populating correctly across all packet types. `import pprint` correctly scoped inside `__main__` block only (production import path has no debug dependency).

**Pending at end of session:** Phase 3 — state management, lap history, event detection.

---

### ~2026-05-15 — Phase 3: Race State Manager

**Worked on:** `src/state_manager.py`. `RaceStateManager` wraps the parser and adds:

- **Lap history** — end-of-lap snapshot saved per lap (lap time, sector times, position, per-corner tyre wear, axle averages)
- **Sector time capture** — `_check_sector_transition()` stores S1/S2 times at the exact frame the boundary is crossed, avoiding the game clearing them before lap end
- **Session reset** — two paths: full reset (session/track change, clears all history) and intra-session reset (lap drops to 1, preserves history for garage visits)
- **Event detection** — tyre wear spikes (>2% in one update), tyre wear thresholds (warning at 50%, critical at 80%), position changes (OVERTAKE / OVERTAKEN), DRS availability changes, new lap
- **Analytics** — pace trend (average last 3 laps vs previous 3), tyre wear rate (% per lap over current stint), pit window estimate (laps until worst corner reaches 80%)
- **Reference lap** — integrated `ReferenceLap` class: personal best with per-sector telemetry, AI best from Session History packets, qualifying best promoted at session boundary
- **Session data store** — `SessionDataStore` writes per-sector and per-lap telemetry to `data/sessions/YYYY-MM-DD_{track}_{session}.json`
- **On-track proximity** — `_compute_track_proximity()` derives absolute track position as `lap × track_length_m + lap_distance_m`, correctly ordering cars across lap boundaries regardless of classification order

Key constants: `TRACK_LENGTH_FALLBACK_M = 10_000`, `PROXIMITY_SPEED_FLOOR_KMH = 30`, `KMH_TO_MPS = 1.0 / 3.6`, `TYRE_WEAR_SPIKE_THRESHOLD_PCT = 2.0`, `TYRE_WARNING_THRESHOLD_PCT = 50.0`, `TYRE_CRITICAL_THRESHOLD_PCT = 80.0`, `STINT_AGE_DROP_THRESHOLD = 5`.

**Tested:** Standalone harness runs live and prints `_format_briefing_for_display()` every 5 seconds. Verified lap history accumulating, events firing, session reset triggering on track change.

**Result:** Full briefing dict populating. Session history packets routing to AI best correctly. Qualifying best surviving the qualifying-to-race transition via `save_qualifying_best()`.

**Pending at end of session:** Phase 4 — AI brain.

---

### ~2026-05-15 — Phase 4: Engineer AI Brain

**Worked on:** `src/engineer.py`. `EngineerAI` drives Gemini 2.5 Flash via Vertex AI.

Session modes:
- **Practice** — speaks every 45 s, immediately for traffic within 15 s or pit entry debrief; includes active programme state, session stats, recommended programme with briefout script
- **Qualifying** — speaks every 8 s on out laps, every 5 s when a car closes within 15 s, immediately for push lap obstruction; silent in sectors 1 and 3 during flying lap
- **Race** — speaks on gap changes > 0.3 s, pit window entry, accelerating tyre degradation, or every 3 laps; 20 s silence cooldown between non-critical transmissions

Prompt architecture:
- `ENGINEER_SYSTEM_PROMPT` — persona, transmission rules, tyre/ERS/DRS/gap/strategy rules, coaching rules, silence rules
- Per-call briefing blocks assembled from current state, sector times, tyre data, nearby cars, recent events, lap history, reference lap, circuit reference notes, recent topic list
- Track knowledge (`F1_KNOWLEDGE` + per-circuit brief from `track_mapper`) injected **once** per session on first call, then suppressed to save tokens
- Rolling conversation history capped at 6 messages

Supporting modules built:
- `src/f1_knowledge.py` — tyre optimal temp windows per compound, wear thresholds, ERS thresholds, `F1_KNOWLEDGE` text block (protected reference document)
- `src/circuit_reference.py` — qualifying and race corner notes for all 24 circuits at AI difficulty 106–110, with braking board distance, gear, and coaching note per turn
- `src/practice_programmes.py` — six telemetry-driven practice programmes (Track Baseline, Trail Braking, Oversteer Management, Tyre Analysis, ERS Deployment, Race Simulation) with `engineer_briefout` and `engineer_debrief` script lines
- `src/track_data.py` — static circuit data: lap length, corners, DRS zones, tyre characteristics, overtaking spots for all 24 circuits
- `src/track_mapper.py` — resolves F1 25 telemetry track names to circuit data, handles aliases (COTA→Texas, Interlagos→Brazil etc.), produces formatted TRACK KNOWLEDGE prompt block

**Tested:** Standalone Gemini integration test (`if __name__ == "__main__"`) fires a fake Monza race briefing at lap 15/57, P3, with tyre wear in the warning range. Response printed with token counts (`[TOKENS] in: X out: Y`).

**Result:** Gemini responding with authentic F1 radio language. Token counts confirmed in/out logged. `MAX_RESPONSE_TOKENS` initially set at 300 (later raised to 1000 — see 2026-05-20).

**Pending at end of session:** Phase 5 — wire everything together with a WebSocket dashboard.

---

### 2026-05-16 — Phase 5: Live Server and Dashboard

**Worked on:** `src/server.py` — asyncio entry point running three concurrent tasks:

1. **UDP listener loop** (`_UDPProtocol`) — asyncio datagram protocol ingesting raw packets to `RaceStateManager.ingest()`, socket buffer set to `UDP_RECV_BUFFER_BYTES = 65536`
2. **Engineer cycle** — polls `engineer.should_speak()` every second, calls `engineer.get_engineer_response()` when triggered, appends to rolling message list (capped at 5)
3. **WebSocket server** — broadcasts 30 Hz JSON snapshot via `_broadcast_loop()`, handles bidirectional messages: `save_track_shape` / `load_track_shape` for GPS track persistence

Payload builder split across four functions to meet the 20-line rule: `_compute_pit_window_fields`, `_build_car_and_session_fields`, `_build_multicar_and_proximity_fields`, `_build_payload`.

Constants: `BROADCAST_INTERVAL_SECONDS = 0.033`, `ENGINEER_CHECK_INTERVAL_S = 1.0`, `UDP_RECV_BUFFER_BYTES = 65536`, `PIT_WINDOW_BUFFER_LAPS = 2`, `WS_PORT = 8765`.

`dashboard/index.html` features built:
- Speed, gear, DRS indicator, throttle/brake bars
- Tyre wear per corner with colour bands (green/amber/red), tyre temperature per corner
- Sector time badges (purple = session best, yellow = personal best, white = normal) via `sectorBadgeClass()`
- Lap history table (last 10 laps)
- Gap panel — physically nearest car ahead and behind on track (proximity-based in practice, position-order fallback in race)
- Pit window display with lap range
- Safety car / VSC status banner
- Live GPS track map — accumulated GPS points drawn as SVG polyline, sector 1/2/3 coloured differently, car dot, track locked after 3 averaged laps, shape saved/restored from `data/tracks/` after 5 clean laps via WebSocket round-trip
- Engineer message history panel (last 5 transmissions with timestamps)
- All-cars mini table

Track map constants: `TRACK_MIN_POINTS_TO_RESTORE = 50`, `TRACK_MIN_POINTS_VALID_LAP = 100`.

**Tested:** Full system run with PS5 live. Dashboard opened in browser. Engineer transmissions confirmed appearing. WebSocket connection stable.

**Result:** Complete system end-to-end working. All five phases confirmed functional.

**Pending at end of session:** Feature improvements and code quality audit.

---

### 2026-05-17 — Feature Session: Lap History Persistence, Proximity, Sectors, Track Locking, Gaps

**Worked on:** Six-step feature additions across `parser.py`, `state_manager.py`, `server.py`, and `dashboard/index.html`:

1. **Lap history persistence** — `state_manager.py` preserves `lap_history` across intra-session resets (garage visits). Full reset (track/session change) still clears it.
2. **On-track proximity** — `_compute_track_proximity()` introduced in `state_manager.py`. Computes absolute track position as `lap × track_length + lap_distance_m`. `_nearest_car_in_direction()` module-level helper finds closest car ahead/behind. Results stored in `_track_car_ahead` / `_track_car_behind` and surfaced in the briefing.
3. **Sector colour badges** — `sectorBadgeClass(timeMs, personalBestMs, sessionBestMs)` returns `'sb'` / `'pb'` / `'normal'`. Dashboard applies purple / yellow / white styling to each sector cell.
4. **GPS track locking and saving** — `maybeRecordTrackPoint()` accumulates GPS points per lap. After 3 clean laps the track outline locks. After 5 clean laps the shape is sent to the server via `save_track_shape` WebSocket message and persisted to `data/tracks/{track_name}.json`. On dashboard load `load_track_shape` retrieves it. Three polylines (`trk-poly-s1/s2/s3`) split at `_sectorBoundary2` / `_sectorBoundary3`.
5. **Gaps panel** — shows `track_car_ahead` and `track_car_behind` from proximity data in practice sessions. Falls back to championship-position adjacent cars in race.
6. **Import check** — all 7 modules confirmed clean.

**Tested:** Import check: `parser`, `state_manager`, `engineer`, `server`, `f1_knowledge`, `track_mapper`, `circuit_reference` — all OK.

**Result:** All features added and import-clean.

**Pending at end of session:** Code quality audit.

---

### 2026-05-17 — Code Quality Audit: 52 Violations Found

**Worked on:** Full audit of the four recently changed files against the project code standard (full docstrings with Parameters/Returns, named constants for every magic number, section headers, methods under 20 lines, full variable names, no dead code, no unused imports).

**Violations found:**

- `parser.py` — 3 violations: `import pprint` at module level; `_default_car_entry()` missing Returns docstring; `_parse_lap_data()` Returns not mentioning `lap_distance_m` or `delta_to_car_in_front_ms`
- `state_manager.py` — 5 violations: `_reset_all_state()`, `_reset_intra_session_state()`, `_handle_session_history()`, `_compute_reference_coaching()` docstrings incomplete; inline literal `1.0 / 3.6` with no named constant
- `server.py` — 12 violations: docstrings missing or incomplete on `_print_banner`, all `_UDPProtocol` methods, `_broadcast_loop`, `main()`, inner `_handler`; magic numbers `65536` and `2` without named constants; `_build_payload` at 140 lines (must be under 20)
- `dashboard/index.html` — 32 violations: 14 functions missing JSDoc; single-letter and abbreviated variable names throughout; missing named constants; 5 functions over 20 lines

**Result:** Report delivered in full before any changes. 52 violations total.

**Pending at end of session:** Step 2 — fix all 52.

---

### 2026-05-18 — Code Quality Fix: All 52 Violations Resolved

**Worked on:** Fixed every violation identified in the audit, file by file.

`parser.py` changes:
- Moved `import pprint` inside `if __name__ == "__main__"` block
- Added full Returns section to `_default_car_entry()` docstring
- Updated `_parse_lap_data()` Returns to mention `lap_distance_m` and `delta_to_car_in_front_ms`

`state_manager.py` changes:
- Expanded docstrings for `_reset_all_state`, `_reset_intra_session_state`, `_handle_session_history`, `_compute_reference_coaching` with full Parameters/Returns sections
- Added named constant `KMH_TO_MPS = 1.0 / 3.6` with explanatory comment; replaced inline literal in `_compute_track_proximity`

`server.py` changes:
- Added full docstrings to `_print_banner`, all `_UDPProtocol` methods (`connection_made`, `datagram_received`, `error_received`), `_broadcast_loop`, `main()`, inner `_handler`
- Added `engineer` parameter documentation to `_build_payload` and `_broadcast_loop` docstrings
- Added named constants `UDP_RECV_BUFFER_BYTES = 65536` and `PIT_WINDOW_BUFFER_LAPS = 2`
- Split `_build_payload` (140 lines) into four functions: `_compute_pit_window_fields`, `_build_car_and_session_fields`, `_build_multicar_and_proximity_fields`, `_build_payload` (orchestrator)

`dashboard/index.html` changes:
- Added JSDoc to all 14 original functions plus all 6 new helper functions extracted during splits
- Renamed all abbreviated and single-letter variable names to full descriptive names (e.g. `x`→`worldX`, `z`→`worldZ`, `ar`→`aspectRatio`, `dw`→`drawAreaW` etc. throughout `_toSvgPt`)
- Added named JS constants `TRACK_MIN_POINTS_TO_RESTORE = 50`, `TRACK_MIN_POINTS_VALID_LAP = 100`
- Renamed `(a, b) => a.dist - b.dist` sort comparator to `(groupA, groupB) => groupA.dist - groupB.dist`
- Split 5 over-length functions by extracting helpers:
  - `_onLapBoundaryForTrackRecord()` from `maybeRecordTrackPoint`
  - `_buildCurrentLapRow()` and `_buildHistoricLapRow()` from `updateLapHistory`
  - `_applyScActivePanel()` and `_applyNormalStrategyPanel()` from `updateStrategy`
  - `_applyGapSection()` and `_resolveAdjacentGaps()` from `updateGaps`
  - `_maybeRequestTrackShape()` and `_maybeUpdateLapHistory()` from `applyData`

**Tested:** Import check after all 52 fixes — all 7 modules clean.

**Result:** Zero violations remaining. Import check passed.

**Pending at end of session:** Logic correctness verification (Step 3 from the audit) and the pending engineer.py items.

---

### 2026-05-20 — Engineer Fixes: Token Limit, Sentence Rule, Repetition, Proximity Skip

**Worked on:** Five targeted fixes to `engineer.py` and `state_manager.py`.

`engineer.py` — STEP 1 (sentence cutoff):
- Raised `MAX_RESPONSE_TOKENS` from 300 to **1000**. At 300 tokens the model was regularly cutting off mid-sentence because it ran out of budget before finishing the thought.
- Added to FUNDAMENTAL RULE in `ENGINEER_SYSTEM_PROMPT`: `"A semicolon, comma, or dash is never the end of a transmission — you must always reach a full stop before stopping."` This makes the completion rule explicit for punctuation that the model was using as an exit point.

`engineer.py` — STEP 2 (programme announcement repetition):
- **Root cause:** `_format_practice_session_block()` included the `Suggest: "engineer_briefout"` line on every single call when no programme was active. The model read it as a script and re-announced the Track Baseline programme every transmission.
- **Fix:** Added `_programme_announced: bool = False` instance attribute. Added `_programme_announced = False` reset in `_load_session_resources()` so it clears on session/track change. Separated `"programme"` from `"lap"` in `_infer_topic()` — programme mentions now return the distinct label `"PROGRAMME_ANNOUNCEMENT"` instead of sharing the generic `"PRACTICE"` label. In `get_engineer_response()`, when topic is `"PROGRAMME_ANNOUNCEMENT"`, sets `self._programme_announced = True`. In `_format_practice_session_block()`, the `Suggest:` line is suppressed after the first announcement so the model no longer sees the scripted text.

`state_manager.py` — STEP 3/4 (proximity diagnosis and fix):
- **Diagnosis:** `_nearest_car_in_direction()` was using `car.get("lap_distance_m", 0.0)` and only skipping cars where `car_lap == 0` or `name` was empty. Cars with `lap_distance_m = 0.0` were included, placed at the very start of their lap (absolute position = `lap × track_length_m`). This produced phantom proximity readings from cars with stale or not-yet-arrived data.
- **Fix:** Added `or car_dist <= 0.0` to the skip condition. Cars with zero or missing `lap_distance_m` are now skipped entirely.

**Tested:** Import check — all 7 modules clean after all changes.

**Result:** All five items resolved. `MAX_RESPONSE_TOKENS = 1000` confirmed.

---

## Pending Items

| Item | Priority | Notes |
|---|---|---|
| Unit tests for `parser.py` | High | Pure data transformation — must have unit tests before project considered complete |
| Unit tests for `state_manager.py` | High | Pure data layer — same requirement |
| Logic correctness verification (Step 3 from audit) | Medium | Six checks: lap history reset, proximity lap-distance use, sector badge reachability, track outline split, GPS lock/save timing, gaps panel session routing |
| Phase 6 — Voice output | — | Not started |
| Phase 7 — 5-persona roundtable | — | Not started |
