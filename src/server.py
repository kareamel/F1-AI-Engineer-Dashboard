"""
F1 Engineer — Live Server
Entry point for the complete F1 25 race engineering system.

Runs three things concurrently using asyncio:
  - UDP listener:     receives telemetry packets from PS5 on port UDP_PORT
  - Engineer cycle:   calls Claude API every ENGINEER_CYCLE_SECONDS, or on
                      critical events detected by the state manager
  - WebSocket server: broadcasts a live JSON snapshot to all dashboard
                      clients every BROADCAST_INTERVAL_SECONDS

Run from the project root:
    venv\\Scripts\\python.exe src\\server.py

Then open dashboard/index.html in any browser.
Multiple browser tabs can connect simultaneously.
"""

import asyncio
import json
import socket
import sys
from datetime import datetime
from pathlib import Path

import websockets
import websockets.exceptions

# Ensure src/ is on sys.path so imports resolve when run from project root
sys.path.insert(0, str(Path(__file__).parent))

from engineer import (
    GEMINI_MODEL,
    DISPLAY_SEPARATOR,
    TIMESTAMP_FORMAT,
    EngineerAI,
)
from state_manager import RaceStateManager
from track_mapper import get_track_data


# ---------------------------------------------------------------------------
# Network constants
# ---------------------------------------------------------------------------

UDP_BIND_HOST = "0.0.0.0"   # bind to all interfaces (explicit, not empty string)
UDP_PORT      = 20777       # F1 25 telemetry port — must match in-game setting
WS_HOST       = "localhost"
WS_PORT       = 8765        # dashboard connects to ws://localhost:8765


# ---------------------------------------------------------------------------
# Track shape persistence
# ---------------------------------------------------------------------------

# Directory where canonical track shapes are saved as {track_name}.json files.
# Created automatically at startup if it does not exist.
TRACK_DATA_DIR = Path(__file__).parent.parent / "data" / "tracks"

# Characters allowed in a track name when building a safe file path
_TRACK_NAME_SAFE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ ")


# ---------------------------------------------------------------------------
# Timing constants
# ---------------------------------------------------------------------------

BROADCAST_INTERVAL_SECONDS  = 0.033 # push interval to dashboard clients (30 Hz)
ENGINEER_CHECK_INTERVAL_S   = 1.0   # poll interval for engineer trigger check

# ---------------------------------------------------------------------------
# UDP socket tuning constants
# ---------------------------------------------------------------------------

# Socket receive buffer size in bytes — large enough to hold ~40 complete F1 25
# packets (max datagram ~1352 B) so bursts at 60 Hz do not overflow the kernel
# buffer on Windows before asyncio can drain it.
UDP_RECV_BUFFER_BYTES = 65536

# ---------------------------------------------------------------------------
# Pit window display constants
# ---------------------------------------------------------------------------

# Number of laps either side of the estimated pit lap used to show a window
# rather than a single target lap, e.g. estimate=15 → show laps 13–17.
PIT_WINDOW_BUFFER_LAPS = 2


# ---------------------------------------------------------------------------
# Message history
# ---------------------------------------------------------------------------

MAX_ENGINEER_MESSAGES = 5   # messages kept in memory and broadcast to dashboard


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------

_BANNER_LINE = "+" + "-" * 56 + "+"

def _print_banner() -> None:
    """Prints the startup status banner to stdout.

    Returns:
        None.
    """
    print(_BANNER_LINE)
    print("|{:^56}|".format("F1 ENGINEER  --  LIVE SYSTEM"))
    print(_BANNER_LINE)
    print("|  UDP Listener    port {:<5}  waiting for PS5             |".format(UDP_PORT))
    print("|  WebSocket       port {:<5}  open dashboard/index.html   |".format(WS_PORT))
    print("|  Engineer AI     event-based  {:<26}|".format(GEMINI_MODEL))
    print(_BANNER_LINE)
    print()


# ---------------------------------------------------------------------------
# Payload builder — split across four functions to stay under 20 lines each
# ---------------------------------------------------------------------------

def _compute_pit_window_fields(pit_window: int | None,
                               current_lap: int,
                               tyre_age: int) -> dict:
    """Derives the displayable pit window start/end laps and estimated tyre life.

    Parameters:
        pit_window:  Estimated laps remaining before mandatory pit, or None.
        current_lap: Current race lap number.
        tyre_age:    Laps on the current tyre set.

    Returns:
        Dict with keys: pit_window_lap_start, pit_window_lap_end,
        tyre_life_estimated.
    """
    pit_window_start = None
    pit_window_end   = None
    if pit_window is not None and current_lap > 0:
        pit_window_start = current_lap + max(0, pit_window - PIT_WINDOW_BUFFER_LAPS)
        pit_window_end   = current_lap + pit_window + PIT_WINDOW_BUFFER_LAPS
    tyre_life_estimated = (tyre_age + pit_window) if pit_window is not None else tyre_age
    return {
        "pit_window_lap_start": pit_window_start,
        "pit_window_lap_end":   pit_window_end,
        "tyre_life_estimated":  tyre_life_estimated,
    }


def _build_car_and_session_fields(state: dict, race_progress_pct: float) -> dict:
    """Extracts car telemetry, session identity, and tyre fields from state.

    Parameters:
        state:             Current race state dict from the briefing.
        race_progress_pct: Race completion percentage (0–100).

    Returns:
        Dict covering car inputs, session context, and all tyre fields.
    """
    tyre_age = state["tyre_age_laps"]
    return {
        "speed_kmh":         state["speed_kmh"],
        "throttle_pct":      state["throttle_pct"],
        "brake_pct":         state["brake_pct"],
        "gear":              state["gear"],
        "drs_active":        state["drs_active"],
        "drs_allowed":       state["drs_allowed"],
        "ers_store_pct":     state["ers_store_pct"],
        "position":          state["position"],
        "current_lap":       state["current_lap"],
        "total_laps":        state["total_laps"],
        "session_type":      state["session_type"],
        "track_name":        state["track_name"],
        "race_progress_pct": race_progress_pct,
        "safety_car_active": bool(state["safety_car_status"]),
        "tyre_compound":     state["tyre_compound"],
        "tyre_age_laps":     tyre_age,
        "tyre_life_used":    tyre_age,
        "tyre_wear_fl":      state["tyre_wear_fl"],
        "tyre_wear_fr":      state["tyre_wear_fr"],
        "tyre_wear_rl":      state["tyre_wear_rl"],
        "tyre_wear_rr":      state["tyre_wear_rr"],
        "tyre_temp_fl":      state["tyre_temp_fl"],
        "tyre_temp_fr":      state["tyre_temp_fr"],
        "tyre_temp_rl":      state["tyre_temp_rl"],
        "tyre_temp_rr":      state["tyre_temp_rr"],
    }


def _build_multicar_and_proximity_fields(state: dict, briefing: dict,
                                         track_info: dict) -> dict:
    """Extracts multi-car, proximity, position, gap, and weather fields.

    Parameters:
        state:      Current race state dict from the briefing.
        briefing:   Full engineer briefing dict from the state manager.
        track_info: Track data dict from track_mapper (may be empty).

    Returns:
        Dict covering all_cars, gap data, track position, and weather.
    """
    return {
        "lap_history":         briefing["lap_history_summary"],
        "sector_1_time":       state["sector1_time_ms"],
        "sector_2_time":       state["sector2_time_ms"],
        "sector_3_time":       None,
        "current_sector":      state["sector"],
        "exit_position":       None,
        "free_air":            True,
        "traffic_driver":      None,
        "traffic_gap":         None,
        "car_ahead_driver":    None,
        "car_ahead_gap":       None,
        "car_ahead_gap_prev":  None,
        "car_behind_driver":   None,
        "car_behind_gap":      None,
        "car_behind_gap_prev": None,
        "leader_driver":       None,
        "leader_gap":          None,
        "car_x":               state["car_x"],
        "car_z":               state["car_z"],
        "lap_distance_m":      state["lap_distance_m"],
        "track_length_km":     track_info.get("lap_length_km", 0.0),
        "all_cars":            state["all_cars"],
        "gap_to_ahead_ms":     state["gap_to_ahead_ms"],
        "gap_to_leader_ms":    state["gap_to_leader_ms"],
        "track_car_ahead":     briefing.get("track_car_ahead"),
        "track_car_behind":    briefing.get("track_car_behind"),
        "pit_window_ideal":    state["pit_window_ideal"],
        "pit_window_latest":   state["pit_window_latest"],
        "pit_rejoin_position": state["pit_rejoin_position"],
        "weather_forecast":    state["weather_forecast"],
        "pit_status":          state["pit_status"],
        "sector2_lap_dist_m":  state["sector2_lap_dist_m"],
        "sector3_lap_dist_m":  state["sector3_lap_dist_m"],
    }


def _build_payload(manager: RaceStateManager, messages: list,
                   engineer: EngineerAI) -> dict:
    """Builds the JSON object broadcast to all dashboard clients every tick.

    Delegates to three section builders then merges the results. Fields not
    yet extracted from telemetry packets are sent as None/0 so the dashboard
    gracefully shows dashes rather than crashing.

    Parameters:
        manager:  Live RaceStateManager instance.
        messages: Current engineer message history list (newest first).
        engineer: Live EngineerAI instance — provides active_programme and
                  circuit_reference for the dashboard practice panels.

    Returns:
        A dict that json.dumps() can serialise directly.
    """
    briefing          = manager.get_engineer_briefing()
    state             = briefing["current_state"]
    track_info        = get_track_data(state["track_name"]) or {}
    current_lap       = state["current_lap"]
    total_laps        = state["total_laps"]
    race_progress_pct = round(current_lap / total_laps * 100, 1) if total_laps > 0 else 0

    pit_fields = _compute_pit_window_fields(
        briefing["pit_window_estimate_laps"], current_lap, state["tyre_age_laps"]
    )
    session_bests = {
        "session_best_s1":   briefing.get("session_best_s1", 0),
        "session_best_s2":   briefing.get("session_best_s2", 0),
        "session_best_s3":   briefing.get("session_best_s3", 0),
        "active_programme":  engineer._active_programme,
        "circuit_reference": engineer._circuit_reference,
        "engineer_messages": list(messages),
    }
    return {
        **_build_car_and_session_fields(state, race_progress_pct),
        **_build_multicar_and_proximity_fields(state, briefing, track_info),
        **pit_fields,
        **session_bests,
    }


# ---------------------------------------------------------------------------
# UDP listener
# ---------------------------------------------------------------------------

class _UDPProtocol(asyncio.DatagramProtocol):
    """asyncio UDP protocol that feeds raw packets into the state manager."""

    def __init__(self, manager: RaceStateManager) -> None:
        """Initialises the protocol with a reference to the state manager.

        Parameters:
            manager: The live RaceStateManager that will receive every packet.

        Returns:
            None.
        """
        self._manager       = manager
        self.packet_count   = 0
        self._announced     = False

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        """Called by asyncio for each received datagram; forwards to the manager.

        Parameters:
            data: Raw datagram bytes from the F1 25 game.
            addr: (host, port) tuple of the sender — used for the first-packet banner.

        Returns:
            None.
        """
        if not self._announced:
            self._announced = True
            print(f"[UDP]  First packet from {addr[0]} — telemetry live\n")
        self.packet_count += 1
        self._manager.ingest(data)

    def error_received(self, exc: Exception) -> None:
        """Called by asyncio if a send or receive error occurs on the socket.

        Parameters:
            exc: The exception raised by the transport layer.

        Returns:
            None.
        """
        print(f"[UDP]  Error: {exc}")

    def connection_lost(self, exc: Exception | None) -> None:
        """Called by asyncio when the transport is closed.

        Parameters:
            exc: The exception that caused the closure, or None for a clean close.

        Returns:
            None.
        """
        if exc:
            print(f"[UDP]  Connection lost: {exc}")


# ---------------------------------------------------------------------------
# Engineer cycle
# ---------------------------------------------------------------------------

async def _engineer_cycle(
    udp_protocol: _UDPProtocol,
    manager:      RaceStateManager,
    engineer:     EngineerAI,
    messages:     list,
) -> None:
    """Polls every ENGINEER_CHECK_INTERVAL_S and calls Gemini when appropriate.

    Waits until at least one telemetry packet has arrived before enabling the
    engineer, so it never fires against an empty default state on startup.
    The blocking Gemini API call is offloaded to a thread pool via
    asyncio.to_thread so it never stalls the event loop.

    Parameters:
        udp_protocol: The live UDP protocol instance — used to check packet_count.
        manager:      Live RaceStateManager to get briefings from.
        engineer:     EngineerAI instance that owns conversation history.
        messages:     Shared list; new messages are prepended here and trimmed
                      to MAX_ENGINEER_MESSAGES entries.
    """
    while True:
        await asyncio.sleep(ENGINEER_CHECK_INTERVAL_S)

        # Hold off until the PS5 is sending data
        if udp_protocol.packet_count == 0:
            continue

        briefing = manager.get_engineer_briefing()
        if not engineer.should_speak(briefing):
            continue

        critical = engineer.get_critical_trigger(briefing)
        try:
            response = await asyncio.to_thread(
                engineer.get_engineer_response, briefing
            )
        except Exception as exc:
            print(f"[ENGINEER]  API error: {exc}")
            continue

        if response is None:
            continue

        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        prefix    = "[CRITICAL]  " if critical else ""
        messages.insert(0, {"timestamp": timestamp, "text": response})
        del messages[MAX_ENGINEER_MESSAGES:]

        print(DISPLAY_SEPARATOR)
        print(f"[{timestamp}]  {prefix}ENGINEER  "
              f"[{udp_protocol.packet_count} packets  |  "
              f"{len(messages)} msg(s)]")
        print(DISPLAY_SEPARATOR)
        print(response)
        print()


# ---------------------------------------------------------------------------
# Track shape save / load helpers
# ---------------------------------------------------------------------------

def _safe_track_filename(track_name: str) -> str:
    """Returns a filesystem-safe filename for the given track name.

    Strips any character not in the safe set so that user-supplied track names
    from the game telemetry cannot produce path-traversal file names.

    Parameters:
        track_name: Raw track name string from the telemetry state.

    Returns:
        A sanitised string suitable for use as a JSON filename (no extension).
    """
    return "".join(c for c in track_name if c in _TRACK_NAME_SAFE_CHARS).strip()


async def _save_track_shape(msg: dict) -> None:
    """Writes a canonical track shape received from the dashboard to disk.

    The shape is stored as JSON at TRACK_DATA_DIR/{track_name}.json so it can
    be loaded instantly on the next visit to the same circuit.  The directory
    is created if it does not already exist.

    Parameters:
        msg: Parsed message dict expected to contain 'track_name' (str) and
             'points' (list of {x, z, dist} dicts).

    Returns:
        None.
    """
    track_name = msg.get("track_name", "").strip()
    points     = msg.get("points", [])
    safe_name  = _safe_track_filename(track_name)
    if not safe_name or not points:
        return
    TRACK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_path = TRACK_DATA_DIR / f"{safe_name}.json"
    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump({"track_name": track_name, "points": points}, fh)
    print(f"[TRACK]  Saved shape for '{track_name}' ({len(points)} pts) → {file_path.name}")


async def _load_track_shape(websocket, msg: dict) -> None:
    """Reads a saved track shape and sends it to the requesting dashboard client.

    If no shape file exists for the requested track, sends an empty 'points'
    array so the dashboard knows to start the recording phase.  The response
    always includes a 'type' field so the dashboard can distinguish it from
    the regular telemetry broadcast.

    Parameters:
        websocket: The WebSocket connection that sent the load request.
        msg:       Parsed message dict expected to contain 'track_name' (str).

    Returns:
        None.
    """
    track_name = msg.get("track_name", "").strip()
    safe_name  = _safe_track_filename(track_name)
    points: list = []
    if safe_name:
        file_path = TRACK_DATA_DIR / f"{safe_name}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            points = data.get("points", [])
    source = f"({len(points)} pts from file)" if points else "(not found — recording will start)"
    print(f"[TRACK]  Load request for '{track_name}' {source}")
    response = json.dumps({"type": "track_shape", "track_name": track_name, "points": points})
    try:
        await websocket.send(response)
    except websockets.exceptions.ConnectionClosed:
        pass


async def _handle_ws_message(websocket, raw_message: str) -> None:
    """Dispatches an incoming WebSocket message to the appropriate handler.

    Only two message types are expected from the dashboard:
      - 'save_track_shape': persist a canonical track outline to disk
      - 'load_track_shape': retrieve a previously saved outline and send it back

    All other message types and malformed JSON are silently ignored.

    Parameters:
        websocket:   The WebSocket connection that sent the message.
        raw_message: Raw JSON string received from the client.

    Returns:
        None.
    """
    try:
        msg = json.loads(raw_message)
    except json.JSONDecodeError:
        return
    msg_type = msg.get("type")
    if msg_type == "save_track_shape":
        await _save_track_shape(msg)
    elif msg_type == "load_track_shape":
        await _load_track_shape(websocket, msg)


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

def _make_ws_handler(clients: set):
    """Returns a WebSocket handler that registers the connection and handles messages.

    Uses a closure over the shared `clients` set so each new connection is
    tracked globally and included in broadcast rounds.  Incoming messages are
    forwarded to _handle_ws_message so the dashboard can request track shape
    saves and loads without a separate HTTP server.

    Parameters:
        clients: The shared set of active ServerConnection instances.

    Returns:
        An async callable suitable for websockets.serve().
    """
    async def _handler(websocket) -> None:
        """Registers the connection, processes incoming messages, cleans up on close.

        Parameters:
            websocket: The ServerConnection instance for this client.

        Returns:
            None.
        """
        clients.add(websocket)
        addr = websocket.remote_address
        print(f"[WS]   Client connected: {addr}  ({len(clients)} total)")
        try:
            async for message in websocket:
                await _handle_ws_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            clients.discard(websocket)
            print(f"[WS]   Client disconnected: {addr}  ({len(clients)} remaining)")
    return _handler


# ---------------------------------------------------------------------------
# Broadcast loop
# ---------------------------------------------------------------------------

async def _broadcast_loop(
    manager:   RaceStateManager,
    messages:  list,
    clients:   set,
    engineer:  EngineerAI,
) -> None:
    """Pushes a JSON snapshot to all connected dashboard clients every tick.

    Disconnected clients raise ConnectionClosed on send — they are silently
    removed from the set so subsequent ticks skip them.

    Parameters:
        manager:  Live RaceStateManager for building payloads.
        messages: Current engineer message history (newest first).
        clients:  Shared set of active WebSocket connections.
        engineer: Live EngineerAI instance forwarded to _build_payload.

    Returns:
        None (runs until cancelled).
    """
    while True:
        await asyncio.sleep(BROADCAST_INTERVAL_SECONDS)
        if not clients:
            continue

        payload  = _build_payload(manager, messages, engineer)
        json_str = json.dumps(payload)
        dead: set = set()

        for ws in list(clients):
            try:
                await ws.send(json_str)
            except (websockets.exceptions.ConnectionClosed, Exception):
                dead.add(ws)

        clients -= dead


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """Initialises all components and runs the three concurrent tasks.

    Returns:
        None.
    """
    TRACK_DATA_DIR.mkdir(parents=True, exist_ok=True)

    manager  = RaceStateManager()
    engineer = EngineerAI()
    # Wire the session data store reference so engineer can read session summaries
    engineer._session_data_store = manager.session_data_store
    messages: list[dict] = []
    clients:  set        = set()

    _print_banner()

    # Build the UDP socket manually so we can configure it before binding.
    # create_datagram_endpoint(local_addr=...) sets neither SO_BROADCAST nor
    # SO_RCVBUF, which causes two problems on Windows:
    #   SO_BROADCAST absent → broadcast-mode packets from F1 25 are silently dropped
    #   SO_RCVBUF default (~8 KB) → oversized F1 25 datagrams (up to 1352 B) drop when
    #   two arrive simultaneously; 65536 B holds ~40 complete packets as headroom
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_RECV_BUFFER_BYTES)
    udp_sock.bind((UDP_BIND_HOST, UDP_PORT))

    loop = asyncio.get_running_loop()
    transport, udp_protocol = await loop.create_datagram_endpoint(
        lambda: _UDPProtocol(manager),
        sock=udp_sock,
    )
    print(f"[UDP]  Listening on port {UDP_PORT} — waiting for PS5...\n")

    async with websockets.serve(_make_ws_handler(clients), WS_HOST, WS_PORT):
        print(f"[WS]   WebSocket server running on ws://{WS_HOST}:{WS_PORT}\n")
        try:
            await asyncio.gather(
                _engineer_cycle(udp_protocol, manager, engineer, messages),
                _broadcast_loop(manager, messages, clients, engineer),
            )
        except asyncio.CancelledError:
            pass
        finally:
            transport.close()


if __name__ == "__main__":
    # ProactorEventLoop (Windows default) processes one IOCP UDP completion at a
    # time and cannot batch-drain a ready socket. SelectorEventLoop uses select()
    # which drains the socket in a tight loop, eliminating the per-packet overhead
    # that causes stale telemetry data on Windows.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SERVER]  Shut down cleanly.")
