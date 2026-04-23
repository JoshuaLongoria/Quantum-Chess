"""
lobby.py — Pre-game lobby screen for Quantum Chess.

Two choices:
    LOCAL  → 2-player on the same machine (original behaviour, no network).
    LAN    → Discover a peer on the LAN via UDP broadcast, then connect.

Call pattern (from main.py):
    lobby = LobbyScreen()
    while True:
        for event in pygame.event.get():
            lobby.handle_event(event)
        result = lobby.update()
        if result:
            break           # result is {"mode":"local"} or
                            #           {"mode":"lan","network":NetworkManager}
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
_F_TITLE = pygame.font.SysFont("consolas, monospace", 44, bold=True)
_F_BTN   = pygame.font.SysFont("consolas, monospace", 22, bold=True)
_F_SUB   = pygame.font.SysFont("consolas, monospace", 15)
_F_SMALL = pygame.font.SysFont("consolas, monospace", 13)
_F_ROLE  = pygame.font.SysFont("consolas, monospace", 20, bold=True)

_TEAL  = (58,  207, 180)
_DARK  = (33,  41,  34)
_WHITE = (230, 240, 235)
_GREY  = (100, 120, 110)
_GREEN = (60,  200, 120)
_RED   = (180,  60,  60)
_BLUE  = (35,   90, 160)


class _Btn:
    """Simple pygame button with hover highlight."""

    def __init__(self, cx: int, cy: int, w: int, h: int,
                 label: str, color: tuple) -> None:
        self.rect  = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        self.label = label
        self.color = color

    def draw(self, screen: pygame.Surface) -> None:
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        col   = tuple(min(255, v + 28) for v in self.color) if hover else self.color
        pygame.draw.rect(screen, col,   self.rect, border_radius=10)
        pygame.draw.rect(screen, _WHITE, self.rect, width=2, border_radius=10)
        surf = _F_BTN.render(self.label, True, _WHITE)
        screen.blit(surf, (self.rect.centerx - surf.get_width()  // 2,
                           self.rect.centery - surf.get_height() // 2))

    def hit(self, pos: tuple) -> bool:
        return self.rect.collidepoint(pos)


class LobbyScreen:
    """
    Manages the pre-game lobby.

    States:
        "menu"      — showing LOCAL / LAN buttons
        "searching" — UDP broadcast running, waiting for peer
        "error"     — connection attempt failed
    """

    def __init__(self) -> None:
        self._state:    str              = "menu"
        self.net:       NetworkManager | None = None
        self._err_msg:  str              = ""
        self._local_ip: str              = get_local_ip()

        cx = WINDOW_WIDTH  // 2
        cy = WINDOW_HEIGHT // 2

        self._btn_local  = _Btn(cx, cy - 48, 270, 52,
                                "LOCAL  (same machine)", (38, 100, 65))
        self._btn_lan    = _Btn(cx, cy + 24, 270, 52,
                                "LAN    (find player)",  _BLUE)
        self._btn_cancel = _Btn(cx, cy + 114, 160, 40, "Cancel", _RED)
        self._btn_back   = _Btn(cx, cy +  60, 160, 40, "Back",   _RED)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        pos = event.pos
        if self._state == "menu":
            if self._btn_local.hit(pos):
                self._state = "_local_ready"
            elif self._btn_lan.hit(pos):
                self._start_lan()
        elif self._state == "searching":
            if self._btn_cancel.hit(pos):
                self._cancel()
        elif self._state == "error":
            if self._btn_back.hit(pos):
                self._state = "menu"

    def update(self) -> dict | None:
        """
        Call once per frame.
        Returns None while waiting; returns a result dict when ready:
            {"mode": "local"}
            {"mode": "lan", "network": NetworkManager}
        """
        if self._state == "_local_ready":
            return {"mode": "local"}

        if self._state == "searching" and self.net:
            if self.net.connected:
                return {"mode": "lan", "network": self.net}
            if self.net.status == "error":
                self._err_msg = "Connection failed — check firewall / same network."
                self._state   = "error"
                self.net.stop()
                self.net = None

        return None

    def render(self, screen: pygame.Surface, tick: int) -> None:
        screen.fill(_DARK)
        cx = WINDOW_WIDTH // 2

        # ── Title ──────────────────────────────────────────────────────
        t1 = _F_TITLE.render("QUANTUM", True, _TEAL)
        t2 = _F_TITLE.render("CHESS",   True, _WHITE)
        screen.blit(t1, (cx - t1.get_width() // 2, 108))
        screen.blit(t2, (cx - t2.get_width() // 2, 158))
        sub = _F_SUB.render(
            "ψ  superposition · entanglement · collapse  ψ", True, _GREY)
        screen.blit(sub, (cx - sub.get_width() // 2, 214))

        # ── State-specific content ─────────────────────────────────────
        if self._state in ("menu", "_local_ready"):
            self._btn_local.draw(screen)
            self._btn_lan.draw(screen)

        elif self._state == "searching":
            self._render_searching(screen, cx, tick)

        elif self._state == "error":
            err = _F_BTN.render(self._err_msg, True, _RED)
            screen.blit(err, (cx - err.get_width() // 2,
                              WINDOW_HEIGHT // 2 - 50))
            self._btn_back.draw(screen)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render_searching(self, screen: pygame.Surface,
                          cx: int, tick: int) -> None:
        cy = WINDOW_HEIGHT // 2

        # Animated "Searching…" label
        n_dots  = (tick // 20) % 4
        dots    = "." * n_dots + " " * (3 - n_dots)
        label   = _F_BTN.render(f"Searching for players{dots}", True, _TEAL)
        screen.blit(label, (cx - label.get_width() // 2, cy - 80))

        # Local IP hint
        hint = _F_SMALL.render(
            f"Your IP: {self._local_ip}  —  both players must be on the same WiFi",
            True, _GREY)
        screen.blit(hint, (cx - hint.get_width() // 2, cy - 48))

        # Pulsing ring
        pulse = math.sin(tick * 0.07)
        r     = int(30 + pulse * 7)
        alpha = int(140 + pulse * 90)
        ring  = pygame.Surface((120, 120), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*_TEAL, alpha), (60, 60), r, width=3)
        screen.blit(ring, (cx - 60, cy - 12))

        self._btn_cancel.draw(screen)

    def _start_lan(self) -> None:
        self._state = "searching"
        self.net    = NetworkManager()
        self.net.start_discovery()

    def _cancel(self) -> None:
        if self.net:
            self.net.stop()
            self.net = None
        self._state = "menu"
