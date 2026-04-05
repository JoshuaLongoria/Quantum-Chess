# State panel, move history, quantum event log
# This module defines the draw_hud function which renders the right-side panel
# showing the current quantum state of the game, including superpositions,
import pygame
import math
from constants import *


def draw_hud(screen: pygame.Surface, pieces: list[dict], tick: int):
    """
    Draw the Quantum State HUD panel on the right side of the screen.
 
    The HUD shows:
      - Current turn (White / Black)
      - List of pieces currently in superposition with their two positions
      - List of currently entangled piece pairs
      - Latest quantum event log entry (e.g. "Knight collapsed to e4")
 
    This panel is what makes the quantum state visible and understandable
    to the audience during your presentation.
 
    Args:
        screen: Main display surface.
        pieces: List of all piece dicts (from game_manager).
        tick: Current frame count for animations.
    """
    # --- HUD background panel -------------------------------------------

    hud_x = BOARD_OFFSET_X + BOARD_PX + 20
    hud_y = BOARD_OFFSET_Y
    hud_h = BOARD_PX
 
    # Panel background
    hud_rect = pygame.Rect(hud_x, hud_y, HUD_WIDTH - 20, hud_h)
    panel_surf = pygame.Surface((HUD_WIDTH - 20, hud_h), pygame.SRCALPHA)
    panel_surf.fill((*HUD_BG, 230))
    screen.blit(panel_surf, (hud_x, hud_y))
 
    # Panel border
    pygame.draw.rect(screen, HUD_BORDER, hud_rect, width=1, border_radius=6)
 
    # --- Title bar -------------------------------------------------------
    title_bar = pygame.Rect(hud_x, hud_y, HUD_WIDTH - 20, 34)
    pygame.draw.rect(screen, (30, 40, 80), title_bar, border_radius=6)
    title = FONT_HUD_T.render("⟨ψ| QUANTUM STATE |ψ⟩", True, HUD_TITLE)
    screen.blit(title, (hud_x + 10, hud_y + 8))
 
    cursor_y = hud_y + 46   # tracks vertical position as we add HUD elements
 
    def hud_section(label: str):
        """Helper: draw a section label with a subtle divider line."""
        nonlocal cursor_y
        cursor_y += 8
        pygame.draw.line(screen, HUD_BORDER,
                         (hud_x + 8, cursor_y), (hud_x + HUD_WIDTH - 30, cursor_y))
        cursor_y += 4
        lbl = FONT_HUD_T.render(label, True, HUD_TITLE)
        screen.blit(lbl, (hud_x + 10, cursor_y))
        cursor_y += 22
 
    def hud_line(text: str, color=None, indent: int = 10):
        """Helper: draw a single line of HUD body text."""
        nonlocal cursor_y
        color = color or HUD_TEXT
        rendered = FONT_HUD_B.render(text, True, color)
        screen.blit(rendered, (hud_x + indent, cursor_y))
        cursor_y += 18
 
    # --- Section: Superposition -----------------------------------------
    hud_section("SUPERPOSITION")
    superposed = [p for p in pieces if p.get("superposed")]
    if superposed:
        for p in superposed:
            pos_list = " ↔ ".join(p.get("positions", ["?"]))
            symbol = PIECE_SYMBOLS.get((p["type"], p["color"]), "?")
            hud_line(f"  {symbol} {p['color'][:1].upper()} {p['type']}", HUD_SUPERPOSE)
            hud_line(f"    {pos_list}", HUD_TEXT, indent=20)
    else:
        hud_line("  No pieces in superposition", HUD_TEXT)
 
    # --- Section: Entanglement ------------------------------------------
    hud_section("ENTANGLEMENT")
    entangled_pairs = _get_entangled_pairs(pieces)
    if entangled_pairs:
        for pa, pb in entangled_pairs:
            sym_a = PIECE_SYMBOLS.get((pa["type"], pa["color"]), "?")
            sym_b = PIECE_SYMBOLS.get((pb["type"], pb["color"]), "?")
            pos_a = pa.get("positions", ["?"])[0]
            pos_b = pb.get("positions", ["?"])[0]
            # Pulsing color for entanglement entries
            pulse = math.sin(tick * 0.05)
            hud_line(f"  {sym_a}{pos_a} ⟷ {sym_b}{pos_b}", HUD_ENTANGLE)
    else:
        hud_line("  No entangled pairs", HUD_TEXT)
 
    # --- Section: Quantum Event Log ------------------------------------
    hud_section("LAST EVENT")


    # In The final game, pass real event messages from game_manager.
    # For now, these are example placeholder messages.
# ---------------------------------------------------------------------------
#  ***This demo section below is just to show how the HUD will look with some example data.***
# ---------------------------------------------------------------------------
 

    demo_events = [
        "Knight split → e4 ↔ g5",
        "Rook entangled with Bishop",
        "Pawn collapsed → d5",
    ]
    for ev in demo_events[-2:]:   # show last 2 events
        hud_line(f"  {ev}", HUD_ACCENT)
 
    # --- Footer: IBM Quantum status indicator --------------------------

    cursor_y = hud_y + hud_h - 36
    pygame.draw.line(screen, HUD_BORDER,
                     (hud_x + 8, cursor_y), (hud_x + HUD_WIDTH - 30, cursor_y))
    cursor_y += 6
 
    # Pulsing dot to indicate hardware connection status


    pulse = math.sin(tick * 0.08)
    dot_alpha = int(150 + pulse * 80)
    dot_surf = pygame.Surface((12, 12), pygame.SRCALPHA)
    pygame.draw.circle(dot_surf, (*ENTANGLE_COLOR, dot_alpha), (6, 6), 5)
    screen.blit(dot_surf, (hud_x + 10, cursor_y + 2))
    status = FONT_HUD_B.render("IBM Quantum: Aer Simulator", True, HUD_TEXT)
    screen.blit(status, (hud_x + 26, cursor_y + 1))

def _get_entangled_pairs(pieces: list[dict]) -> list[tuple]:
    """
    Extract unique entangled pairs from the piece list.
 
    Each piece stores a list of qubit_ids it's entangled with.
    We return pairs (piece_a, piece_b) without duplicates.
 
    Args:
        pieces: Full list of piece dicts.
 
    Returns:
        List of (piece_a, piece_b) tuples.
    """
    qubit_map = {p["qubit_id"]: p for p in pieces if "qubit_id" in p}
    seen = set()
    pairs = []
    for piece in pieces:
        for partner_id in piece.get("entangled_with", []):
            pair_key = tuple(sorted([piece["qubit_id"], partner_id]))
            if pair_key not in seen and partner_id in qubit_map:
                seen.add(pair_key)
                pairs.append((piece, qubit_map[partner_id]))
    return pairs

 



 