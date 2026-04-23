#Board state, piece positions, classical move logic

"""
board.py
--------
Luis — Game Logic | Quantum Chess
CS5331/4331 Introduction to Quantum Computing | Texas Tech University

Classical board state and move-rule engine.

Responsibilities:
  - Initialise the standard 32-piece starting position
  - Store every piece using the shared data contract 
  - Generate legal classical moves for any piece
  - Validate and execute classical moves (single-square to single-square)
  - Detect check (is a king under attack?)
  - Detect checkmate and stalemate
  - Provide helper look-ups (piece-at-square, all-pieces-for-colour, …)

The module is deliberately *classical only*.  Quantum extensions
(superposition move, entangle move, measure / collapse) live in
quantum_rules.py, which imports this module and mutates board state
through the public API below.

Coordinate conventions
  - Algebraic notation throughout:  files a-h, ranks 1-8
  - Internal helpers convert to (col, row) grid when needed
    col 0 = 'a', col 7 = 'h'
    row 0 = rank 8 (top of screen), row 7 = rank 1 (bottom)
  - This matches the renderer's algebraic_to_grid() function.

Shared data contract:
    piece = {
        "type":           "knight",          # king, queen, rook, bishop, knight, pawn
        "color":          "white",           # "white" or "black"
        "positions":      ["e4"],            # classical: one square
        "superposed":     False,             # True when in superposition
        "qubit_id":       3,                 # index in the quantum register
        "entangled_with": [],                # qubit IDs of entangled partners
    }
---------------------------------------------------------------------------
"""

#4/4 changed _to_grid() to to_grid() and _to_alg() to to_alg() for consistency with renderer.py

from __future__ import annotations
from typing import Optional
from entanglement_rules import (EntanglementGroup, 
                                get_combined_legal_moves, 
                                break_entanglement,
                                )

# -------------------------------------------------------------------------
# Coordinate helpers
# -------------------------------------------------------------------------

FILES = "abcdefgh"
RANKS = "12345678"

_BISHOP_DIRS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
_ROOK_DIRS   = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_QUEEN_DIRS  = _BISHOP_DIRS + _ROOK_DIRS


def to_grid(pos: str) -> tuple[int, int]:
    """Algebraic (e.g. 'e4') → (col, row) with row 0 = rank 8."""
    col = ord(pos[0]) - ord('a')
    row = 8 - int(pos[1])
    return col, row


def to_alg(col: int, row: int) -> str:
    """(col, row) → algebraic.  row 0 = rank 8."""
    return FILES[col] + str(8 - row)


def _on_board(col: int, row: int) -> bool:
    return 0 <= col < 8 and 0 <= row < 8


# -------------------------------------------------------------------------
# Board class
# -------------------------------------------------------------------------

class Board:
    """
    Full classical board state for Quantum Chess.

    Pieces are stored in a flat list (self.pieces) using the shared dict
    format.  A dict self._square_map caches {square_string: piece_dict}
    for O(1) occupancy look-ups.  The map must be rebuilt whenever pieces
    move — call _rebuild_map() after any mutation.

    Quantum extensions in quantum_rules.py will call the public helpers
    (piece_at, move_piece, remove_piece, add_piece, …) to keep this
    module unaware of qubits.
    """

    def __init__(self):
        self.pieces: list[dict] = []
        self._square_map: dict[str, dict] = {}
        self._next_qubit_id: int = 0        # auto-increment qubit IDs
        self._setup_initial_position()
        self._entanglement_groups: dict[int, EntanglementGroup] = {}  # group_id -> group data
        self._next_group_id = 0  # auto-increment group IDs

    # ------------------------------------------------------------------
    # Initial position
    # ------------------------------------------------------------------

    def _make_piece(self, ptype: str, color: str, pos: str) -> dict:
        """Create a piece dict that follows the shared data contract."""
        ## added entanglement_group: None to the piece dict for group management
        piece = {
            "type":           ptype,
            "color":          color,
            "positions":      [pos],
            "superposed":     False,
            "qubit_id":       self._next_qubit_id,
            "entangled_with": [],
            "entanglement_group": None,
        }
        self._next_qubit_id += 1
        return piece

    def _setup_initial_position(self):
        """Place all 32 pieces in the standard FIDE starting position."""
        # Back-rank order for both colours
        back_rank = ["rook", "knight", "bishop", "queen",
                     "king", "bishop", "knight", "rook"]

        # White pieces — rank 1 (row 7) and rank 2 (row 6)
        for i, ptype in enumerate(back_rank):
            sq = to_alg(i, 7)                       # a1 … h1
            self.pieces.append(self._make_piece(ptype, "white", sq))
        for i in range(8):
            sq = to_alg(i, 6)                       # a2 … h2
            self.pieces.append(self._make_piece("pawn", "white", sq))

        # Black pieces — rank 8 (row 0) and rank 7 (row 1)
        for i, ptype in enumerate(back_rank):
            sq = to_alg(i, 0)                       # a8 … h8
            self.pieces.append(self._make_piece(ptype, "black", sq))
        for i in range(8):
            sq = to_alg(i, 1)                       # a7 … h7
            self.pieces.append(self._make_piece("pawn", "black", sq))

        self._rebuild_map()

    # ------------------------------------------------------------------
    # Internal square map
    # ------------------------------------------------------------------

    def _rebuild_map(self):
        """
        Rebuild the {square: piece} look-up from self.pieces.

        A superposed piece occupies TWO squares — both are stored in the
        map so that occupancy checks and capture logic work correctly.
        """
        self._square_map = {}
        for p in self.pieces:
            for sq in p["positions"]:
                self._square_map[sq] = p

    # ------------------------------------------------------------------
    # Public look-up helpers
    # ------------------------------------------------------------------

    def piece_at(self, square: str) -> Optional[dict]:
        """Return the piece on *square* or None if empty."""
        return self._square_map.get(square)

    def pieces_by_color(self, color: str) -> list[dict]:
        """Return all living pieces of a given colour."""
        return [p for p in self.pieces if p["color"] == color]

    def find_king(self, color: str) -> Optional[dict]:
        """Return the king piece for *color*, or None (should never be None)."""
        for p in self.pieces:
            if p["type"] == "king" and p["color"] == color:
                return p
        return None

    def all_squares_attacked_by(self, color: str) -> set[str]:
        """
        Return the set of squares that *color* attacks.

        Used for check detection. Superposed (ghost) pieces are excluded —
        they don't threaten squares until measured or captured.
        """
        attacked: set[str] = set()
        for piece in self.pieces_by_color(color):
            if piece.get("superposed"):
                continue  # ghosts don't threaten anything
            for origin in piece["positions"]:
                attacked.update(
                    self._raw_attacks(piece, origin)
                )
        return attacked

    # ------------------------------------------------------------------
    # Move execution
    # ------------------------------------------------------------------

    def move_piece(self, piece: dict, target: str):
        """
        Execute a classical move: move *piece* to *target*.

        If *target* is occupied by an opponent, that piece is captured
        (removed from self.pieces).

        Pawn promotion: auto-queen when a pawn reaches the last rank.
        """
        occupant = self.piece_at(target)
        if occupant is not None and occupant is not piece:
            self.remove_piece(occupant)

        # Update position — collapse to single classical square
        piece["positions"] = [target]
        piece["superposed"] = False

        # Auto-queen promotion
        _, row = to_grid(target)
        if piece["type"] == "pawn":
            if (piece["color"] == "white" and row == 0) or \
               (piece["color"] == "black" and row == 7):
                piece["type"] = "queen"

        self._rebuild_map()

    def remove_piece(self, piece: dict):
        """Remove *piece* from the board (capture / collapse away)."""
        from quantum_rules import break_entanglement_on_capture
        msg = break_entanglement_on_capture(self, piece)

        if piece in self.pieces:
            self.pieces.remove(piece)
        self._rebuild_map()

    def add_piece(self, piece: dict):
        """Add a piece to the board (used by quantum_rules for splits)."""
        self.pieces.append(piece)
        self._rebuild_map()

    # ------------------------------------------------------------------
    # Check / checkmate / stalemate
    # ------------------------------------------------------------------

    def is_in_check(self, color: str) -> bool:
        """Return True if *color*'s king is in check."""
        king = self.find_king(color)
        if king is None:
            return False
        opponent = "black" if color == "white" else "white"
        attacked = self.all_squares_attacked_by(opponent)
        # King might be superposed — check all its positions
        return any(sq in attacked for sq in king["positions"])

    def king_square_if_in_check(self, color: str) -> Optional[str]:
        """Return the algebraic square of *color*'s king if in check, else None."""
        if self.is_in_check(color):
            king = self.find_king(color)
            return king["positions"][0] if king else None
        return None

    def has_any_legal_move(self, color: str) -> bool:
        """Return True if *color* has at least one legal move."""
        for piece in self.pieces_by_color(color):
            if self.get_legal_moves(piece):
                return True
        return False

    def is_checkmate(self, color: str) -> bool:
        """True if *color* is in check and has no legal moves."""
        return self.is_in_check(color) and not self.has_any_legal_move(color)

    def is_stalemate(self, color: str) -> bool:
        """True if *color* is NOT in check but has no legal moves."""
        return (not self.is_in_check(color)) and (not self.has_any_legal_move(color))

    # ------------------------------------------------------------------
    # Legal move generation
    # ------------------------------------------------------------------

    def get_legal_moves(self, piece: dict) -> list[str]:
        """Get legal moves, accounting for entanglement."""
        if piece.get("superposed"):
            return []
        
        group_id = piece.get("entanglement_group")
        if group_id is None:
            return self.get_legal_moves_single_type(piece["type"], piece["positions"][0], piece["color"])
        return get_combined_legal_moves(piece, self)
    
    # ------------------------------------------------------------------
    # Pseudo-legal generation (ignores check legality)
    # ------------------------------------------------------------------

    def get_legal_moves_single_type(self, piece_type: str, origin: str, color: str) -> list[str]:
        """Get moves for a piece type from a square."""
        #create a dummy piece dict to reuse existing move generation logic
        temp_piece = {"type": piece_type, "color": color}
    
        if piece_type == "pawn":
            return self._pawn_moves(temp_piece, origin)
        elif piece_type == "rook":
            return self._sliding_moves(temp_piece, origin, _ROOK_DIRS)
        elif piece_type == "bishop":
            return self._sliding_moves(temp_piece, origin, _BISHOP_DIRS)
        elif piece_type == "knight":
            return self._knight_moves(temp_piece, origin)
        elif piece_type == "queen":
            return self._sliding_moves(temp_piece, origin, _QUEEN_DIRS)
        elif piece_type == "king":
            return self._king_moves(temp_piece, origin)
        
        return []

        # --- directional constants (module-level aliases used below) ---------

    # --- individual piece movers -----------------------------------------

    def _pawn_moves(self, piece: dict, origin: str) -> list[str]:
        """Generate pseudo-legal pawn moves (advance + capture)."""
        moves: list[str] = []
        color = piece["color"]
        col, row = to_grid(origin)
        direction = -1 if color == "white" else 1      # white moves up (row--)

        # Single push
        r1 = row + direction
        if _on_board(col, r1):
            sq1 = to_alg(col, r1)
            if self.piece_at(sq1) is None:
                moves.append(sq1)

                # Double push from starting rank
                start_row = 6 if color == "white" else 1
                if row == start_row:
                    r2 = row + 2 * direction
                    sq2 = to_alg(col, r2)
                    if self.piece_at(sq2) is None:
                        moves.append(sq2)

        # Diagonal captures
        for dc in (-1, 1):
            nc = col + dc
            nr = row + direction
            if _on_board(nc, nr):
                sq = to_alg(nc, nr)
                occupant = self.piece_at(sq)
                if occupant is not None and occupant["color"] != color:
                    moves.append(sq)

        return moves

    def _knight_moves(self, piece: dict, origin: str) -> list[str]:
        """Generate pseudo-legal knight jumps."""
        moves: list[str] = []
        col, row = to_grid(origin)
        offsets = [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                   (1, -2), (1, 2), (2, -1), (2, 1)]
        for dc, dr in offsets:
            nc, nr = col + dc, row + dr
            if _on_board(nc, nr):
                sq = to_alg(nc, nr)
                occupant = self.piece_at(sq)
                if occupant is None or occupant["color"] != piece["color"]:
                    moves.append(sq)
        return moves

    def _sliding_moves(self, piece: dict, origin: str,
                       directions: list[tuple[int, int]]) -> list[str]:
        """Generate pseudo-legal moves for sliding pieces (bishop/rook/queen)."""
        moves: list[str] = []
        col, row = to_grid(origin)
        for dc, dr in directions:
            nc, nr = col + dc, row + dr
            while _on_board(nc, nr):
                sq = to_alg(nc, nr)
                occupant = self.piece_at(sq)
                if occupant is None:
                    moves.append(sq)
                elif occupant["color"] != piece["color"]:
                    moves.append(sq)           # capture — then stop sliding
                    break
                else:
                    break                      # own piece blocks
                nc += dc
                nr += dr
        return moves

    def _king_moves(self, piece: dict, origin: str) -> list[str]:
        """Generate pseudo-legal king moves (one step in any direction)."""
        moves: list[str] = []
        col, row = to_grid(origin)
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if dc == 0 and dr == 0:
                    continue
                nc, nr = col + dc, row + dr
                if _on_board(nc, nr):
                    sq = to_alg(nc, nr)
                    occupant = self.piece_at(sq)
                    if occupant is None or occupant["color"] != piece["color"]:
                        moves.append(sq)
        return moves

    # ------------------------------------------------------------------
    # Attack generation (for check detection)
    # ------------------------------------------------------------------

    def _raw_attacks(self, piece: dict, origin: str) -> list[str]:
        """
        Squares a piece ATTACKS from *origin* (not the same as legal moves
        for pawns — pawns attack diagonally, not forward).
        """
        ptype = piece["type"]
        color = piece["color"]
        
        if ptype == "pawn":
            return self._pawn_attacks(piece, origin)
        
        # Switch based on the piece type to call the existing internal helpers
        if ptype == "rook":
            return self._sliding_moves(piece, origin, _ROOK_DIRS)
        elif ptype == "bishop":
            return self._sliding_moves(piece, origin, _BISHOP_DIRS)
        elif ptype == "queen":
            return self._sliding_moves(piece, origin, _QUEEN_DIRS)
        elif ptype == "knight":
            return self._knight_moves(piece, origin)
        elif ptype == "king":
            return self._king_moves(piece, origin)
            
        return []

    def _pawn_attacks(self, piece: dict, origin: str) -> list[str]:
        """Squares a pawn threatens (diagonals only, regardless of occupancy)."""
        attacks: list[str] = []
        col, row = to_grid(origin)
        direction = -1 if piece["color"] == "white" else 1
        for dc in (-1, 1):
            nc, nr = col + dc, row + direction
            if _on_board(nc, nr):
                attacks.append(to_alg(nc, nr))
        return attacks

    # ------------------------------------------------------------------
    # Safety filter (does a move leave own king in check?)
    # ------------------------------------------------------------------

    def _is_move_safe(self, piece: dict, origin: str, target: str) -> bool:
        """
        Simulate moving *piece* from *origin* to *target* and return True
        if the moving side's king is NOT in check afterwards.

        We do this non-destructively by temporarily mutating state, testing,
        then rolling back.  This is the standard approach in move generators.
        """
        # Save state
        old_positions = piece["positions"][:]
        captured = self.piece_at(target)
        captured_in_list = captured in self.pieces if captured else False

        # Apply tentative move
        piece["positions"] = [target]
        if captured is not None and captured is not piece:
            if captured in self.pieces:
                self.pieces.remove(captured)
        self._rebuild_map()

        # Test
        safe = not self.is_in_check(piece["color"])

        # Rollback
        piece["positions"] = old_positions
        if captured is not None and captured_in_list and captured not in self.pieces:
            self.pieces.append(captured)
        self._rebuild_map()

        return safe

    # ------------------------------------------------------------------
    # Serialisation helpers (for renderer / game_manager)
    # ------------------------------------------------------------------

    def get_pieces_list(self) -> list[dict]:
        """
        Return the live piece list.

        renderer.render_frame() expects exactly this list under the
        "pieces" key of the game_state dict.
        """
        return self.pieces
    # ------------------------------------------------------------------
    # Entanglement group management
    # ------------------------------------------------------------------

    # Note: The board manages entanglement groups, but the quantum_rules
    # module handles the logic of creating, merging, and breaking them based

    def next_qubit_id(self) -> int:
        """Reserve and return the next available qubit ID."""
        qid = self._next_qubit_id
        self._next_qubit_id += 1
        return qid
    def create_entanglement_group(self, pieces: list[dict]) -> EntanglementGroup:
        group_id = self._next_group_id
        self._next_group_id += 1
        group = EntanglementGroup(group_id, pieces)
        self._entanglement_groups[group_id] = group
        for piece in pieces:
            piece["entanglement_group"] = group_id
        return group

    def get_entanglement_group(self, group_id: int) -> EntanglementGroup | None:
        return self._entanglement_groups.get(group_id)

    def merge_entanglement_groups(self, group_id_a: int, group_id_b: int) -> EntanglementGroup:
        group_a = self._entanglement_groups.get(group_id_a)
        group_b = self._entanglement_groups.get(group_id_b)
        if not group_a or not group_b:
            return None
        for piece in group_b.pieces:
            piece["entanglement_group"] = group_id_a
            group_a.add_piece(piece)
        del self._entanglement_groups[group_id_b]
        return group_a

    def remove_entanglement_group(self, group_id: int):
        if group_id in self._entanglement_groups:
            del self._entanglement_groups[group_id]

# =========================================================================
# Standalone test — run with:  python board.py
# =========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  board.py — Classical Board State Tests")
    print("=" * 60)

    b = Board()

    # --- Test 1: piece count ---
    assert len(b.pieces) == 32, f"Expected 32 pieces, got {len(b.pieces)}"
    print(f"\n[PASS] Initial piece count: {len(b.pieces)}")

    # --- Test 2: piece-at look-up ---
    e1 = b.piece_at("e1")
    assert e1 is not None and e1["type"] == "king" and e1["color"] == "white"
    print(f"[PASS] e1 = white king  (qubit_id {e1['qubit_id']})")

    e8 = b.piece_at("e8")
    assert e8 is not None and e8["type"] == "king" and e8["color"] == "black"
    print(f"[PASS] e8 = black king  (qubit_id {e8['qubit_id']})")

    d1 = b.piece_at("d1")
    assert d1 is not None and d1["type"] == "queen" and d1["color"] == "white"
    print(f"[PASS] d1 = white queen (qubit_id {d1['qubit_id']})")

    empty = b.piece_at("e4")
    assert empty is None
    print("[PASS] e4 is empty")

    # --- Test 3: pawn legal moves from starting position ---
    pawn_e2 = b.piece_at("e2")
    moves_e2 = b.get_legal_moves(pawn_e2)
    assert "e3" in moves_e2 and "e4" in moves_e2, f"e2 pawn moves: {moves_e2}"
    assert len(moves_e2) == 2, f"Expected 2 moves for e2 pawn, got {moves_e2}"
    print(f"[PASS] e2 pawn legal moves: {sorted(moves_e2)}")

    # --- Test 4: knight legal moves from starting position ---
    knight_b1 = b.piece_at("b1")
    moves_b1 = b.get_legal_moves(knight_b1)
    assert "a3" in moves_b1 and "c3" in moves_b1
    print(f"[PASS] b1 knight legal moves: {sorted(moves_b1)}")

    # --- Test 5: execute a move ---
    b.move_piece(pawn_e2, "e4")
    assert b.piece_at("e4") is pawn_e2
    assert b.piece_at("e2") is None
    print("[PASS] Moved e2 pawn to e4")

    # --- Test 6: check detection (simple checkmate) ---
    # White: Kf6, Qg7.  Black: Kh8.
    # Queen on g7 attacks h8 diagonally → check.
    # h8 king's only neighbours (g8, g7, h7) are all covered → checkmate.
    b2 = Board()
    b2.pieces.clear()
    b2._next_qubit_id = 0
    wk = b2._make_piece("king",  "white", "f6")
    wq = b2._make_piece("queen", "white", "g7")
    bk = b2._make_piece("king",  "black", "h8")
    b2.pieces = [wk, wq, bk]
    b2._rebuild_map()

    assert b2.is_in_check("black"), "Black should be in check"
    assert b2.is_checkmate("black"), "Black should be in checkmate"
    print("[PASS] Checkmate detection works")

    # --- Test 7: stalemate detection ---
    b3 = Board()
    b3.pieces.clear()
    b3._next_qubit_id = 0
    wk3 = b3._make_piece("king",  "white", "f6")
    wq3 = b3._make_piece("queen", "white", "g6")
    bk3 = b3._make_piece("king",  "black", "h8")
    b3.pieces = [wk3, wq3, bk3]
    b3._rebuild_map()
    # Black to move — h8 king has no legal moves, not in check = stalemate
    assert b3.is_stalemate("black"), "Should be stalemate"
    print("[PASS] Stalemate detection works")

    print("\n" + "=" * 60)
    print("  All board.py tests passed!")
    print("=" * 60)
