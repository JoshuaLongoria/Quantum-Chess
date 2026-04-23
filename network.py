"""
network.py — LAN discovery and game communication for Quantum Chess.

Phase 1 – Discovery (UDP broadcast, port 5001):
    Both instances broadcast a JSON beacon every second.
    When a peer beacon is heard, roles are assigned by session ID:
        higher ID → server (plays White)
        lower  ID → client (plays Black)

Phase 2 – Gameplay (TCP, port 5000):
    Newline-delimited JSON messages.
    Types sent by main.py:
        {"type": "click",        "square": "e4"}
        {"type": "measure_click","square": "e4", "result": 0}
        {"type": "key",          "mode":   "superposition"}
        {"type": "cancel"}
"""
from __future__ import annotations
import json
import random
import socket
import threading
import time

DISCOVERY_PORT = 5001
GAME_PORT      = 5000
_BROADCAST     = "255.255.255.255"
_GAME_TAG      = "quantum-chess-v1"


def get_local_ip() -> str:
    """Return this machine's LAN IP (the interface that reaches the router)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


class NetworkManager:
    """
    Peer-to-peer LAN manager for Quantum Chess.

    Lifecycle:
        net = NetworkManager()
        net.start_discovery()          # kick off UDP broadcast in background
        # poll net.connected each frame
        net.send({"type": "click", "square": "e4"})
        for msg in net.poll(): ...
        net.stop()
    """

    def __init__(self) -> None:
        self.session_id: int        = random.randint(1, 2 ** 30)
        self.role:       str | None = None      # "server" (White) | "client" (Black)
        self.peer_ip:    str | None = None
        self.connected:  bool       = False
        self.status:     str        = "idle"    # "searching"|"connected"|"error"

        self._conn:      socket.socket | None = None
        self._srv_sock:  socket.socket | None = None
        self._running:   bool  = False
        self._incoming:  list  = []
        self._lock:      threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_discovery(self) -> None:
        """Begin broadcasting and listening for a peer on the LAN."""
        self._running = True
        self.status   = "searching"
        threading.Thread(target=self._broadcast_loop, daemon=True).start()
        threading.Thread(target=self._listen_udp,     daemon=True).start()

    def send(self, msg: dict) -> None:
        """Send a JSON message to the connected peer."""
        if self._conn and self.connected:
            try:
                self._conn.sendall((json.dumps(msg) + "\n").encode())
            except OSError:
                self.connected = False
                self.status    = "error"

    def poll(self) -> list[dict]:
        """Return (and clear) every message received since the last call."""
        with self._lock:
            out, self._incoming = self._incoming[:], []
        return out

    def stop(self) -> None:
        """Shut down all sockets and background threads."""
        self._running  = False
        self.connected = False
        for s in (self._conn, self._srv_sock):
            if s:
                try:
                    s.close()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # UDP discovery
    # ------------------------------------------------------------------

    def _broadcast_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        local_ip = get_local_ip()
        sock.bind((local_ip, 0))  # force broadcast out the WiFi interface
        # subnet broadcast (e.g. 192.168.1.255) is more reliable than 255.255.255.255
        subnet_broadcast = local_ip.rsplit(".", 1)[0] + ".255"
        payload = json.dumps({"tag": _GAME_TAG, "id": self.session_id}).encode()
        while self._running:
            try:
                sock.sendto(payload, (subnet_broadcast, DISCOVERY_PORT))
            except OSError:
                pass
            time.sleep(1.0)
        try:
            sock.close()
        except OSError:
            pass

    def _listen_udp(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", DISCOVERY_PORT))
        except OSError:
            self.status = "error"
            return
        sock.settimeout(1.0)
        while self._running:
            try:
                data, addr = sock.recvfrom(1024)
                msg     = json.loads(data.decode())
                peer_id = int(msg.get("id", 0))
                if msg.get("tag") != _GAME_TAG or peer_id == self.session_id:
                    continue
                # Found a peer — stop broadcasting and open TCP
                self._running = False
                self.peer_ip  = addr[0]
                if self.session_id > peer_id:
                    self.role = "server"
                    threading.Thread(target=self._tcp_accept,
                                     daemon=True).start()
                else:
                    self.role = "client"
                    threading.Thread(target=self._tcp_connect,
                                     args=(addr[0],), daemon=True).start()
            except (socket.timeout, json.JSONDecodeError, ValueError):
                pass
        try:
            sock.close()
        except OSError:
            pass

    # ------------------------------------------------------------------
    # TCP connection
    # ------------------------------------------------------------------

    def _tcp_accept(self) -> None:
        """Server side: open a listening socket and wait for the client."""
        self._srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._srv_sock.bind(("", GAME_PORT))
            self._srv_sock.listen(1)
            self._srv_sock.settimeout(15)
            conn, _ = self._srv_sock.accept()
            self._conn = conn
            self._on_connected()
        except OSError:
            self.status = "error"

    def _tcp_connect(self, host: str) -> None:
        """Client side: connect to the server's TCP socket (retry for ~10 s)."""
        for _ in range(20):
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.settimeout(3)
                conn.connect((host, GAME_PORT))
                self._conn = conn
                self._on_connected()
                return
            except OSError:
                time.sleep(0.5)
        self.status = "error"

    def _on_connected(self) -> None:
        self.connected = True
        self.status    = "connected"
        threading.Thread(target=self._recv_loop, daemon=True).start()

    # ------------------------------------------------------------------
    # Receive loop (runs in background thread)
    # ------------------------------------------------------------------

    def _recv_loop(self) -> None:
        buf = ""
        while self.connected:
            try:
                chunk = self._conn.recv(4096)
                if not chunk:
                    break
                buf += chunk.decode()
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            with self._lock:
                                self._incoming.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            except OSError:
                break
        self.connected = False
        self.status    = "error"
