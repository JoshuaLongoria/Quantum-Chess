"""
entanglement_rules.py

Movement inheritance through quantum entanglement.

When pieces entangle, they form a group that inherits movement rules
from all pieces in the group. A piece can move using ANY of the combined
movement patterns.

Entanglement inheritance chart:
    Pawn    -> can inherit from Rook, Bishop, Knight
    Rook    -> can inherit from Pawn, Bishop, Knight
    Bishop  -> can inherit from Pawn, Rook, Knight
    Knight  -> can inherit from Pawn, Rook, Bishop, Queen
    Queen   -> can inherit from Knight
    King    -> cannot be entangled (immutable)
"""

from __future__ import annotations
from typing import Optional


# =========================================================================
# Entanglement Group Management
# =========================================================================

class EntanglementGroup:
    """
    Represents a group of entangled pieces that share movement rules.
    
    All pieces in a group can move using the combined movement patterns
    of every piece in the group.
    """
    
    def __init__(self, group_id: int, pieces: list[dict] = None):
        """
        Args:
            group_id: Unique ID for this entanglement group
            pieces: List of piece dicts in this group
        """
        self.group_id = group_id
        self.pieces: list[dict] = pieces or []
        self._next_group_id = 0
    
    def add_piece(self, piece: dict):
        """Add a piece to this entanglement group."""
        if piece not in self.pieces:
            self.pieces.append(piece)
            piece["entanglement_group"] = self.group_id
    
    def remove_piece(self, piece: dict):
        """Remove a piece from this group."""
        if piece in self.pieces:
            self.pieces.remove(piece)
            if "entanglement_group" in piece:
                del piece["entanglement_group"]
    
    def get_piece_types(self) -> set[str]:
        """Return set of all piece types in this group."""
        return {p["type"] for p in self.pieces}
    
    def is_empty(self) -> bool:
        """True if no pieces in group."""
        return len(self.pieces) == 0


def can_entangle(piece_a: dict, piece_b: dict) -> bool:
    """
    Check if two pieces can be entangled according to the rules.
    
    - King cannot be entangled with anything
    - A piece cannot be entangled with itself
    - A piece cannot be entangled with the same color/opponent
    
    Returns:
        True if entanglement is allowed
    """
    # Can't entangle with enemy
    if piece_a["color"] != piece_b["color"]:
        return False
    
    # Can't entangle with self
    if piece_a is piece_b:
        return False
    
    # King cannot be entangled
    if piece_a["type"] == "king" or piece_b["type"] == "king":
        return False
    
    # Already entangled?
    if (piece_a.get("entanglement_group") and 
        piece_a.get("entanglement_group") == piece_b.get("entanglement_group")):
        return False
    
    return True


def entangle_pieces(piece_a: dict, piece_b: dict, board) -> str:
    """
    Entangle two pieces, combining their movement rules.
    
    Args:
        piece_a, piece_b: Piece dicts to entangle
        board: Board instance (for managing groups)
    
    Returns:
        Status message describing the entanglement
    """
    if not can_entangle(piece_a, piece_b):
        reasons = {
            "king": f"Kings cannot be entangled.",
            "enemy": f"Can only entangle your own pieces.",
            "self": f"Cannot entangle a piece with itself.",
            "already": f"These pieces are already entangled.",
        }
        
        if piece_a["type"] == "king" or piece_b["type"] == "king":
            return reasons["king"]
        if piece_a["color"] != piece_b["color"]:
            return reasons["enemy"]
        if piece_a is piece_b:
            return reasons["self"]
        if (piece_a.get("entanglement_group") == piece_b.get("entanglement_group")):
            return reasons["already"]
    
    # Merge groups
    group_a = piece_a.get("entanglement_group")
    group_b = piece_b.get("entanglement_group")
    
    if group_a is None and group_b is None:
        # Both uncoupled — create new group
        new_group = board.create_entanglement_group([piece_a, piece_b])
        msg = (f"{piece_a['type'].capitalize()} + {piece_b['type'].capitalize()} "f"entangled! Combined movement rules active.")
    
    elif group_a is not None and group_b is None:
        # Add piece_b to group_a
        group = board.get_entanglement_group(group_a)
        group.add_piece(piece_b)
        pieces_str = ", ".join(p["type"] for p in group.pieces)
        msg = (f"{piece_b['type'].capitalize()} joins entanglement group. "
               f"Group now has: {pieces_str}")
    
    elif group_a is None and group_b is not None:
        # Add piece_a to group_b
        group = board.get_entanglement_group(group_b)
        group.add_piece(piece_a)
        pieces_str = ", ".join(p["type"] for p in group.pieces)
        msg = (f"{piece_a['type'].capitalize()} joins entanglement group. "
               f"Group now has: {pieces_str}")
    
    else:
        # Both in groups — merge them
        group_a_obj = board.get_entanglement_group(group_a)
        group_b_obj = board.get_entanglement_group(group_b)
        merged = board.merge_entanglement_groups(group_a, group_b)
        pieces_str = ", ".join(p["type"] for p in merged.pieces)
        msg = f"Entanglement groups merged! Now: {pieces_str}"
    
    return msg


def break_entanglement(piece: dict, board) -> str:
    """
    Break a piece's entanglement (e.g., when captured or measured).
    
    Returns:
        Status message
    """
    group_id = piece.get("entanglement_group")
    if group_id is None:
        return ""  # Not entangled
    
    group = board.get_entanglement_group(group_id)
    if group is None:
        return ""
    
    group.remove_piece(piece)
    msg = f"{piece['type'].capitalize()} entanglement broken."
    
    if group.is_empty():
        board.remove_entanglement_group(group_id)
    
    return msg


# =========================================================================
# Movement Inheritance
# =========================================================================

def get_inherited_piece_types(piece: dict, board) -> set[str]:
    """
    Get all piece types that an entangled piece can move like.
    
    If piece is in an entanglement group, returns all types in the group.
    Otherwise returns just the piece's own type.
    
    Returns:
        set of piece type strings: {"pawn", "rook", "bishop", ...}
    """
    group_id = piece.get("entanglement_group")
    
    if group_id is not None:
        group = board.get_entanglement_group(group_id)
        if group:
            return group.get_piece_types()
    
    return {piece["type"]}


def get_combined_legal_moves(piece: dict, board) -> list[str]:
    """
    Get legal moves for an entangled piece (or regular piece).
    
    For an entangled piece, computes the union of all legal moves
    that any piece type in the group could make from the same square.
    
    Args:
        piece: Piece dict
        board: Board instance
    
    Returns:
        List of algebraic square strings (combined moves)
    """
    # Superposed pieces can't move
    if piece.get("superposed"):
        return []
    
    origin = piece["positions"][0]
    group_id = piece.get("entanglement_group")
    
    if group_id is None:
        # Not entangled — just use normal move generation
        return board.get_legal_moves_single_type(piece["type"], origin, piece["color"])
    
    # Entangled — get moves for all piece types in the group
    group = board.get_entanglement_group(group_id)
    if not group:
        return board.get_legal_moves_single_type(piece["type"], origin, piece["color"])
    
    all_moves = set()
    for piece_type in group.get_piece_types():
        moves = board.get_legal_moves_single_type(piece_type, origin, piece["color"])
        all_moves.update(moves)
    
    return list(all_moves)


# =========================================================================
# Entanglement State Queries
# =========================================================================

def get_entanglement_info(piece: dict, board) -> dict:
    """
    Get detailed information about a piece's entanglement state.
    
    Returns:
        {
            "is_entangled": bool,
            "group_id": int or None,
            "group_pieces": [piece types],
            "combined_moves": int (count of available moves)
        }
    """
    group_id = piece.get("entanglement_group")
    
    if group_id is None:
        return {
            "is_entangled": False,
            "group_id": None,
            "group_pieces": [piece["type"]],
            "combined_moves": len(board.get_legal_moves_for_type(
                piece["type"], piece["positions"][0], piece["color"]
            ))
        }
    
    group = board.get_entanglement_group(group_id)
    if not group:
        return {
            "is_entangled": False,
            "group_id": None,
            "group_pieces": [piece["type"]],
            "combined_moves": 0
        }
    
    return {
        "is_entangled": True,
        "group_id": group_id,
        "group_pieces": sorted(group.get_piece_types()),
        "combined_moves": len(get_combined_legal_moves(piece, board))
    }


# =========================================================================
# Visualization Helpers
# =========================================================================

def get_entanglement_indicator(piece: dict) -> str:
    """
    Get a short symbol for the piece's entanglement state.
    
    Used in HUD or piece display:
        "∞" = entangled
        "?" = superposed
        "-" = normal
    """
    if piece.get("entanglement_group") is not None:
        return "∞"
    elif piece.get("superposed"):
        return "?"
    return "-"


def format_entanglement_display(piece: dict, board) -> str:
    """
    Get a human-readable string describing entanglement.
    
    Example: "Rook (∞ entangled with pawn, bishop)"
    """
    info = get_entanglement_info(piece, board)
    
    if not info["is_entangled"]:
        return piece["type"].capitalize()
    
    # Remove the piece's own type from the display
    other_types = [t for t in info["group_pieces"] if t != piece["type"]]
    if other_types:
        return f"{piece['type'].capitalize()} (∞ + {', '.join(other_types)})"
    
    return piece["type"].capitalize()


# =========================================================================
# Tests
# =========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  entanglement_rules.py — Entanglement Tests")
    print("=" * 60)
    
    # Test 1: Can entangle?
    pawn = {"type": "pawn", "color": "white", "positions": ["a2"], "superposed": False}
    rook = {"type": "rook", "color": "white", "positions": ["a1"], "superposed": False}
    king = {"type": "king", "color": "white", "positions": ["e1"], "superposed": False}
    enemy = {"type": "pawn", "color": "black", "positions": ["a4"], "superposed": False}
    
    assert can_entangle(pawn, rook) == True
    assert can_entangle(pawn, king) == False
    assert can_entangle(pawn, enemy) == False
    assert can_entangle(pawn, pawn) == False
    print("\n[PASS] can_entangle() validation works")
    
    # Test 2: Entanglement group creation
    group = EntanglementGroup(1, [pawn, rook])
    assert len(group.pieces) == 2
    assert group.get_piece_types() == {"pawn", "rook"}
    print("[PASS] EntanglementGroup creation works")
    
    # Test 3: Add/remove pieces
    bishop = {"type": "bishop", "color": "white", "positions": ["c1"], "superposed": False}
    group.add_piece(bishop)
    assert len(group.pieces) == 3
    assert "bishop" in group.get_piece_types()
    group.remove_piece(bishop)
    assert len(group.pieces) == 2
    print("[PASS] Add/remove pieces from group works")
    
    # Test 4: Indicator display
    assert get_entanglement_indicator(pawn) == "-"
    pawn["entanglement_group"] = 1
    assert get_entanglement_indicator(pawn) == "∞"
    pawn["superposed"] = True
    assert get_entanglement_indicator(pawn) == "?"  # superposed takes priority
    print("[PASS] Entanglement indicator display works")
    
    print("\n" + "=" * 60)
    print("  All entanglement_rules.py tests passed!")
    print("=" * 60)
