# F1 Engineer AI

A real-time AI race engineer that connects to F1 25 telemetry via UDP and
provides live coaching, race strategy, and gap calls over a browser dashboard.

**Current model:** `gemini-2.5-flash` via Google Cloud Vertex AI

---

## Structure

```
src/          Python backend — parser, state manager, AI brain, data store
dashboard/    Browser interface for live telemetry display
data/         Saved session data (JSON, auto-created)
logs/         Debug logs
.env          API keys and GCP credentials (never committed)
```

---

## Run instructions

**Prerequisites**

1. Python 3.12+ with a virtual environment in `venv/`
2. Google Cloud SDK installed and authenticated:
   ```
   gcloud auth application-default login
   gcloud auth application-default set-quota-project <your-project-id>
   ```
3. `.env` file in the project root:
   ```
   ANTHROPIC_API_KEY=...         # kept as fallback, not used for active calls
   GEMINI_API_KEY=...            # kept as fallback
   GOOGLE_CLOUD_PROJECT=...      # your GCP project ID
   GOOGLE_CLOUD_REGION=us-central1
   ```
4. Key packages: `google-genai==2.3.0`, `websockets`, `python-dotenv`, `f1-packets`

**Start the live system**

```
venv\Scripts\python.exe src\server.py
```

Then open `dashboard/index.html` in a browser.

**F1 25 in-game settings**

- Settings → Telemetry → UDP Telemetry: On
- IP Address: your PC's local IP
- Port: 20777
- Format: 2025
- Send Rate: 60 Hz (recommended)

**Test the AI brain in isolation**

```
venv\Scripts\python.exe src\engineer.py
```

Runs a fake Monza race briefing and prints the Gemini response with token counts.

---

## Phases

- [x] **Phase 0** — Project setup ✅
  > `f1-packets` installs under the `f1` namespace. Correct import: `from f1 import packets`

- [x] **Phase 1** — UDP listener ✅
  > PS5 confirmed broadcasting all packet types at ~60 fps. Source IP: 192.168.1.39.
  > Standalone listener: `venv\Scripts\python.exe src\listener.py`

- [x] **Phase 2** — Packet parser ✅
  > Extracts speed, throttle, brake, gear, DRS, lap data, tyre wear per corner, ERS, fuel,
  > track name, session type, multi-car array, pit window fields, weather forecast.
  > Standalone: `venv\Scripts\python.exe src\parser.py`

- [x] **Phase 3** — Race state manager ✅
  > `RaceStateManager` wraps the parser, maintains lap history, detects events
  > (tyre spikes/thresholds, position changes, DRS, new laps, session restarts),
  > records sector and lap data to `SessionDataStore`, and produces
  > `get_engineer_briefing()` with pace trend, wear rate, and pit window.
  > Standalone: `venv\Scripts\python.exe src\state_manager.py`

- [x] **Phase 4** — Engineer AI brain ✅
  > `EngineerAI` drives `gemini-2.5-flash` via Vertex AI. Session-aware: practice,
  > qualifying, and race modes each use a different briefing format and trigger logic.
  > Track knowledge and F1_KNOWLEDGE are injected once per session then suppressed.
  > Circuit reference corner notes and practice programme suggestions are included.
  > Token usage logged after every call. Rolling history capped at 6 messages.
  > Standalone: `venv\Scripts\python.exe src\engineer.py`

- [x] **Phase 5** — Dashboard interface ✅
  > WebSocket server broadcasts a 30 Hz JSON snapshot to `dashboard/index.html`.
  > Displays speed, gear, DRS, tyre wear/temps, gap data, pit window, sector times,
  > track map position, all-cars array, and engineer message history.
  > Full system: `venv\Scripts\python.exe src\server.py`

- [ ] **Phase 6** — Voice output
- [ ] **Phase 7** — 5-persona roundtable

---

## Source files

| File | Description |
|------|-------------|
| `src/server.py` | Main entry point — runs the UDP listener, engineer cycle, and WebSocket broadcast server concurrently. |
| `src/engineer.py` | AI brain — session-aware briefing builder and Gemini API driver with practice, qualifying, and race modes. |
| `src/state_manager.py` | Race state layer — lap history, event detection, sector/lap data recording, and briefing assembly. |
| `src/parser.py` | UDP packet parser — decodes all F1 25 packet types into a live `race_state` dict. |
| `src/circuit_reference.py` | Corner-by-corner coaching notes and lap time targets for all 24 circuits at 108-110 AI difficulty. |
| `src/practice_programmes.py` | Definitions and selection logic for the six telemetry-driven practice session programmes. |
| `src/session_data.py` | `SessionDataStore` — writes per-lap and per-sector telemetry to dated JSON files under `data/sessions/`. |
| `src/f1_knowledge.py` | Domain constants — tyre optimal temp windows, wear thresholds, ERS levels, and the `F1_KNOWLEDGE` text block. |
| `src/reference_lap.py` | Three-tier reference lap system — personal best, AI best (from Session History packets), and qualifying best. |
| `src/track_mapper.py` | Resolves telemetry track names to circuit data and produces the TRACK KNOWLEDGE prompt block. |
| `src/track_data.py` | Static data for all 24 circuits — corners, DRS zones, tyre characteristics, overtaking spots. |
| `src/listener.py` | Phase 1 standalone UDP listener — prints raw packet counts for verifying PS5 connectivity. |
| `src/geojson_to_svg.py` | Converts GeoJSON track boundary data into SVG path files for the dashboard map. |
| `src/generate_svg_data_js.py` | Generates the JavaScript track coordinate arrays consumed by the dashboard track map. |
| `src/test.py` | Standalone test harness for early integration checks. |
| `src/__init__.py` | Empty package marker so `src/` is importable as a package. |
