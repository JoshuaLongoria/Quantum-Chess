"""
renderer.py
-----------
Person C — UI & Visualization | Quantum Chess
CS5331/4331 Introduction to Quantum Computing | Texas Tech University
 
This is the main rendering module. It handles everything the player sees:
  - The chess board with a dark quantum aesthetic
  - Classic piece positions
  - Ghost pieces for superposed pieces (semi-transparent, on two squares)
  - Glowing entanglement lines between linked pieces
  - A Quantum State HUD panel on the right side showing live quantum status
Pygame works like a canvas you repaint every frame (~60x per second).
Each frame you:
  1. Clear the screen (fill with background color)
  2. Draw everything from back to front (background → board → pieces → effects → HUD)
  3. Call pygame.display.flip() to show the frame to the user
 
Key concepts:
  - pygame.Surface  : a drawable rectangle (the screen is a Surface)
  - pygame.Rect     : a rectangle defined by (x, y, width, height)
  - screen.blit()   : "stamp" one Surface onto another at a given position
  - pygame.draw.*   : draw shapes directly onto a Surface
  - pygame.font.*   : render text onto a Surface
 
Coordinate system: (0, 0) is TOP-LEFT. X grows right, Y grows DOWN.
---------------------------------------------------------------------------
 
Dependencies: pygame, math, typing
"""

import pygame
import math
import sys

#---Window Layout---
pygame.init()
BOARD_COLS = 8
BOARD_ROWS = 8
SQUARE_SIZE = 80

BOARD_OFFSET_X = 60
BOARD_OFFSET_Y = 60
BOARD_PX = SQUARE_SIZE * BOARD_COLS 
HUD_WIDTH = 280
LABEL_PAD = 30

WINDOW_WIDTH = BOARD_OFFSET_X + BOARD_PX + HUD_WIDTH + 40
WINDOW_HEIGHT = BOARD_OFFSET_Y + BOARD_PX + LABEL_PAD + 20

#---Color Palette---
# Dark, moody colors for a quantum chess vibe

BG_COLOR = (15, 18, 35)          
BOARD_LIGHT = ( 44, 62, 95)
BOARD_DARK = ( 22, 33, 58)
BOARD_BORDER = ( 80, 100, 140)

PIECE_WHITE = (230, 235, 245)
PIECE_BLACK = ( 30, 35, 55)
PIECE_OUTLINE = (90, 110, 150)

GHOST_WHITE = (180, 200, 240)
GHOST_BLACK = (60, 75, 120)
GHOST_ALPHA = 110 #GHOST PIECES 

ENTANGLE_COLOR = (80, 220, 255) 
ENTANGLE_ALPHA = 160
ENTANGLE_PULSE = True 

SELECTED_COLOR = (255, 215, 0) 
VALID_MOVE_COLOR = (80, 200, 120)
CHECK_COLOR = (220, 60, 60)

HUD_BG = (20, 25, 48)
HUD_BORDER = (50, 70, 120)
HUD_TITLE = (180, 200, 255)
HUD_TEXT = (160, 175, 210)
HUD_ACCENT = (255, 215, 0)
HUD_SUPERPOSE = (80, 180, 255)
HUD_ENTANGLE = (80, 220, 255)

LABEL_COLOR = (100, 120, 160)

# --- Typography -----------------------------------------------------------
FONT_PIECE_SIZE  = 44    # piece symbol font size
FONT_LABEL_SIZE  = 16    # board coordinate labels (a-h, 1-8)
FONT_HUD_TITLE   = 15    # HUD section headings
FONT_HUD_BODY    = 13    # HUD body text
 
# Pygame uses system fonts; "segoeuisymbol" renders chess Unicode well on Windows.
# "dejavusans" works cross-platform. We fall back gracefully.
FONT_PIECE   = pygame.font.SysFont("segoeuisymbol, dejavusans, symbola", FONT_PIECE_SIZE)
FONT_LABEL   = pygame.font.SysFont("consolas, monospace", FONT_LABEL_SIZE)
FONT_HUD_T   = pygame.font.SysFont("consolas, monospace", FONT_HUD_TITLE, bold=True)
FONT_HUD_B   = pygame.font.SysFont("consolas, monospace", FONT_HUD_BODY)
 
# --- Chess piece Unicode symbols ------------------------------------------
# These render as actual chess piece glyphs in most system fonts.
PIECE_SYMBOLS = {
    ("king",   "white"): "♔",
    ("queen",  "white"): "♕",
    ("rook",   "white"): "♖",
    ("bishop", "white"): "♗",
    ("knight", "white"): "♘",
    ("pawn",   "white"): "♙",
    ("king",   "black"): "♚",
    ("queen",  "black"): "♛",
    ("rook",   "black"): "♜",
    ("bishop", "black"): "♝",
    ("knight", "black"): "♞",
    ("pawn",   "black"): "♟",
}
 
 
# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------
 
def square_to_pixel(col: int, row: int) -> tuple[int, int]:
    """
    Convert board grid coordinates to pixel coordinates (top-left of that square).
 
    Board uses (col, row) where col 0 = 'a' file, row 0 = rank 8 (top of screen).
    So row increases downward on screen, matching Pygame's Y axis.
 
    Args:
        col: Board column 0-7 (left to right, a-h)
        row: Board row 0-7 (top to bottom, rank 8 to rank 1)
 
    Returns:
        (pixel_x, pixel_y) of the square's top-left corner
    """
    x = BOARD_OFFSET_X + col * SQUARE_SIZE
    y = BOARD_OFFSET_Y + row * SQUARE_SIZE
    return x, y
 
 
def square_center(col: int, row: int) -> tuple[int, int]:
    """Return the pixel center of a board square."""
    x, y = square_to_pixel(col, row)
    return x + SQUARE_SIZE // 2, y + SQUARE_SIZE // 2
 
 
def algebraic_to_grid(pos: str) -> tuple[int, int]:
    """
    Convert algebraic notation (e.g. 'e4') to grid (col, row).
 
    'a' = col 0, 'h' = col 7
    Rank '8' = row 0 (top), rank '1' = row 7 (bottom)
 
    Args:
        pos: Algebraic square like 'e4', 'a1', 'h8'
 
    Returns:
        (col, row) grid coordinates
    """
    col = ord(pos[0]) - ord('a')        # 'a'=0, 'b'=1 ... 'h'=7
    row = 8 - int(pos[1])               # '8'=0 (top), '1'=7 (bottom)
    return col, row
 
 
# ---------------------------------------------------------------------------
# Drawing helpers — Board
# ---------------------------------------------------------------------------
 
def draw_board(screen: pygame.Surface):
    """
    Draw the 8x8 chess board squares and border.
 
    Squares alternate between BOARD_LIGHT and BOARD_DARK.
    Light squares: (col + row) is even. Dark squares: (col + row) is odd.
 
    Args:
        screen: The main Pygame display surface to draw on.
    """
    # Draw outer border glow first (slightly larger rectangle behind the board)
    border_rect = pygame.Rect(
        BOARD_OFFSET_X - 3,
        BOARD_OFFSET_Y - 3,
        BOARD_PX + 6,
        BOARD_PX + 6
    )
    pygame.draw.rect(screen, BOARD_BORDER, border_rect, border_radius=4)
 
    # Draw each square
    for row in range(BOARD_ROWS):
        for col in range(BOARD_COLS):
            color = BOARD_LIGHT if (col + row) % 2 == 0 else BOARD_DARK
            x, y = square_to_pixel(col, row)
            # pygame.Rect(x, y, width, height)
            pygame.draw.rect(screen, color, pygame.Rect(x, y, SQUARE_SIZE, SQUARE_SIZE))
 
 
def draw_coordinates(screen: pygame.Surface):
    """
    Draw file letters (a-h) below the board and rank numbers (1-8) to the left.
 
    These help players identify squares during the game and presentation.
    """
    files = "abcdefgh"
    ranks = "87654321"   # rank 8 is at the top (row 0), rank 1 at the bottom
 
    for i in range(8):
        # File labels below the board
        label = FONT_LABEL.render(files[i], True, LABEL_COLOR)
        x = BOARD_OFFSET_X + i * SQUARE_SIZE + SQUARE_SIZE // 2 - label.get_width() // 2
        y = BOARD_OFFSET_Y + BOARD_PX + 6
        screen.blit(label, (x, y))
 
        # Rank labels to the left of the board
        label = FONT_LABEL.render(ranks[i], True, LABEL_COLOR)
        x = BOARD_OFFSET_X - label.get_width() - 8
        y = BOARD_OFFSET_Y + i * SQUARE_SIZE + SQUARE_SIZE // 2 - label.get_height() // 2
        screen.blit(label, (x, y))
 
 
def highlight_square(screen: pygame.Surface, col: int, row: int,
                      color: tuple, alpha: int = 100, border_only: bool = False):
    """
    Draw a colored highlight overlay on a board square.
 
    We use a separate transparent Surface (pygame.SRCALPHA) because Pygame
    doesn't support alpha on basic draw calls — you need a Surface with
    per-pixel alpha to get transparency effects.
 
    Args:
        screen: Main display surface.
        col, row: Grid coordinates of the square to highlight.
        color: RGB color tuple.
        alpha: Transparency 0 (invisible) to 255 (fully opaque).
        border_only: If True, draw only a border instead of a filled overlay.
    """
    x, y = square_to_pixel(col, row)
 
    # Create a small transparent surface the size of one square
    overlay = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
 
    if border_only:
        # Draw a thick colored border around the square
        pygame.draw.rect(overlay, (*color, alpha),
                         pygame.Rect(0, 0, SQUARE_SIZE, SQUARE_SIZE), width=4)
    else:
        # Fill the square with a semi-transparent color
        overlay.fill((*color, alpha))
 
    screen.blit(overlay, (x, y))
 
 
def draw_valid_move_dots(screen: pygame.Surface, moves: list[str]):
    """
    Draw small green dots on squares where the selected piece can legally move.
 
    Args:
        screen: Main display surface.
        moves: List of algebraic square strings like ['e4', 'f5'].
    """
    for pos in moves:
        col, row = algebraic_to_grid(pos)
        # Draw a filled circle — radius 10 for empty squares, ring for occupied
        dot_surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
        pygame.draw.circle(dot_surf, (*VALID_MOVE_COLOR, 140),
                           (SQUARE_SIZE // 2, SQUARE_SIZE // 2), 10)
        x, y = square_to_pixel(col, row)
        screen.blit(dot_surf, (x, y))
 
 
# ---------------------------------------------------------------------------
# Drawing helpers — Pieces
# ---------------------------------------------------------------------------
 
def draw_piece(screen: pygame.Surface, piece: dict,
               col: int, row: int, alpha: int = 255):
    """
    Draw a single chess piece on the board at (col, row).
 
    Pieces are drawn as Unicode chess symbols centered on their square.
    A slight shadow offset gives depth. Alpha controls transparency
    (used for ghost pieces in superposition).
 
    Args:
        screen: Main display surface.
        piece: Piece dict with 'type' and 'color' keys.
        col, row: Grid position to draw at.
        alpha: Transparency (255 = solid, ~110 = ghost).
    """
    symbol = PIECE_SYMBOLS.get((piece["type"], piece["color"]), "?")
    base_color = PIECE_WHITE if piece["color"] == "white" else PIECE_BLACK
 
    # Render the piece glyph onto a surface with per-pixel alpha
    # so we can control transparency for ghost pieces
    piece_surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
 
    # Shadow (slightly offset, darker, semi-transparent) — adds visual depth
    shadow_color = (0, 0, 0, min(alpha // 2, 80))
    shadow_text = FONT_PIECE.render(symbol, True, shadow_color[:3])
    shadow_text.set_alpha(shadow_color[3])
    cx = SQUARE_SIZE // 2 - shadow_text.get_width() // 2 + 2
    cy = SQUARE_SIZE // 2 - shadow_text.get_height() // 2 + 2
    piece_surf.blit(shadow_text, (cx, cy))
 
    # Main piece glyph
    glyph = FONT_PIECE.render(symbol, True, base_color)
    glyph.set_alpha(alpha)
    gx = SQUARE_SIZE // 2 - glyph.get_width() // 2
    gy = SQUARE_SIZE // 2 - glyph.get_height() // 2
    piece_surf.blit(glyph, (gx, gy))
 
    # Stamp the piece surface onto the screen at the correct position
    x, y = square_to_pixel(col, row)
    screen.blit(piece_surf, (x, y))
 
 
def draw_ghost_piece(screen: pygame.Surface, piece: dict, col: int, row: int):
    """
    Draw a semi-transparent "ghost" version of a piece for superposition.
 
    The ghost indicates the piece *might* be here — it's in superposition
    and hasn't collapsed yet. It's drawn at reduced alpha with a colored
    tint (GHOST_WHITE or GHOST_BLACK) to visually distinguish it from
    a fully collapsed piece.
 
    Args:
        screen: Main display surface.
        piece: Piece dict.
        col, row: Grid position for this ghost instance.
    """
 
    symbol = PIECE_SYMBOLS.get((piece["type"], piece["color"]), "?")
    ghost_color = GHOST_WHITE if piece["color"] == "white" else GHOST_BLACK
 
    ghost_surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
 
    # Blue-white shimmer background on the square to signal quantum state
    shimmer = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
    shimmer.fill((100, 160, 255, 30))
    ghost_surf.blit(shimmer, (0, 0))
 
    # Dashed border around the ghost square to signal superposition
    border_surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
    pygame.draw.rect(border_surf, (100, 180, 255, 120),
                     pygame.Rect(2, 2, SQUARE_SIZE - 4, SQUARE_SIZE - 4), width=2)
    ghost_surf.blit(border_surf, (0, 0))
 
    # Ghost glyph at reduced alpha
    glyph = FONT_PIECE.render(symbol, True, ghost_color)
    glyph.set_alpha(GHOST_ALPHA)
    gx = SQUARE_SIZE // 2 - glyph.get_width() // 2
    gy = SQUARE_SIZE // 2 - glyph.get_height() // 2
    ghost_surf.blit(glyph, (gx, gy))
 
    x, y = square_to_pixel(col, row)
    screen.blit(ghost_surf, (x, y))
 
 
# ---------------------------------------------------------------------------
# Drawing helpers — Entanglement effects
# ---------------------------------------------------------------------------
 
def draw_entanglement_line(screen: pygame.Surface,
                            pos_a: str, pos_b: str,
                            tick: int):
    """
    Draw a glowing cyan line between two entangled pieces.
 
    The line pulses in opacity over time using a sine wave based on
    the current game tick (frame count). This gives the visual impression
    of quantum "vibration" between the pieces.
 
    Args:
        screen: Main display surface.
        pos_a: Algebraic position of first entangled piece (e.g. 'e4').
        pos_b: Algebraic position of second entangled piece (e.g. 'g6').
        tick: Current frame count — used to drive the pulse animation.
    """
    col_a, row_a = algebraic_to_grid(pos_a)
    col_b, row_b = algebraic_to_grid(pos_b)
    cx_a, cy_a = square_center(col_a, row_a)
    cx_b, cy_b = square_center(col_b, row_b)
 
    # Pulsing alpha: sine wave oscillates between 80 and 200 over ~2 seconds
    # math.sin() returns -1 to 1; we map that to 80-200
    if ENTANGLE_PULSE:
        pulse = math.sin(tick * 0.05)             # oscillates -1 to 1
        alpha = int(80 + (pulse + 1) * 60)        # maps to 80-200
    else:
        alpha = ENTANGLE_ALPHA
 
    # Draw multiple lines at different widths to simulate a "glow" effect.
    # Pygame doesn't have native glow — we fake it with layered semi-transparent lines.
    # Outer glow (wide, very transparent)
    line_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    pygame.draw.line(line_surf, (*ENTANGLE_COLOR, alpha // 4),
                     (cx_a, cy_a), (cx_b, cy_b), width=8)
    # Mid glow
    pygame.draw.line(line_surf, (*ENTANGLE_COLOR, alpha // 2),
                     (cx_a, cy_a), (cx_b, cy_b), width=4)
    # Core line (bright, thin)
    pygame.draw.line(line_surf, (*ENTANGLE_COLOR, alpha),
                     (cx_a, cy_a), (cx_b, cy_b), width=2)
 
    screen.blit(line_surf, (0, 0))
 
    # Draw small circles at each endpoint to mark the pieces as entangled
    end_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    for cx, cy in [(cx_a, cy_a), (cx_b, cy_b)]:
        pygame.draw.circle(end_surf, (*ENTANGLE_COLOR, alpha), (cx, cy), 8)
        pygame.draw.circle(end_surf, (*ENTANGLE_COLOR, alpha // 3), (cx, cy), 14)
    screen.blit(end_surf, (0, 0))
 
 
# ---------------------------------------------------------------------------
# Drawing helpers — Quantum State HUD
# ---------------------------------------------------------------------------
 
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


    # In your final game, pass real event messages from game_manager.
    # For now, these are example placeholder messages.


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
 
 
# ---------------------------------------------------------------------------
# Main render function — called every frame
# ---------------------------------------------------------------------------
 
def render_frame(screen: pygame.Surface, game_state: dict, tick: int):
    """
    Render one complete frame of the Quantum Chess game.
 
    This is the master function Person C calls from main.py each frame.
    It draws everything in the correct back-to-front order:
 
        1. Background
        2. Board squares
        3. Coordinate labels
        4. Square highlights (selected, valid moves, check)
        5. Entanglement lines (behind pieces)
        6. Classical pieces (solid)
        7. Ghost pieces (superposed)
        8. HUD panel
 
    Args:
        screen: Main Pygame display surface.
        game_state: Dict from game_manager containing board state.
            Expected keys:
              "pieces"       : list of piece dicts
              "selected"     : algebraic pos of selected square (or None)
              "valid_moves"  : list of algebraic move targets
              "current_turn" : "white" or "black"
              "check_king"   : algebraic pos of king in check (or None)
        tick: Current frame counter (for animations).
    """
    pieces      = game_state.get("pieces", [])
    selected    = game_state.get("selected", None)
    valid_moves = game_state.get("valid_moves", [])
    check_king  = game_state.get("check_king", None)
 
    # 1. Background
    screen.fill(BG_COLOR)
 
    # 2. Board squares
    draw_board(screen)
 
    # 3. Coordinate labels
    draw_coordinates(screen)
 
    # 4a. Highlight selected square
    if selected:
        col, row = algebraic_to_grid(selected)
        highlight_square(screen, col, row, SELECTED_COLOR, alpha=80)
 
    # 4b. Highlight valid move targets
    draw_valid_move_dots(screen, valid_moves)
 
    # 4c. Highlight king in check
    if check_king:
        col, row = algebraic_to_grid(check_king)
        highlight_square(screen, col, row, CHECK_COLOR, alpha=100, border_only=True)
 
    # 5. Entanglement lines (drawn before pieces so lines go under them)
    entangled_pairs = _get_entangled_pairs(pieces)
    for piece_a, piece_b in entangled_pairs:
        pos_a = piece_a.get("positions", [None])[0]
        pos_b = piece_b.get("positions", [None])[0]
        if pos_a and pos_b:
            draw_entanglement_line(screen, pos_a, pos_b, tick)
 
    # 6 & 7. Draw pieces — solid for classical, ghost for superposed
    for piece in pieces:
        positions = piece.get("positions", [])
        is_superposed = piece.get("superposed", False)
 
        if is_superposed and len(positions) == 2:
            # Draw ghost on BOTH squares — the piece might be at either
            for pos in positions:
                col, row = algebraic_to_grid(pos)
                draw_ghost_piece(screen, piece, col, row)
        elif positions:
            # Draw solid piece on its single classical position
            col, row = algebraic_to_grid(positions[0])
            draw_piece(screen, piece, col, row)
 
    # 8. HUD panel
    draw_hud(screen, pieces, tick)
 
 
# ---------------------------------------------------------------------------
# Demo — run this file directly to see the renderer in action
# ---------------------------------------------------------------------------
 
if __name__ == "__main__":

    #Standalone demo: renders a sample board state so you can see all the
    #visual features without needing the full game_manager running.
    #Run with:  python renderer.py
    #Press ESC or close the window to quit.
    # Create the window
    # pygame.display.set_mode((width, height)) creates the main window surface


    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Quantum Chess — Renderer Demo")
 
    # A clock object limits how fast the game loop runs (target: 60 FPS)
    clock = pygame.time.Clock()
 
    # --- Sample game state for the demo ----------------------------------
    # This mimics what game_manager.py will eventually provide.
    # Two regular pieces, one superposed knight, and one entangled pair.


    demo_state = {
        "current_turn": "white",
        "selected": "e2",           # e2 is highlighted as selected
        "valid_moves": ["e3", "e4", "d3", "f3"],
        "check_king": None,
        "pieces": [
            # --- Classical pieces (single position) ---
            {"type": "king",   "color": "white",  "positions": ["e1"],
             "superposed": False, "qubit_id": 0,  "entangled_with": []},
            {"type": "queen",  "color": "white",  "positions": ["d1"],
             "superposed": False, "qubit_id": 1,  "entangled_with": []},
            {"type": "pawn",   "color": "white",  "positions": ["e2"],
             "superposed": False, "qubit_id": 2,  "entangled_with": []},
            {"type": "pawn",   "color": "white",  "positions": ["d2"],
             "superposed": False, "qubit_id": 3,  "entangled_with": []},
            {"type": "king",   "color": "black",  "positions": ["e8"],
             "superposed": False, "qubit_id": 4,  "entangled_with": []},
            {"type": "queen",  "color": "black",  "positions": ["d8"],
             "superposed": False, "qubit_id": 5,  "entangled_with": []},
            {"type": "pawn",   "color": "black",  "positions": ["e7"],
             "superposed": False, "qubit_id": 6,  "entangled_with": []},
 
            # --- Superposed knight (exists on TWO squares simultaneously) ---
            # This demonstrates the ghost piece rendering

            {"type": "knight", "color": "white",  "positions": ["c3", "g5"],
             "superposed": True,  "qubit_id": 7,  "entangled_with": [8]},
 
            # --- Entangled rook pair (linked via Bell state) ---
            # These two pieces will have the glowing entanglement line between them

            {"type": "rook",   "color": "white",  "positions": ["a1"],
             "superposed": False, "qubit_id": 8,  "entangled_with": [7]},
            {"type": "bishop", "color": "black",  "positions": ["f6"],
             "superposed": False, "qubit_id": 9,  "entangled_with": [10]},
            {"type": "rook",   "color": "black",  "positions": ["h8"],
             "superposed": False, "qubit_id": 10, "entangled_with": [9]},
        ],
    }
 
    # --- Game loop -------------------------------------------------------
    # The game loop runs continuously until the player quits.
    # Each iteration = one frame.

    tick = 0
    running = True
 
    while running:
 
        # --- Event handling ---
        # pygame.event.get() returns all events since last frame
        # (keyboard, mouse, window close, etc.)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # User clicked the X button
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # User pressed ESC
                    running = False
 
        # --- Render the frame ---
        render_frame(screen, demo_state, tick)
 
        # --- Show the frame ---
        # pygame.display.flip() swaps the back buffer to the screen.
        # Without this, nothing you drew will actually appear.
        pygame.display.flip()
 
        # --- Timing ---
        # clock.tick(60) pauses just long enough to keep us at 60 FPS.
        # It also returns milliseconds elapsed since last frame (unused here).
        clock.tick(60)
        tick += 1
 
    # Clean up Pygame resources before exiting
    pygame.quit()
    sys.exit()