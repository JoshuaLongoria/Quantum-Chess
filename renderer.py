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
from board import to_grid
from constants import *  # includes GHOST_WHITE_FX, GHOST_BLACK_FX
from ui_components import draw_hud, _get_entangled_pairs
 
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
        col, row = to_grid(pos)
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
    is_white = piece["color"] == "white"
    ghost_color = GHOST_WHITE    if is_white else GHOST_BLACK
    fx_color    = GHOST_WHITE_FX if is_white else GHOST_BLACK_FX

    ghost_surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)

    # Team-colored shimmer background to signal quantum state
    shimmer = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
    shimmer.fill((*fx_color, 28))
    ghost_surf.blit(shimmer, (0, 0))

    # Team-colored border around the ghost square
    border_surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
    pygame.draw.rect(border_surf, (*fx_color, 140),
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
    col_a, row_a = to_grid(pos_a)
    col_b, row_b = to_grid(pos_b)
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
 
 
# render_frame is the main function Person C will call from main.py each frame to draw everything.
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
        col, row = to_grid(selected)
        highlight_square(screen, col, row, SELECTED_COLOR, alpha=80)
 
    # 4b. Highlight valid move targets
    draw_valid_move_dots(screen, valid_moves)
 
    # 4c. Highlight king in check
    if check_king:
        col, row = to_grid(check_king)
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
                col, row = to_grid(pos)
                draw_ghost_piece(screen, piece, col, row)
        elif positions:
            # Draw solid piece on its single classical position
            col, row = to_grid(positions[0])
            draw_piece(screen, piece, col, row)
 
    # 8. HUD panel
    draw_hud(screen, pieces, tick, event_log=game_state.get("event_log"),
             backend_label=game_state.get("backend_label", "Simulator (local)"))
