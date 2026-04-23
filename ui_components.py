# State panel, move history, quantum event log
# This module defines the draw_hud function which renders the right-side panel
# showing the current quantum state of the game, including superpositions,
import pygame
import math
from constants import *

def get_forfeit_button_rect():
    hud_x = BOARD_OFFSET_X + BOARD_PX + 20
    hud_y = BOARD_OFFSET_Y
    hud_h = BOARD_PX
    btn_w = 180
    btn_h = 42
    btn_x = hud_x + 35
    btn_y = hud_y + hud_h - 90

    return pygame.Rect(btn_x, btn_y, btn_w, btn_h)

def draw_forfeit_button(screen: pygame.Surface, current_turn: str):
    rect = get_forfeit_button_rect()
    pygame.draw.rect(screen, (170, 40, 40), rect, border_radius=8)
    pygame.draw.rect(screen, (235, 90, 90), rect, width=2, border_radius=8)

    label = FONT_HUD_T.render(
        f"Forfeit ({current_turn.capitalize()})",
        True,
        (255, 255, 255)
    )
    lx = rect.x + rect.width // 2 - label.get_width() // 2
    ly = rect.y + rect.height // 2 - label.get_height() // 2
    screen.blit(label, (lx, ly))

def get_restart_button_rect():
    hud_x = BOARD_OFFSET_X + BOARD_PX + 20
    hud_y = BOARD_OFFSET_Y
    hud_h = BOARD_PX

    btn_w = 180
    btn_h = 42
    btn_x = hud_x + 35
    btn_y = hud_y + hud_h - 140

    return pygame.Rect(btn_x, btn_y, btn_w, btn_h)

def get_quit_button_rect():
    hud_x = BOARD_OFFSET_X + BOARD_PX + 20
    hud_y = BOARD_OFFSET_Y
    hud_h = BOARD_PX

    btn_w = 180
    btn_h = 42
    btn_x = hud_x + 35
    btn_y = hud_y + hud_h - 90

    return pygame.Rect(btn_x, btn_y, btn_w, btn_h)

def draw_restart_button(screen: pygame.Surface):
    rect = get_restart_button_rect()
    pygame.draw.rect(screen, (185, 150, 35), rect, border_radius=8)
    pygame.draw.rect(screen, (240, 210, 90), rect, width=2, border_radius=8)

    label = FONT_HUD_T.render("Restart", True, (20, 20, 20))
    lx = rect.x + rect.width // 2 - label.get_width() // 2
    ly = rect.y + rect.height // 2 - label.get_height() // 2
    screen.blit(label, (lx, ly))

def draw_quit_button(screen: pygame.Surface):
    rect = get_quit_button_rect()
    pygame.draw.rect(screen, (170, 40, 40), rect, border_radius=8)
    pygame.draw.rect(screen, (235, 90, 90), rect, width=2, border_radius=8)

    label = FONT_HUD_T.render("Quit", True, (255, 255, 255))
    lx = rect.x + rect.width // 2 - label.get_width() // 2
    ly = rect.y + rect.height // 2 - label.get_height() // 2
    screen.blit(label, (lx, ly))

# This is where you will implement the draw_hud() function that renders the
# Quantum State HUD panel on the right side of the screen. This panel is crucial
def draw_hud(screen: pygame.Surface, pieces: list[dict], tick: int, event_log=None, backend_label: str = "Simulator (local)", current_turn: str = "white", game_result: str = ""):
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
    pygame.draw.rect(screen, HUD_BORDER, hud_rect, width=2, border_radius=6)
 
    # --- Title bar -------------------------------------------------------
    title_bar = pygame.Rect(hud_x, hud_y, HUD_WIDTH - 20, 34)
    pygame.draw.rect(screen, (58, 207, 180), title_bar, border_radius=6)
    title = FONT_HUD_T.render("ψ| QUANTUM STATE |ψ", True, HUD_TITLE)
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

    def hud_wrapped(text: str, color=None, indent: int = 10):
        """Helper: draw HUD text wrapped to fit inside the panel."""
        nonlocal cursor_y
        color = color or HUD_TEXT
        max_width = HUD_WIDTH - 20 - indent - 8
        words = text.split()
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if FONT_HUD_B.size(test)[0] <= max_width:
                line = test
            else:
                if line:
                    rendered = FONT_HUD_B.render(line, True, color)
                    screen.blit(rendered, (hud_x + indent, cursor_y))
                    cursor_y += 16
                line = word
        if line:
            rendered = FONT_HUD_B.render(line, True, color)
            screen.blit(rendered, (hud_x + indent, cursor_y))
            cursor_y += 16
            
    # --- Display Controls -----------------------------------------
    hud_section("CONTROLS")
    hud_line("Q = Superposition", HUD_ACCENT)
    hud_line("E = Entangle", HUD_ACCENT)
    hud_line("M = Measure", HUD_ACCENT)
    hud_line("Esc = Cancel mode", HUD_ACCENT)
    hud_wrapped("Superposition: select a piece, then choose 2 legal squares.", HUD_TEXT)
    hud_wrapped("Entangle: select 2 friendly pieces to link them.", HUD_TEXT)
 
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
    events = event_log[-5:] if event_log else []
    for ev in events:
        hud_wrapped(f"  {ev}", HUD_ACCENT)

    if game_result:
        hud_section("RESULT")
        hud_wrapped(game_result, HUD_ACCENT)

        draw_restart_button(screen)
        draw_quit_button(screen)
    else:
        draw_forfeit_button(screen, current_turn)
 
    # --- Footer: IBM Quantum status indicator --------------------------

    cursor_y = hud_y + hud_h - 36
    pygame.draw.line(screen, HUD_BORDER,
                     (hud_x + 8, cursor_y), (hud_x + HUD_WIDTH - 30, cursor_y))
    cursor_y += 6
 
    # Pulsing dot to indicate hardware connection status

    pulse = math.sin(tick * 0.08)
    dot_alpha = int(150 + pulse * 80)
    is_real_hw = backend_label.startswith("IBM Quantum:")
    dot_color = (0, 220, 120) if is_real_hw else SIMULATION_COLOR
    dot_surf = pygame.Surface((12, 12), pygame.SRCALPHA)
    pygame.draw.circle(dot_surf, (*dot_color, dot_alpha), (6, 6), 5)
    screen.blit(dot_surf, (hud_x + 10, cursor_y + 2))
    label_color = (0, 220, 120) if is_real_hw else HUD_TEXT
    status = FONT_HUD_B.render(backend_label, True, label_color)
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
