"""
lobby.py — Pre-game lobby screen for Quantum Chess.

Three choices:
    LOCAL  → 2-player on the same machine (no network).
    HOST   → Open a TCP server on port 5000, display your IP; partner clicks JOIN.
    JOIN   → Type the host's IP and connect directly.

HOST/JOIN bypasses UDP broadcast entirely and works on any network
(home WiFi, phone hotspot, university LAN with AP isolation, etc.).

Call pattern (from main.py):
    lobby = LobbyScreen()
    while True:
        for event in pygame.event.get():
            lobby.handle_event(event)
        result = lobby.update()
        if result:
            break       # {"mode": "local"}  or
                        # {"mode": "lan", "network": NetworkManager}
        lobby.render(screen, tick)
        pygame.display.flip()
        clock.tick(60)
"""
from __future__ import annotations
import math
import pygame
from constants import WINDOW_WIDTH, WINDOW_HEIGHT
from network import NetworkManager, get_local_ip

pygame.font.init()
_F_TITLE  = pygame.font.SysFont("consolas, monospace", 44, bold=True)
_F_BTN    = pygame.font.SysFont("consolas, monospace", 22, bold=True)
_F_SUB    = pygame.font.SysFont("consolas, monospace", 15)
_F_SMALL  = pygame.font.SysFont("consolas, monospace", 13)
_F_IP     = pygame.font.SysFont("consolas, monospace", 28, bold=True)

_TEAL  = (58,  207, 180)
_DARK  = (33,   41,  34)
_WHITE = (230, 240, 235)
_GREY  = (100, 120, 110)
_GREEN = (60,  200, 120)
_RED   = (180,  60,  60)
_BLUE  = (35,   90, 160)
_GOLD  = (220, 180,  50)


class _Btn:
    def __init__(self, cx: int, cy: int, w: int, h: int,
                 label: str, color: tuple) -> None:
        self.rect  = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        self.label = label
        self.color = color

    def draw(self, screen: pygame.Surface) -> None:
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        col   = tuple(min(255, v + 28) for v in self.color) if hover else self.color
        pygame.draw.rect(screen, col,    self.rect, border_radius=10)
        pygame.draw.rect(screen, _WHITE, self.rect, width=2, border_radius=10)
        surf = _F_BTN.render(self.label, True, _WHITE)
        screen.blit(surf, (self.rect.centerx - surf.get_width()  // 2,
                           self.rect.centery - surf.get_height() // 2))

    def hit(self, pos: tuple) -> bool:
        return self.rect.collidepoint(pos)


class _IPInput:
    """Single-line text box for IP address entry."""

    def __init__(self, cx: int, cy: int, w: int, h: int) -> None:
        self.rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        self.text = ""

    def handle_key(self, event: pygame.event.Event) -> bool:
        """Handle a KEYDOWN event. Returns True if Enter was pressed."""
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return True
        elif len(self.text) < 15:           # "255.255.255.255" = 15 chars
            ch = event.unicode
            if ch in "0123456789.":
                self.text += ch
        return False

    def draw(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, (50, 70, 60), self.rect, border_radius=6)
        pygame.draw.rect(screen, _TEAL,        self.rect, width=2, border_radius=6)
        display = self.text if self.text else "type host IP here…"
        color   = _WHITE    if self.text else _GREY
        surf = _F_BTN.render(display, True, color)
        screen.blit(surf, (self.rect.x + 12,
                           self.rect.centery - surf.get_height() // 2))


class LobbyScreen:
    """
    State machine:
        "menu"        — LOCAL / LAN buttons
        "lan_menu"    — HOST / JOIN / Back
        "hosting"     — TCP server running, displays local IP
        "entering_ip" — IP text input for joining
        "connecting"  — TCP client connecting to host
        "error"       — connection failed, Back to lan_menu
    """

    def __init__(self) -> None:
        self._state:    str               = "menu"
        self.net:       NetworkManager | None = None
        self._err_msg:  str               = ""
        self._local_ip: str               = get_local_ip()

        cx = WINDOW_WIDTH  // 2
        cy = WINDOW_HEIGHT // 2

        # menu
        self._btn_local = _Btn(cx, cy - 48, 270, 52, "LOCAL  (same machine)", (38, 100, 65))
        self._btn_lan   = _Btn(cx, cy + 24, 270, 52, "LAN    (find player)",  _BLUE)

        # lan_menu
        self._btn_host  = _Btn(cx, cy - 52, 280, 52, "HOST  (wait for partner)", _BLUE)
        self._btn_join  = _Btn(cx, cy + 20, 280, 52, "JOIN  (enter host IP)",    (38, 100, 65))
        self._btn_back  = _Btn(cx, cy + 92, 160, 40, "Back", _RED)

        # entering_ip
        self._ip_input    = _IPInput(cx, cy - 10, 290, 44)
        self._btn_connect = _Btn(cx, cy + 54, 180, 44, "Connect", _GREEN)

        # shared cancel (hosting / entering_ip / connecting)
        self._btn_cancel = _Btn(cx, cy + 130, 160, 40, "Cancel", _RED)

        # error
        self._btn_err_back = _Btn(cx, cy + 70, 160, 40, "Back", _RED)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        # Resolve mouse position only for click events
        pos = event.pos if event.type == pygame.MOUSEBUTTONDOWN else None

        if self._state == "menu":
            if pos:
                if self._btn_local.hit(pos):
                    self._state = "_local_ready"
                elif self._btn_lan.hit(pos):
                    self._state = "lan_menu"

        elif self._state == "lan_menu":
            if pos:
                if self._btn_host.hit(pos):
                    self._start_host()
                elif self._btn_join.hit(pos):
                    self._ip_input.text = ""
                    self._state = "entering_ip"
                elif self._btn_back.hit(pos):
                    self._state = "menu"

        elif self._state == "hosting":
            if pos and self._btn_cancel.hit(pos):
                self._cancel()

        elif self._state == "entering_ip":
            if event.type == pygame.KEYDOWN:
                if self._ip_input.handle_key(event):
                    self._try_connect()
            elif pos:
                if self._btn_connect.hit(pos):
                    self._try_connect()
                elif self._btn_cancel.hit(pos):
                    self._state = "lan_menu"

        elif self._state == "connecting":
            if pos and self._btn_cancel.hit(pos):
                self._cancel()

        elif self._state == "error":
            if pos and self._btn_err_back.hit(pos):
                self._state = "lan_menu"

    def update(self) -> dict | None:
        """
        Call once per frame.
        Returns None while waiting; returns a result dict when ready:
            {"mode": "local"}
            {"mode": "lan", "network": NetworkManager}
        """
        if self._state == "_local_ready":
            return {"mode": "local"}

        if self._state in ("hosting", "connecting") and self.net:
            if self.net.connected:
                return {"mode": "lan", "network": self.net}
            if self.net.status == "error":
                self._err_msg = "Connection failed — check the IP and that both machines are on the same network."
                self._state   = "error"
                self.net.stop()
                self.net = None

        return None

    def render(self, screen: pygame.Surface, tick: int) -> None:
        screen.fill(_DARK)
        cx = WINDOW_WIDTH // 2

        # Title
        t1 = _F_TITLE.render("QUANTUM", True, _TEAL)
        t2 = _F_TITLE.render("CHESS",   True, _WHITE)
        screen.blit(t1, (cx - t1.get_width() // 2, 108))
        screen.blit(t2, (cx - t2.get_width() // 2, 158))
        sub = _F_SUB.render(
            "ψ  superposition · entanglement · collapse  ψ", True, _GREY)
        screen.blit(sub, (cx - sub.get_width() // 2, 214))

        # State-specific content
        if self._state in ("menu", "_local_ready"):
            self._btn_local.draw(screen)
            self._btn_lan.draw(screen)

        elif self._state == "lan_menu":
            self._render_lan_menu(screen, cx)

        elif self._state == "hosting":
            self._render_hosting(screen, cx, tick)

        elif self._state == "entering_ip":
            self._render_entering_ip(screen, cx)

        elif self._state == "connecting":
            self._render_connecting(screen, cx, tick)

        elif self._state == "error":
            # word-wrap if message is too long
            err = _F_SMALL.render(self._err_msg, True, _RED)
            screen.blit(err, (cx - err.get_width() // 2,
                              WINDOW_HEIGHT // 2 - 60))
            self._btn_err_back.draw(screen)

    # ------------------------------------------------------------------
    # Private render helpers
    # ------------------------------------------------------------------

    def _render_lan_menu(self, screen: pygame.Surface, cx: int) -> None:
        cy = WINDOW_HEIGHT // 2
        label = _F_BTN.render("Choose your role:", True, _WHITE)
        screen.blit(label, (cx - label.get_width() // 2, cy - 100))
        self._btn_host.draw(screen)
        self._btn_join.draw(screen)
        self._btn_back.draw(screen)

    def _render_hosting(self, screen: pygame.Surface, cx: int, tick: int) -> None:
        cy = WINDOW_HEIGHT // 2

        n_dots = (tick // 20) % 4
        label  = _F_BTN.render("Waiting for partner" + "." * n_dots, True, _TEAL)
        screen.blit(label, (cx - label.get_width() // 2, cy - 90))

        # Prominent IP display
        ip_surf = _F_IP.render(self._local_ip, True, _GOLD)
        screen.blit(ip_surf, (cx - ip_surf.get_width() // 2, cy - 50))

        hint = _F_SMALL.render(
            "Tell your partner to click JOIN and enter this IP address.", True, _GREY)
        screen.blit(hint, (cx - hint.get_width() // 2, cy - 10))

        port_hint = _F_SMALL.render(f"(TCP port {5000})", True, _GREY)
        screen.blit(port_hint, (cx - port_hint.get_width() // 2, cy + 12))

        # Pulsing ring below hints
        pulse = math.sin(tick * 0.07)
        r     = int(22 + pulse * 5)
        alpha = int(130 + pulse * 80)
        ring  = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*_TEAL, alpha), (40, 40), r, width=3)
        screen.blit(ring, (cx - 40, cy + 36))

        self._btn_cancel.draw(screen)

    def _render_entering_ip(self, screen: pygame.Surface, cx: int) -> None:
        cy = WINDOW_HEIGHT // 2
        label = _F_BTN.render("Enter the host's IP address:", True, _WHITE)
        screen.blit(label, (cx - label.get_width() // 2, cy - 70))
        self._ip_input.draw(screen)
        self._btn_connect.draw(screen)
        self._btn_cancel.draw(screen)

    def _render_connecting(self, screen: pygame.Surface, cx: int, tick: int) -> None:
        cy = WINDOW_HEIGHT // 2
        n_dots = (tick // 20) % 4
        label  = _F_BTN.render("Connecting" + "." * n_dots, True, _TEAL)
        screen.blit(label, (cx - label.get_width() // 2, cy - 60))

        if self.net and self.net.peer_ip:
            hint = _F_SMALL.render(f"→ {self.net.peer_ip}:{5000}", True, _GREY)
            screen.blit(hint, (cx - hint.get_width() // 2, cy - 24))

        pulse = math.sin(tick * 0.07)
        r     = int(22 + pulse * 5)
        alpha = int(130 + pulse * 80)
        ring  = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*_TEAL, alpha), (40, 40), r, width=3)
        screen.blit(ring, (cx - 40, cy + 10))

        self._btn_cancel.draw(screen)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _start_host(self) -> None:
        self._state     = "hosting"
        self._local_ip  = get_local_ip()   # refresh in case interface changed
        self.net        = NetworkManager()
        self.net.start_host()

    def _try_connect(self) -> None:
        ip = self._ip_input.text.strip()
        if not ip:
            return
        self._state = "connecting"
        self.net    = NetworkManager()
        self.net.start_join(ip)

    def _cancel(self) -> None:
        if self.net:
            self.net.stop()
            self.net = None
        self._state = "lan_menu"
