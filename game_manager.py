# Turn flow, win condition, event orchestration
"""
game_manager.py

Turn flow, win-condition detection, and event orchestration.

Responsibilities:
  - Track whose turn it is (white / black)
  - Handle mouse clicks: select a piece, show legal moves, execute moves
  - Manage quantum move modes (superposition, measure, entangle)
  - Build the game_state dict that renderer.render_frame() consumes each frame
  - Detect check, checkmate, and stalemate after every move
  - Maintain a quantum event log for the HUD

Quantum move flow (triggered by keyboard in main.py):
  Q key -> "superposition" mode: click piece, then click destination
  M key -> "measure" mode:       click any superposed own piece to collapse it
  E key -> "entangle" mode:      click two own pieces to link them (stub)
  Esc   -> cancel active quantum mode

---------------------------------------------------------------------------
"""

from __future__ import annotations
from typing import Optional
from board import Board, to_grid, to_alg
from constants import BOARD_OFFSET_X, BOARD_OFFSET_Y, SQUARE_SIZE, BOARD_PX
# Use unified QuantumBackend from Entanglement.py (replaces Quantum_engin.py)
from Entanglement import QuantumBackend, IBM_BACKEND
from quantum_rules import (
    superposition_move,
    collapse_piece,
    entangle_move,
    break_entanglement_on_capture,
    capture_superposed,
)



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
        engine:        QuantumBackend for H gate, measurement, and entanglement.
        current_turn:  "white" or "black".
        selected_piece: Currently selected piece dict, or None.
        selected_sq:   Algebraic square of the selected piece, or None.
        valid_moves:   List of legal destination squares for selected piece.
        event_log:     List of human-readable strings for the HUD event log.
        game_over:     True once checkmate or stalemate is detected.
        game_result:   Short result string ("White wins", "Draw", etc.).
        quantum_mode:  Active quantum input mode, or None for classical play.
        _q_piece:      First piece stored during a multi-step quantum move.
    """

    def __init__(self, quantum_mode: str = "simulated", ibm_backend: str = None):
        self.board = Board()
        # quantum_mode: "simulated", "aer", or "ibm"
        # ibm_backend: optional override from config.py
        backend = ibm_backend or IBM_BACKEND
        self.engine = QuantumBackend(mode=quantum_mode, ibm_backend=backend)
        self.current_turn: str = "white"
        self.selected_piece: Optional[dict] = None
        self.selected_sq: Optional[str] = None
        self.valid_moves: list[str] = []
        self.event_log: list[str] = []
        self.game_over: bool = False
        self.game_result: str = ""
        self.quantum_mode: Optional[str] = None   # "superposition" | "measure" | "entangle"
        self._q_piece: Optional[dict] = None      # piece selected for quantum move
        self._q_sq_a:  Optional[str]  = None      # first ghost destination chosen
        self._last_capture_result: Optional[int] = None  # set when a quantum ghost capture occurs; used by LAN to sync the result

    # ------------------------------------------------------------------
    # Game-state dict (consumed by renderer every frame)
    # ------------------------------------------------------------------

    def get_game_state(self) -> dict:
        """
        Build and return the dict that renderer.render_frame() expects.

        Keys:
            pieces       - live piece list from the board
            selected     - algebraic square of the selected piece (or None)
            valid_moves  - list of legal move targets
            current_turn - "white" or "black"
            check_king   - algebraic square of king in check (or None)
            event_log    - list of recent event strings for the HUD
            game_over    - bool
            game_result  - result string
            quantum_mode - active quantum mode string or None
        """
        return {
            "pieces":          self.board.get_pieces_list(),
            "selected":        self.selected_sq,
            "valid_moves":     self.valid_moves,
            "current_turn":    self.current_turn,
            "check_king":      self.board.king_square_if_in_check(self.current_turn),
            "event_log":       self.event_log,
            "game_over":       self.game_over,
            "game_result":     self.game_result,
            "quantum_mode":    self.quantum_mode,
            "backend_label":   self.engine.status_label,
        }

    # ------------------------------------------------------------------
    # Quantum mode control (called from main.py on keypress)
    # ------------------------------------------------------------------

    def set_quantum_mode(self, mode: str):
        """
        Activate a quantum input mode, or toggle it off if already active.

        Called by main.py when the player presses Q / M / E.
        Pressing the same key twice cancels the mode.
        """
        if self.game_over:
            return

        if self.quantum_mode == mode:
            self._cancel_quantum_mode()
            self.log("Quantum mode cancelled.")
            return

        self._cancel_quantum_mode()
        self.quantum_mode = mode

        hints = {
            "superposition": "SUPERPOSITION: select piece, then click 2 ghost squares.",
            "measure":       "MEASURE: click a superposed piece to collapse it.",
            "entangle":      "ENTANGLE: click two pieces to link them. [stub]",
        }
        self.log(hints.get(mode, ""))

    def _cancel_quantum_mode(self):
        """Reset quantum mode state and clear selection."""
        self.quantum_mode = None
        self._q_piece = None
        self._q_sq_a  = None
        self.deselect()

    def forfeit(self):
        if self.game_over:
            return

        winner = "Black" if self.current_turn == "white" else "White"
        self.game_over = True
        self.game_result = f"Forfeit -- {winner} wins!"
        self.log(self.game_result)
        self._cancel_quantum_mode()

    # ------------------------------------------------------------------
    # Click handling — dispatches to classical or quantum path
    # ------------------------------------------------------------------

    def handle_click(self, px: int, py: int):
        """
        Process a mouse click at pixel coordinates (px, py).

        Routes to the active quantum mode handler, or falls through to
        classical chess click handling.
        """
        if self.game_over:
            return

        square = pixel_to_square(px, py)

        if self.quantum_mode == "superposition":
            self._handle_superposition_click(square)
        elif self.quantum_mode == "measure":
            self._handle_measure_click(square)
        elif self.quantum_mode == "entangle":
            self._handle_entangle_click(square)
        else:
            self._handle_classical_click(square)

    # ------------------------------------------------------------------
    # Classical click handler
    # ------------------------------------------------------------------

    def _handle_classical_click(self, square: Optional[str]):
        """
        Standard chess selection and move execution.

        State machine:
          Nothing selected -> click own piece       -> select it
          Piece selected   -> click valid target    -> execute move
          Piece selected   -> click another own piece -> re-select
          Piece selected   -> click invalid square  -> deselect
        """
        if square is None:
            self.deselect()
            return

        clicked_piece = self.board.piece_at(square)

        if self.selected_piece is None:
            if clicked_piece and clicked_piece["color"] == self.current_turn:
                if clicked_piece["superposed"]:
                    self.log("Superposed pieces can't move. Use M to measure first.")
                    return
                self.select(clicked_piece, square)
            return

        if square == self.selected_sq:
            self.deselect()
            return

        if clicked_piece and clicked_piece["color"] == self.current_turn:
            if clicked_piece["superposed"]:
                self.log("Superposed pieces can't move. Use M to measure first.")
                return
            self.select(clicked_piece, square)
            return

        if square in self.valid_moves:
            self.execute_move(square)
            return

        self.deselect()

    # ------------------------------------------------------------------
    # Quantum click handlers
    # ------------------------------------------------------------------

    def handle_square(self, square: Optional[str]):
        """
        Apply a game action for a given algebraic square.

        Mirrors handle_click() but takes an algebraic square directly instead
        of pixel coordinates.  Used by the LAN network loop to replay the
        opponent's moves on the local board.
        """
        if self.game_over:
            return
        if self.quantum_mode == "superposition":
            self._handle_superposition_click(square)
        elif self.quantum_mode == "measure":
            self._handle_measure_click(square)
        elif self.quantum_mode == "entangle":
            self._handle_entangle_click(square)
        else:
            self._handle_classical_click(square)

    def _handle_superposition_click(self, square: Optional[str]):
        """
        Three-step handler for the superposition move.

        Step 1: click own (non-superposed) piece to select it.
        Step 2: click any legal square (or current square) for the first ghost.
        Step 3: click a different legal square for the second ghost.
               The original square disappears; both chosen squares show ghosts.
        """
        if square is None:
            self._cancel_quantum_mode()
            return

        if self._q_piece is None:
            # Step 1 — select the piece
            piece = self.board.piece_at(square)
            if piece and piece["color"] == self.current_turn and not piece["superposed"]:
                if piece["type"] == "king":
                    self.log("The king cannot enter superposition.")
                    return   # no turn loss
                if piece.get("entangled_with") or piece.get("entanglement_group") is not None:
                    self.log(f"{piece['type'].capitalize()} is entangled — cannot split.")
                    return   # no turn loss — just block and wait
                self._q_piece = piece
                self.selected_sq = square
                # Legal moves + the piece's own square (ghost can stay here too)
                origin = piece["positions"][0]
                self.valid_moves = list(set(self.board.get_legal_moves(piece) + [origin]))
                self.log(f"{piece['type'].capitalize()} selected. Click first ghost square.")
            else:
                self.log("Select one of your non-superposed pieces.")

        elif self._q_sq_a is None:
            # Step 2 — first ghost destination
            if square not in self.valid_moves:
                self.log("Invalid square. Pick a reachable square for ghost 1.")
                return
            self._q_sq_a = square
            self.selected_sq = square
            # Remove the chosen square from options so both ghosts must differ
            self.valid_moves = [sq for sq in self.valid_moves if sq != square]
            self.log(f"Ghost 1 at {square}. Click second ghost square.")

        else:
            # Step 3 — second ghost destination
            if square == self._q_sq_a:
                self.log("Both ghosts must be on different squares.")
                return
            if square not in self.valid_moves:
                self.log("Invalid square. Pick a reachable square for ghost 2.")
                return

            msg = superposition_move(self.board, self.engine, self._q_piece, self._q_sq_a, square)
            self.log(msg)
            if self._q_piece["superposed"]:  # move succeeded
                self._cancel_quantum_mode()
                self.next_turn()
                self.check_end_conditions()
            else:
                self._cancel_quantum_mode()  # failed — no turn loss

    def _handle_measure_click(self, square: Optional[str]):
        """
        Single-click handler: collapse a superposed piece you own.
        """
        if square is None:
            self._cancel_quantum_mode()
            return

        piece = self.board.piece_at(square)
        if piece and piece["color"] == self.current_turn and piece["superposed"]:
            msg = collapse_piece(self.board, self.engine, piece)
            self.log(msg)
            self.quantum_mode = None
            self.next_turn()
            self.check_end_conditions()
        else:
            self.log("Click one of your superposed pieces to collapse it.")

    def _handle_entangle_click(self, square: Optional[str]):
        """
        Two-step handler for the entangle move.

        Step 1: click first own piece.
        Step 2: click second own piece to link them.
        Invalid selections at either step are rejected without a turn loss.
        """
        if square is None:
            self._cancel_quantum_mode()
            return

        piece = self.board.piece_at(square)
        if piece is None or piece["color"] != self.current_turn:
            self.log("Select one of your own pieces to entangle.")
            return

        if self._q_piece is None:
            # Reject ineligible pieces before accepting the first selection
            if piece.get("entanglement_group") is not None or piece.get("entangled_with"):
                self.log(f"{piece['type'].capitalize()} is already entangled — pick a different piece.")
                return
            if piece.get("superposed"):
                self.log("Cannot entangle a superposed piece — measure it first.")
                return
            self._q_piece = piece
            self.selected_sq = square
            self.log(f"Entangle: now click the second piece to link with {piece['type'].capitalize()}.")
        else:
            if piece is self._q_piece:
                self.log("Cannot entangle a piece with itself.")
                return

            msg = entangle_move(self.board, self.engine, self._q_piece, piece)
            self.log(msg)
            self._cancel_quantum_mode()
            if "Entangled" in msg:
                # Only advance the turn when entanglement actually succeeded
                self.next_turn()
                self.check_end_conditions()

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

        If the target holds a superposed enemy piece a 50/50 quantum
        measurement decides the outcome: the ghost either collapses to the
        attacked square (capture succeeds) or survives at its other position
        (capture fails, attacker stays put, turn is still spent).
        """
        self._last_capture_result = None
        piece = self.selected_piece
        origin = self.selected_sq
        symbol = piece["type"].capitalize()
        capture_target = self.board.piece_at(target)

        # Quantum capture: 50/50 whether the ghost is actually there
        if (capture_target
                and capture_target["color"] != piece["color"]
                and capture_target["superposed"]):
            msg = capture_superposed(self.board, self.engine, piece, capture_target, target)
            self._last_capture_result = self.engine.last_result
            self.log(msg)
            self.deselect()
            self.next_turn()
            self.check_end_conditions()
            return

        # Classical move / classical capture
        if capture_target and capture_target["color"] != piece["color"]:
            msg = break_entanglement_on_capture(self.board, capture_target)
            if msg:
                self.log(msg)
            cap_symbol = capture_target["type"].capitalize()
            self.log(f"{piece['color'].capitalize()} {symbol} {origin}x{target} (captured {cap_symbol})")
        else:
            self.log(f"{piece['color'].capitalize()} {symbol} {origin}->{target}")

        self.board.move_piece(piece, target)
        self.deselect()
        self.next_turn()
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
            self.game_result = f"Checkmate -- {winner} wins!"
            self.log(self.game_result)

        elif self.board.is_stalemate(color):
            self.game_over = True
            self.game_result = "Stalemate -- Draw!"
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


# =========================================================================
# Standalone test — run with:  python game_manager.py
# =========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  game_manager.py -- GameManager Tests")
    print("=" * 60)

    gm = GameManager()

    # --- Test 1: initial state ---
    state = gm.get_game_state()
    assert state["current_turn"] == "white"
    assert state["selected"] is None
    assert state["valid_moves"] == []
    assert len(state["pieces"]) == 32
    assert state["quantum_mode"] is None
    print("\n[PASS] Initial game state is correct")

    # --- Test 2: select a pawn ---
    e2_px = BOARD_OFFSET_X + 4 * SQUARE_SIZE + SQUARE_SIZE // 2
    e2_py = BOARD_OFFSET_Y + 6 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm.handle_click(e2_px, e2_py)

    state = gm.get_game_state()
    assert state["selected"] == "e2", f"Expected e2 selected, got {state['selected']}"
    assert "e3" in state["valid_moves"] and "e4" in state["valid_moves"]
    print(f"[PASS] Selected e2 pawn -- valid moves: {sorted(state['valid_moves'])}")

    # --- Test 3: move pawn to e4 ---
    e4_px = BOARD_OFFSET_X + 4 * SQUARE_SIZE + SQUARE_SIZE // 2
    e4_py = BOARD_OFFSET_Y + 4 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm.handle_click(e4_px, e4_py)

    state = gm.get_game_state()
    assert state["current_turn"] == "black"
    assert gm.board.piece_at("e4") is not None
    assert gm.board.piece_at("e2") is None
    print("[PASS] Moved e2->e4, turn switched to black")

    # --- Test 4: superposition mode via set_quantum_mode ---
    gm2 = GameManager()
    gm2.set_quantum_mode("superposition")
    assert gm2.quantum_mode == "superposition"

    # Step 1: select white b1 knight
    b1_px = BOARD_OFFSET_X + 1 * SQUARE_SIZE + SQUARE_SIZE // 2
    b1_py = BOARD_OFFSET_Y + 7 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm2.handle_click(b1_px, b1_py)
    assert gm2._q_piece is not None
    assert gm2._q_piece["type"] == "knight"
    print("[PASS] Superposition step 1: knight selected")

    # Step 2: click a3 (valid knight destination)
    a3_px = BOARD_OFFSET_X + 0 * SQUARE_SIZE + SQUARE_SIZE // 2
    a3_py = BOARD_OFFSET_Y + 5 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm2.handle_click(a3_px, a3_py)
    knight = gm2.board.piece_at("b1") or gm2.board.piece_at("a3")
    assert knight is not None and knight["superposed"]
    assert len(knight["positions"]) == 2
    print(f"[PASS] Superposition step 2: knight in superposition {knight['positions']}")
    assert gm2.current_turn == "black", "Turn should have switched"
    print("[PASS] Turn switched after superposition move")

    # --- Test 5: measure mode ---
    gm2.set_quantum_mode("measure")
    assert gm2.quantum_mode == "measure"

    # Click the superposed knight (it's on both b1 and a3 -- click b1)
    gm2.current_turn = "white"  # force back for test
    gm2.handle_click(b1_px, b1_py)
    assert not knight["superposed"], "Knight should have collapsed"
    assert len(knight["positions"]) == 1
    print(f"[PASS] Measure: knight collapsed to {knight['positions'][0]}")

    # --- Test 6: toggle mode off ---
    gm3 = GameManager()
    gm3.set_quantum_mode("superposition")
    assert gm3.quantum_mode == "superposition"
    gm3.set_quantum_mode("superposition")   # press Q again
    assert gm3.quantum_mode is None
    print("[PASS] Pressing same mode key twice cancels mode")

    # --- Test 7: entangle stub ---
    gm4 = GameManager()
    gm4.set_quantum_mode("entangle")
    a1_px = BOARD_OFFSET_X + 0 * SQUARE_SIZE + SQUARE_SIZE // 2
    a1_py = BOARD_OFFSET_Y + 7 * SQUARE_SIZE + SQUARE_SIZE // 2
    h1_px = BOARD_OFFSET_X + 7 * SQUARE_SIZE + SQUARE_SIZE // 2
    h1_py = BOARD_OFFSET_Y + 7 * SQUARE_SIZE + SQUARE_SIZE // 2
    gm4.handle_click(a1_px, a1_py)
    assert gm4._q_piece is not None
    gm4.handle_click(h1_px, h1_py)
    assert any("STUB" in ev for ev in gm4.event_log)
    print("[PASS] Entangle stub fires and logs correctly")

    print("\n" + "=" * 60)
    print("  All game_manager.py tests passed!")
    print("=" * 60)
