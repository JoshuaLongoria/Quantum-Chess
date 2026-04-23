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
import sys

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
def get_broadcast_address() -> str:
    """
    Get the subnet broadcast address for this machine.
    
    On most networks, this is the local IP with the last octet changed to 255.
    E.g., 192.168.1.100 → 192.168.1.255
    """
    try:
        ip = get_local_ip()
        if ip == "127.0.0.1":
            return "255.255.255.255"
        parts = ip.split(".")
        parts[-1] = "255"
        broadcast = ".".join(parts)
        print(f"[Network] Local IP: {ip} → Broadcast: {broadcast}")
        return broadcast
    except Exception:
        return "255.255.255.255"

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

        self._broadcast_running = False
        self._listen_running = False
        self._incoming:  list  = []
        self._lock:      threading.Lock = threading.Lock()
        
        self._broadcast_address = get_broadcast_address()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_discovery(self) -> None:
         """Begin broadcasting and listening for a peer on the LAN."""
         print(f"[Network] Starting discovery (session ID: {self.session_id})")
         self._broadcast_running = True
         self._listen_running = True
         self.status = "searching"
         threading.Thread(target=self._broadcast_loop, daemon=True).start()
         threading.Thread(target=self._listen_udp, daemon=True).start()

    def send(self, msg: dict) -> None:
        """Send a JSON message to the connected peer."""
        if self._conn and self.connected:
            try:
                self._conn.sendall((json.dumps(msg) + "\n").encode())
            except OSError as e:
                print(f"[Network] Send failed: {e}")
                self.connected = False
                self.status    = "error"

    def poll(self) -> list[dict]:
        """Return (and clear) every message received since the last call."""
        with self._lock:
            out, self._incoming = self._incoming[:], []
        return out

    def stop(self) -> None:
        """Shut down all sockets and background threads."""
        print("[Network] Stopping...")
        self._broadcast_running = False
        self._listen_running = False
        self.connected = False
        for s in (self._conn, self._srv_sock, self._broadcast_sock, self._listen_sock):
            if s:
                try:
                    s.close()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # UDP discovery
    # ------------------------------------------------------------------

    def _broadcast_loop(self) -> None:
        """Broadcast our beacon every second."""
        self._broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        payload = json.dumps({"tag": _GAME_TAG, "id": self.session_id}).encode()
        
        while self._broadcast_running:
            try:
                self._broadcast_sock.sendto(payload, (self._broadcast_address, DISCOVERY_PORT))
            except OSError as e:
                print(f"[Network] Broadcast error: {e}")
            time.sleep(1.0)
        
        try:
            self._broadcast_sock.close()
        except OSError:
            pass
        print("[Network] Broadcast loop stopped")

 
    def _listen_udp(self) -> None:
        """Listen for peer beacons."""
        self._listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Windows-specific: exclusive address use for immediate port rebind
        if sys.platform == "win32":
            try:
                self._listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except (OSError, AttributeError):
                pass
        
        try:
            self._listen_sock.bind(("0.0.0.0", DISCOVERY_PORT))
            print(f"[Network] Listening for UDP beacons on port {DISCOVERY_PORT}")
        except OSError as e:
            print(f"[Network] UDP bind failed: {e}")
            self.status = "error"
            self._listen_running = False
            return
        
        self._listen_sock.settimeout(1.0)
        
        while self._listen_running:
            try:
                data, addr = self._listen_sock.recvfrom(1024)
                msg = json.loads(data.decode())
                peer_id = int(msg.get("id", 0))
                
                # Ignore own beacons and wrong game beacons
                if msg.get("tag") != _GAME_TAG or peer_id == self.session_id:
                    continue
                print(f"[Network] Found peer: {addr[0]} (ID: {peer_id}, mine: {self.session_id})")
                
                # Stop broadcasting and listening
                self._listen_running = False
                self._broadcast_running = False
                self.peer_ip = addr[0]
                
                # Assign roles by session ID
                if self.session_id > peer_id:
                    self.role = "server"
                    print("[Network] ✓ I am SERVER (White) — waiting for client connection")
                    threading.Thread(target=self._tcp_accept, daemon=True).start()
                else:
                    self.role = "client"
                    print(f"[Network] ✓ I am CLIENT (Black) — connecting to {addr[0]}")
                    threading.Thread(target=self._tcp_connect, args=(addr[0],), daemon=True).start()
            
            except socket.timeout:
                pass
            except (json.JSONDecodeError, ValueError) as e:
                pass
        
        try:
            self._listen_sock.close()
        except OSError:
            pass
        print("[Network] Listen loop stopped")

    # ------------------------------------------------------------------
    # TCP connection
    # ------------------------------------------------------------------

    def _tcp_accept(self) -> None:
        """Server side: open a listening socket and wait for the client."""
        self._srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        if sys.platform == "win32":
            try:
                self._srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except (OSError, AttributeError):
                pass
        
        try:
            self._srv_sock.bind(("0.0.0.0", GAME_PORT))
            print(f"[Network] Server: listening on 0.0.0.0:{GAME_PORT}")
            self._srv_sock.listen(1)
            self._srv_sock.settimeout(30)  # 30 second timeout
            
            conn, addr = self._srv_sock.accept()
            print(f"[Network] Server: client connected from {addr}")
            self._conn = conn
            self._on_connected()
        except socket.timeout:
            print("[Network] Server: timeout waiting for client (30s)")
            self.status = "error"
        except OSError as e:
            print(f"[Network] Server: error - {e}")
            self.status = "error"
 
    def _tcp_connect(self, host: str) -> None:
        """Client side: connect to the server's TCP socket (retry for ~10s)."""
        max_attempts = 20
        
        for attempt in range(max_attempts):
            try:
                print(f"[Network] Client: attempt {attempt + 1}/{max_attempts} to connect to {host}:{GAME_PORT}")
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.settimeout(3)
                conn.connect((host, GAME_PORT))
                print(f"[Network] Client: ✓ connected on attempt {attempt + 1}")
                self._conn = conn
                self._on_connected()
                return
            except OSError as e:
                print(f"[Network] Client: attempt {attempt + 1} failed - {e}")
                time.sleep(0.5)
        
        print("[Network] Client: all connection attempts failed")
        self.status = "error"
 
    def _on_connected(self) -> None:
        self.connected = True
        self.status = "connected"
        print("[Network] ✓ CONNECTED!")
        threading.Thread(target=self._recv_loop, daemon=True).start()
 
    # ------------------------------------------------------------------
    # Receive loop (runs in background thread)
    # ------------------------------------------------------------------
 
    def _recv_loop(self) -> None:
        """Read messages from the peer."""
        buf = ""
        while self.connected:
            try:
                chunk = self._conn.recv(4096)
                if not chunk:
                    print("[Network] Peer closed connection")
                    break
                buf += chunk.decode()
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            with self._lock:
                                self._incoming.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            print(f"[Network] JSON decode error: {e}")
            except OSError as e:
                print(f"[Network] Recv error: {e}")
                break
        
        self.connected = False
        self.status = "error"
        print("[Network] Recv loop stopped")
