# constants.py
# This module defines all the constants used across the Quantum Chess game,
# including colors, fonts, layout dimensions, and piece symbols.

import pygame


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

BG_COLOR =  (33, 41, 34)
BOARD_LIGHT = (91, 130, 102)  
BOARD_DARK = (41, 73, 54)
BOARD_BORDER = (62, 98, 89)

PIECE_WHITE = (255, 255, 255)
PIECE_BLACK = ( 30, 35, 55)
PIECE_OUTLINE = (90, 110, 150)

GHOST_WHITE     = (140, 230, 255)   # icy cyan glyph — white team ghosts
GHOST_BLACK     = (255, 90,  210)   # hot magenta glyph — black team ghosts
GHOST_WHITE_FX  = (100, 210, 255)   # cyan shimmer/border for white ghosts
GHOST_BLACK_FX  = (255, 60,  200)   # magenta shimmer/border for black ghosts
GHOST_ALPHA = 110 #GHOST PIECES

ENTANGLE_COLOR = (80, 220, 255) 
ENTANGLE_ALPHA = 160
ENTANGLE_PULSE = True
SIMULATION_COLOR = (208, 240, 25)

SELECTED_COLOR = (255, 215, 0) 
VALID_MOVE_COLOR = (169, 229, 187)
CHECK_COLOR = (220, 60, 60)

HUD_BG = (145,243,179)
HUD_BORDER = (62, 98, 89)
HUD_TITLE = (2, 18, 8)
HUD_TEXT = (18, 152, 248)
HUD_ACCENT = (96, 93, 131)
HUD_SUPERPOSE = (49, 133, 252)
HUD_ENTANGLE = (49, 133, 252)

LABEL_COLOR = (255, 255, 255)

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