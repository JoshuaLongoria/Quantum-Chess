"""
board_entanglement_extensions.py

Add these methods to your Board class in board.py

Manages entanglement groups and integrates with movement calculation.
"""

# Add these imports at the top of board.py
from entanglement_rules import (
    EntanglementGroup,
    get_combined_legal_moves,
    break_entanglement,
)


class Board_EntanglementExtensions:
    """
    Add these methods to your existing Board class.
    
    Handles:
    - Creating and managing entanglement groups
    - Tracking which pieces belong to which groups
    - Merging groups when pieces with existing groups entangle
    - Cleanup when pieces are captured
    """
    
    def __init__(self):
        """Add these to your Board.__init__()"""
        self._entanglement_groups: dict[int, EntanglementGroup] = {}
        self._next_group_id = 0
    
    # =====================================================================
    # Group Management
    # =====================================================================
    
    def create_entanglement_group(self, pieces: list[dict]) -> EntanglementGroup:
        """
        Create a new entanglement group with the given pieces.
        
        Args:
            pieces: List of piece dicts to group together
        
        Returns:
            The newly created EntanglementGroup
        """
        group_id = self._next_group_id
        self._next_group_id += 1
        
        group = EntanglementGroup(group_id, pieces)
        self._entanglement_groups[group_id] = group
        
        # Mark each piece with the group ID
        for piece in pieces:
            piece["entanglement_group"] = group_id
        
        return group
    
    def get_entanglement_group(self, group_id: int) -> EntanglementGroup | None:
        """Get an entanglement group by ID."""
        return self._entanglement_groups.get(group_id)
    
    def merge_entanglement_groups(self, group_id_a: int, group_id_b: int) -> EntanglementGroup:
        """
        Merge two entanglement groups into one.
        
        All pieces from both groups now form a single group with combined
        movement rules.
        
        Args:
            group_id_a, group_id_b: IDs of groups to merge
        
        Returns:
            The merged EntanglementGroup
        """
        group_a = self._entanglement_groups.get(group_id_a)
        group_b = self._entanglement_groups.get(group_id_b)
        
        if not group_a or not group_b:
            return None
        
        # Move all pieces from group_b into group_a
        for piece in group_b.pieces:
            piece["entanglement_group"] = group_id_a
            group_a.add_piece(piece)
        
        # Remove group_b
        del self._entanglement_groups[group_id_b]
        
        return group_a
    
    def remove_entanglement_group(self, group_id: int):
        """Delete an entanglement group (used after all pieces removed/captured)."""
        if group_id in self._entanglement_groups:
            del self._entanglement_groups[group_id]
    
    # =====================================================================
    # Integration with Move Calculation
    # =====================================================================
    
    def get_legal_moves(self, piece: dict) -> list[str]:
        """
        Get legal moves for a piece, accounting for entanglement.
        
        Replace your existing get_legal_moves() with this version.
        If the piece is entangled, returns combined moves from all
        pieces in the group.
        """
        # Superposed pieces can't move
        if piece.get("superposed"):
            return []
        
        # Check if piece is entangled
        group_id = piece.get("entanglement_group")
        
        if group_id is None:
            # Not entangled — use normal move calculation
            return self._get_legal_moves_single_type(piece)
        
        # Entangled — get combined moves
        return get_combined_legal_moves(piece, self)
    
    def _get_legal_moves_single_type(self, piece: dict) -> list[str]:
        """
        Get legal moves for a single piece type (not entangled).
        
        This is your existing move calculation logic.
        Rename your current get_legal_moves() to this.
        """
        # Your existing implementation here
        # For example:
        origin = piece["positions"][0]
        return self.get_legal_moves_for_type(piece["type"], origin, piece["color"])
    
    def get_legal_moves_for_type(self, piece_type: str, origin: str, color: str) -> list[str]:
        """
        Get legal moves for a specific piece type from an origin square.
        
        This is a helper used by both regular and entangled pieces.
        Implement this by extracting your piece-type-specific move logic.
        
        Example structure:
        ```python
        if piece_type == "pawn":
            return self._get_pawn_moves(origin, color)
        elif piece_type == "rook":
            return self._get_rook_moves(origin, color)
        # ... etc
        ```
        """
        # Your implementation
        raise NotImplementedError(
            "Implement this by extracting your piece type-specific move logic"
        )
    
    # =====================================================================
    # Capture Handling
    # =====================================================================
    
    def remove_piece(self, piece: dict):
        """
        Remove a piece from the board.
        
        If the piece is entangled, break the entanglement.
        Add this to your existing remove_piece() method:
        """
        # Break entanglement if the piece is in a group
        msg = break_entanglement(piece, self)
        
        # Your existing removal logic
        # self.board[piece["positions"][0]] = None  (or however you store it)
    
    def get_all_entangled_pieces(self, piece: dict) -> list[dict]:
        """
        Get all pieces in an entanglement group with the given piece.
        
        Returns:
            List of piece dicts in the same group, including the original piece
        """
        group_id = piece.get("entanglement_group")
        if group_id is None:
            return [piece]
        
        group = self._entanglement_groups.get(group_id)
        if not group:
            return [piece]
        
        return group.pieces
    
    def get_entanglement_stats(self) -> dict:
        """
        Get statistics about entanglement on the board.
        
        Returns:
            {
                "total_groups": int,
                "total_entangled_pieces": int,
                "groups": [
                    {"id": int, "pieces": [piece_types], "size": int},
                    ...
                ]
            }
        """
        stats = {
            "total_groups": len(self._entanglement_groups),
            "total_entangled_pieces": 0,
            "groups": []
        }
        
        for group_id, group in self._entanglement_groups.items():
            stats["total_entangled_pieces"] += len(group.pieces)
            stats["groups"].append({
                "id": group_id,
                "pieces": sorted(group.get_piece_types()),
                "size": len(group.pieces)
            })
        
        return stats
    
    # =====================================================================
    # Debugging & Display
    # =====================================================================
    
    def print_entanglement_state(self):
        """Print current entanglement groups (useful for debugging)."""
        if not self._entanglement_groups:
            print("[Entanglement] No entangled pieces")
            return
        
        print("[Entanglement] Current groups:")
        for group_id, group in self._entanglement_groups.items():
            piece_info = ", ".join([
                f"{p['type']}@{p['positions'][0]}"
                for p in group.pieces
            ])
            print(f"  Group {group_id}: {piece_info}")


# =========================================================================
# INTEGRATION INSTRUCTIONS
# =========================================================================

"""
To integrate into your existing board.py:

1. Add imports at the top:
   from entanglement_rules import (
       EntanglementGroup,
       get_combined_legal_moves,
       break_entanglement,
   )

2. In Board.__init__(), add:
   self._entanglement_groups: dict[int, EntanglementGroup] = {}
   self._next_group_id = 0

3. Replace your get_legal_moves(piece) method with the new version above.

4. In your move-calculation code, break it into:
   - get_legal_moves_for_type(piece_type, origin, color)
   
   This allows both regular and entangled pieces to use the same logic.

5. Update remove_piece() to call break_entanglement().

6. Add the helper/debugging methods as needed.

Example move calculation refactor:

OLD:
    def get_legal_moves(self, piece):
        if piece['type'] == 'pawn':
            return self._get_pawn_moves(piece)
        elif piece['type'] == 'rook':
            return self._get_rook_moves(piece)
        # ...

NEW:
    def get_legal_moves(self, piece):
        if piece.get("superposed"):
            return []
        group_id = piece.get("entanglement_group")
        if group_id is None:
            return self._get_legal_moves_single_type(piece)
        return get_combined_legal_moves(piece, self)
    
    def _get_legal_moves_single_type(self, piece):
        origin = piece['positions'][0]
        return self.get_legal_moves_for_type(piece['type'], origin, piece['color'])
    
    def get_legal_moves_for_type(self, piece_type, origin, color):
        if piece_type == 'pawn':
            return self._get_pawn_moves_from(origin, color)
        # ... refactored to take (origin, color) instead of (piece)
"""
