"""
game_manager.py
---------------
Luis — Game Logic | Quantum Chess
CS5331/4331 Introduction to Quantum Computing | Texas Tech University

Turn flow, win-condition detection, and event orchestration.

Responsibilities:
  - Track whose turn it is (white / black)
  - Handle mouse clicks: select a piece, show legal moves, execute moves
  - Build the game_state dict that renderer.render_frame() consumes each frame
  - Detect check, checkmate, and stalemate after every move
  - Maintain a quantum event log for the HUD
  - Provide hooks for quantum moves (superposition, entangle, measure)
    that quantum_rules.py will call back into

Coordinate flow:
  1. main.py receives a Pygame mouse-click event
  2. main.py calls game_manager.handle_click(pixel_x, pixel_y)
  3. game_manager figures out which square was clicked
  4. Depending on current selection state it either:
       a) selects a piece  (highlights it, computes legal moves)
       b) moves the selected piece to the target square
       c) deselects (clicked empty square / own piece with no moves)
  5. After a move, game_manager checks for check/checkmate/stalemate
  6. main.py calls game_manager.get_game_state() and passes the dict
     to renderer.render_frame()

---------------------------------------------------------------------------
"""

from __future__ import annotations
from typing import Optional
from board import Board, to_grid, to_alg
from constants import BOARD_OFFSET_X, BOARD_OFFSET_Y, SQUARE_SIZE, BOARD_PX


# -------------------------------------------------------------------------
# Pixel-to-board conversion
# -------------------------------------------------------------------------

def pixel_to_square(px: int, py: int) -> Optional[str]:
    """
    Convert a pixel coordinate (from a mouse click) to an algebraic square.

    Returns None if the click is outside the board area.
    """
    col = (px - BOARD_OFFSET_X) // SQUARE_SIZE
    row = (py - BOARD_OFFSET_Y) // SQUARE_SIZE
    if 0 <= col < 8 and 0 <= row < 8:
        return to_alg(col, row)
    return None


# -------------------------------------------------------------------------
# GameManager
# -------------------------------------------------------------------------

class GameManager:
    """
    Central orchestrator for a Quantum Chess game session.

    Attributes:
        board:         Board instance holding all piece state.
        current_turn:  "white" or "black".
        selected_piece: Currently selected piece dict, or None.
        selected_sq:   Algebraic square of the selected piece, or None.
        valid_moves:   List of legal destination squares for selected piece.
        event_log:     List of human-readable strings for the HUD event log.
        game_over:     True once checkmate or stalemate is detected.
        game_result:   Short result string ("White wins", "Draw", etc.).
    """

    def __init__(self):
        self.board = Board()
        self.current_turn: str = "white"
        self.selected_piece: Optional[dict] = None
        self.selected_sq: Optional[str] = None
        self.valid_moves: list[str] = []
        self.event_log: list[str] = []
        self.game_over: bool = False
        self.game_result: str = ""

    # ------------------------------------------------------------------
    # Game-state dict (consumed by renderer every frame)
    # ------------------------------------------------------------------

    def get_game_state(self) -> dict:
        """
        Build and return the dict that renderer.render_frame() expects.

        Keys:
            pieces       – live piece list from the board
            selected     – algebraic square of the selected piece (or None)
            valid_moves  – list of legal move targets
            current_turn – "white" or "black"
            check_king   – algebraic square of king in check (or None)
            event_log    – list of recent event strings for the HUD
            game_over    – bool
            game_result  – result string
        """
        return {
            "pieces":       self.board.get_pieces_list(),
            "selected":     self.selected_sq,
            "valid_moves":  self.valid_moves,
            "current_turn": self.current_turn,
            "check_king":   self.board.king_square_if_in_check(self.current_turn),
            "event_log":    self.event_log,
            "game_over":    self.game_over,
            "game_result":  self.game_result,
        }

    # ------------------------------------------------------------------
    # Click handling
    # ------------------------------------------------------------------

    def handle_click(self, px: int, py: int):
        """
        Process a mouse click at pixel coordinates (px, py).

        State machine:
          • Nothing selected → click own piece → select it
          • Piece selected   → click valid target → execute move
          • Piece selected   → click another own piece → re-select
          • Piece selected   → click invalid square → deselect
        """
        if self.game_over:
            return

        square = pixel_to_square(px, py)
        if square is None:
            # Click outside the board — deselect
            self.deselect()
            return

        clicked_piece = self.board.piece_at(square)

        # ----- No piece currently selected -----
        if self.selected_piece is None:
            if clicked_piece and clicked_piece["color"] == self.current_turn:
                self.select(clicked_piece, square)
            return

        # ----- A piece IS selected -----

        # Clicked the same square → deselect
        if square == self.selected_sq:
            self.deselect()
            return

        # Clicked another of our own pieces → re-select that one instead
        if clicked_piece and clicked_piece["color"] == self.current_turn:
            self.select(clicked_piece, square)
            return

        # Clicked a valid move target → execute the move
        if square in self.valid_moves:
            self.execute_move(square)
            return

        # Clicked an invalid square → deselect
        self.deselect()

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def select(self, piece: dict, square: str):
        """Select a piece and compute its legal moves."""
        self.selected_piece = piece
        self.selected_sq = square
        self.valid_moves = self.board.get_legal_moves(piece)

    def deselect(self):
        """Clear the current selection."""
        self.selected_piece = None
        self.selected_sq = None
        self.valid_moves = []

    # ------------------------------------------------------------------
    # Move execution
    # ------------------------------------------------------------------

    def execute_move(self, target: str):
        """
        Move the selected piece to *target*, handle captures, log events,
        switch turns, and check for game-ending conditions.
        """
        piece = self.selected_piece
        origin = self.selected_sq

        # Build a human-readable description for the event log
        symbol = piece["type"].capitalize()
        capture_target = self.board.piece_at(target)
        if capture_target and capture_target["color"] != piece["color"]:
            cap_symbol = capture_target["type"].capitalize()
            self.log(f"{piece['color'].capitalize()} {symbol} {origin}×{target} (captured {cap_symbol})")
        else:
            self.log(f"{piece['color'].capitalize()} {symbol} {origin}→{target}")

        # Execute on the board (handles capture + auto-promotion)
        self.board.move_piece(piece, target)

        # Clear selection
        self.deselect()

        # Switch turn
        self.next_turn()

        # Check for game-ending conditions
        self.check_end_conditions()

    # ------------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------------

    def next_turn(self):
        """Switch to the other player's turn."""
        self.current_turn = "black" if self.current_turn == "white" else "white"

    # ------------------------------------------------------------------
    # End-of-game detection
    # ------------------------------------------------------------------

    def check_end_conditions(self):
        """
        After switching turns, check if the new current player is in
        checkmate or stalemate.
        """
        color = self.current_turn

        if self.board.is_checkmate(color):
            winner = "Black" if color == "white" else "White"
            self.game_over = True
            self.game_result = f"Checkmate — {winner} wins!"
            self.log(self.game_result)

        elif self.board.is_stalemate(color):
            self.game_over = True
            self.game_result = "Stalemate — Draw!"
            self.log(self.game_result)

        elif self.board.is_in_check(color):
            self.log(f"{color.capitalize()} is in check!")

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def log(self, message: str):
        """Append a message to the event log (shown in the HUD)."""
        self.event_log.append(message)

    def get_recent_events(self, n: int = 4) -> list[str]:
        """Return the last *n* events for HUD display."""
        return self.event_log[-n:]

    # ------------------------------------------------------------------
    # Quantum move stubs (to be wired to quantum_rules.py)
    # ------------------------------------------------------------------

    def handle_superposition_move(self, piece: dict, sq_a: str, sq_b: str):
        """
        Stub: put *piece* into superposition across sq_a and sq_b.

        Will be implemented when quantum_rules.py is integrated.
        For now, logs the intent so the HUD shows something useful
        during early testing.
        """
        symbol = piece["type"].capitalize()
        self.log(f"{symbol} split → {sq_a} ↔ {sq_b}")
        # TODO: call quantum_rules.superposition_move(self.board, piece, sq_a, sq_b)

    def handle_entangle_move(self, piece_a: dict, piece_b: dict):
        """
        Stub: entangle two pieces via a Bell state.

        Will be implemented when quantum_rules.py is integrated.
        """
        sym_a = piece_a["type"].capitalize()
        sym_b = piece_b["type"].capitalize()
        pos_a = piece_a["positions"][0]
        pos_b = piece_b["positions"][0]
        self.log(f"{sym_a}({pos_a}) entangled with {sym_b}({pos_b})")
        # TODO: call quantum_rules.entangle_move(self.board, piece_a, piece_b)

    def handle_measure(self, piece: dict):
        """
        Stub: force-measure a superposed piece, collapsing it.

        Will be implemented when quantum_rules.py is integrated.
        """
        symbol = piece["type"].capitalize()
        self.log(f"{symbol} measured (collapse pending)")
        # TODO: call quantum_rules.measure_piece(self.board, piece)


# =========================================================================
# Standalone test — run with:  python game_manager.py
# =========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  game_manager.py — GameManager Tests")
    print("=" * 60)

    gm = GameManager()

    # --- Test 1: initial state ---
    state = gm.get_game_state()
    assert state["current_turn"] == "white"
    assert state["selected"] is None
    assert state["valid_moves"] == []
    assert len(state["pieces"]) == 32
    print("\n[PASS] Initial game state is correct")

    # --- Test 2: select a pawn by clicking its pixel location ---
    # e2 pawn: col=4, row=6 → pixel center roughly (OFFSET_X + 4*80 + 40, OFFSET_Y + 6*80 + 40)
    e2_px = BOARD_OFFSET_X + 4 * SQUARE_SIZE + SQUARE_SIZE // 2
    e2_py = BOARD_OFFSET_Y + 6 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm.handle_click(e2_px, e2_py)

    state = gm.get_game_state()
    assert state["selected"] == "e2", f"Expected e2 selected, got {state['selected']}"
    assert "e3" in state["valid_moves"]
    assert "e4" in state["valid_moves"]
    print(f"[PASS] Selected e2 pawn — valid moves: {sorted(state['valid_moves'])}")

    # --- Test 3: move pawn to e4 ---
    e4_px = BOARD_OFFSET_X + 4 * SQUARE_SIZE + SQUARE_SIZE // 2
    e4_py = BOARD_OFFSET_Y + 4 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm.handle_click(e4_px, e4_py)

    state = gm.get_game_state()
    assert state["current_turn"] == "black", f"Expected black's turn, got {state['current_turn']}"
    assert state["selected"] is None
    assert gm.board.piece_at("e4") is not None
    assert gm.board.piece_at("e2") is None
    print("[PASS] Moved e2→e4, turn switched to black")

    # --- Test 4: click outside board does nothing ---
    gm.handle_click(5, 5)
    state = gm.get_game_state()
    assert state["selected"] is None
    print("[PASS] Click outside board deselects cleanly")

    # --- Test 5: black moves a pawn ---
    d7_px = BOARD_OFFSET_X + 3 * SQUARE_SIZE + SQUARE_SIZE // 2
    d7_py = BOARD_OFFSET_Y + 1 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm.handle_click(d7_px, d7_py)  # select d7 pawn

    state = gm.get_game_state()
    assert state["selected"] == "d7"
    print(f"[PASS] Black selected d7 — valid moves: {sorted(state['valid_moves'])}")

    d5_px = BOARD_OFFSET_X + 3 * SQUARE_SIZE + SQUARE_SIZE // 2
    d5_py = BOARD_OFFSET_Y + 3 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm.handle_click(d5_px, d5_py)  # move to d5

    state = gm.get_game_state()
    assert state["current_turn"] == "white"
    assert gm.board.piece_at("d5") is not None
    print("[PASS] Black moved d7→d5, turn switched to white")

    # --- Test 6: event log ---
    assert len(gm.event_log) >= 2
    print(f"[PASS] Event log has {len(gm.event_log)} entries:")
    for ev in gm.event_log:
        print(f"       • {ev}")

    # --- Test 7: re-select (click different own piece) ---
    # White's turn — click b1 knight, then click d2 pawn instead
    b1_px = BOARD_OFFSET_X + 1 * SQUARE_SIZE + SQUARE_SIZE // 2
    b1_py = BOARD_OFFSET_Y + 7 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm.handle_click(b1_px, b1_py)
    assert gm.get_game_state()["selected"] == "b1"

    d2_px = BOARD_OFFSET_X + 3 * SQUARE_SIZE + SQUARE_SIZE // 2
    d2_py = BOARD_OFFSET_Y + 6 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm.handle_click(d2_px, d2_py)
    assert gm.get_game_state()["selected"] == "d2"
    print("[PASS] Re-selecting a different own piece works")

    # Deselect
    gm.handle_click(5, 5)
    assert gm.get_game_state()["selected"] is None
    print("[PASS] Deselection works")

    print("\n" + "=" * 60)
    print("  All game_manager.py tests passed!")
    print("=" * 60)# Turn flow, win condition, event orchestration
