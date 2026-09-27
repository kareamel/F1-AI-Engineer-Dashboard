"""
Phase 1 — UDP Listener
Responsible for: opening a UDP socket on port 20777, receiving raw telemetry
packets broadcast by F1 25 (PS5) on the local network, and printing a
one-line summary for each packet to confirm data is arriving.
This is a standalone diagnostic script. No parsing or AI logic lives here.
"""

import socket
import datetime

from f1 import packets


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# F1 25 broadcasts telemetry on this port — must match the in-game UDP settings
UDP_PORT = 20777

# Largest F1 25 packet is well under 2 KB; 4096 gives comfortable headroom
BUFFER_SIZE = 4096

# Byte index of packet_id inside every PacketHeader struct
PACKET_ID_OFFSET = 6

# strftime format for the per-packet timestamp column
TIMESTAMP_FORMAT = "%H:%M:%S.%f"

# Width of the source IP column in the printed output
SOURCE_IP_COLUMN_WIDTH = 15

# Width of the packet size column in the printed output
PACKET_SIZE_COLUMN_WIDTH = 5


# ---------------------------------------------------------------------------
# Packet ID lookup table  (F1 25 / 2025 UDP spec)
# ---------------------------------------------------------------------------

PACKET_NAMES = {
    0:  "Motion",
    1:  "Session",
    2:  "Lap Data",
    3:  "Event",
    4:  "Participants",
    5:  "Car Setups",
    6:  "Car Telemetry",
    7:  "Car Status",
    8:  "Final Classification",
    9:  "Lobby Info",
    10: "Car Damage",
    11: "Session History",
    12: "Tyre Sets",
    13: "Motion Ex",
    14: "Time Trial",
    15: "Lap Positions",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_local_ip() -> str:
    """Returns this machine's LAN IP address.

    Briefly connects to an external address (no data is sent) so the OS
    selects the correct outbound network interface and reveals its IP.

    Returns:
        The local IPv4 address as a string, e.g. '192.168.1.42'.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe_socket:
        probe_socket.connect(("8.8.8.8", 80))
        return probe_socket.getsockname()[0]


def identify_packet(raw_data: bytes) -> str:
    """Reads the packet_id byte from a raw F1 25 packet and returns its name.

    Parameters:
        raw_data: The raw UDP payload bytes received from the PS5.

    Returns:
        A human-readable packet type name, e.g. 'Car Telemetry'.
        Returns a descriptive fallback string for unknown or truncated packets.
    """
    if len(raw_data) <= PACKET_ID_OFFSET:
        return "Unknown (too short)"
    packet_id = raw_data[PACKET_ID_OFFSET]
    return PACKET_NAMES.get(packet_id, f"Unknown (id={packet_id})")


# ---------------------------------------------------------------------------
# Socket setup and receive loop  (split to keep each function under 20 lines)
# ---------------------------------------------------------------------------

def _create_socket() -> socket.socket:
    """Creates, configures, and binds the UDP socket for receiving telemetry.

    Binds to all interfaces so packets are received from the PS5 regardless
    of which network adapter is active on this machine.

    Returns:
        A bound, ready-to-receive UDP socket.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", UDP_PORT))
    return udp_socket


def _run_receive_loop(udp_socket: socket.socket) -> None:
    """Continuously receives packets and prints a one-line summary for each.

    Runs until the user presses Ctrl+C.

    Parameters:
        udp_socket: A bound UDP socket ready to receive data.
    """
    try:
        while True:
            raw_data, (source_ip, _) = udp_socket.recvfrom(BUFFER_SIZE)
            timestamp = datetime.datetime.now().strftime(TIMESTAMP_FORMAT)[:-3]
            packet_type = identify_packet(raw_data)
            packet_size = len(raw_data)
            print(
                f"[{timestamp}]  "
                f"{source_ip:<{SOURCE_IP_COLUMN_WIDTH}}  "
                f"{packet_size:>{PACKET_SIZE_COLUMN_WIDTH}} bytes  |  "
                f"{packet_type}"
            )
    except KeyboardInterrupt:
        print("\nListener stopped. See you on the grid.")
    finally:
        udp_socket.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Opens the UDP socket, prints startup info, and starts the receive loop.

    Designed to be run directly: venv\\Scripts\\python.exe src\\listener.py
    """
    udp_socket = _create_socket()
    local_ip = get_local_ip()
    print("F1 Engineer — Phase 1 UDP Listener")
    print(f"Listening on {local_ip}:{UDP_PORT}")
    print("Waiting for packets from F1 25 (PS5)...")
    print("Press Ctrl+C to stop.\n")
    _run_receive_loop(udp_socket)


if __name__ == "__main__":
    main()
