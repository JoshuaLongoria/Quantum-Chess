# Superposition move, entangle move stub, measure/collapse logic
"""
quantum_rules.py

Quantum move rules that extend the classical board.

Three quantum moves:
    superposition_move(board, engine, piece, sq_a, sq_b)
        Split a piece across two squares (H gate).

    collapse_piece(board, engine, piece)
        Force-measure a superposed piece, collapsing it to one square.

    capture_superposed(board, engine, attacker, target_piece, capture_sq)
        Attempt to capture a superposed piece; triggers a quantum
        measurement — the capture succeeds only if the piece collapses
        to the contested square.

All functions mutate board state through board.py's public API and
return a short human-readable string for the game_manager event log.
"""

from __future__ import annotations
from board import Board
# Use unified QuantumBackend from Entanglement.py (replaces Quantum_engin.py)
from Entanglement import QuantumBackend


# ---------------------------------------------------------------------------
# Superposition move
# ---------------------------------------------------------------------------

def superposition_move(board: Board, engine: QuantumBackend,
                       piece: dict, sq_a: str, sq_b: str) -> str:
    """
    Split *piece* into superposition across sq_a and sq_b.

    Applies an H gate to the piece's qubit, then sets its positions list
    to [sq_a, sq_b] so the board and renderer treat it as a ghost piece
    on both squares.

    Rules:
      - The piece must currently be at sq_a (its classical position).
      - sq_b must be a valid destination for that piece type (caller
        is responsible for validating this before calling).
      - The piece cannot already be superposed or entangled.

    Returns a log string.
    """
    if piece["superposed"]:
        return f"{piece['type'].capitalize()} is already in superposition."

    if piece["entangled_with"] or piece.get("entanglement_group") is not None:
        return f"{piece['type'].capitalize()} is entangled — cannot split."

    engine.apply_hadamard(piece["qubit_id"])
    piece["positions"] = [sq_a, sq_b]
    piece["superposed"] = True
    board._rebuild_map()

    symbol = piece["type"].capitalize()
    color  = piece["color"].capitalize()
    return f"{color} {symbol} split -> {sq_a} <-> {sq_b}"


# ---------------------------------------------------------------------------
# Entangle move (stub — waiting for Entanglement.py)
# ---------------------------------------------------------------------------

def entangle_move(board: Board, engine: QuantumBackend,
                   piece_a: dict, piece_b: dict) -> str:
    """
    Link piece_a and piece_b into a Bell state via QuantumBackend.

    Creates quantum entanglement between two pieces — when either is
    measured, both collapse to the same outcome (correlated measurement).

    Rules:
      - Both pieces must be classical (not superposed, not entangled)
      - Both pieces must be on the board
      - After entangling, both pieces share entangled_with list

    Returns a log string.
    """
    """
    MINIMAL FIX FOR quantum_rules.py
    
    Replace entangle_move() function with this version that:
    1. Still does quantum entanglement
    2. ALSO creates a movement group so pieces share moves
    """
    # Validate both pieces are classical
    if piece_a["superposed"] or piece_b["superposed"]:
        return "Cannot entangle: one or both pieces are in superposition."

    if piece_a["entangled_with"] or piece_b["entangled_with"]:
        return "Cannot entangle: one or both pieces are already entangled."

    if piece_a["color"] != piece_b["color"]:
        return "Cannot entangle: must be your own pieces."
    
    if piece_a is piece_b:
        return "Cannot entangle a piece with itself."
    
    if piece_a["type"] == "king" or piece_b["type"] == "king":
        return "Kings cannot be entangled."
    
    # Create QUANTUM entanglement
    engine.entangle(piece_a["qubit_id"], piece_b["qubit_id"])
    piece_a["entangled_with"].append(piece_b["qubit_id"])
    piece_b["entangled_with"].append(piece_a["qubit_id"])
    
    # CREATE MOVEMENT GROUP 
    from entanglement_rules import EntanglementGroup
    board.create_entanglement_group([piece_a, piece_b])
    
    sym_a = piece_a["type"].capitalize()
    sym_b = piece_b["type"].capitalize()
    pos_a = piece_a["positions"][0]
    pos_b = piece_b["positions"][0]
    return f"Entangled {sym_a}({pos_a}) <-> {sym_b}({pos_b}) [Bell state + movement group]"


def break_entanglement_on_capture(board: Board, captured_piece: dict):
    """
    Called when an entangled piece is captured.
    Breaks both quantum entanglement AND movement group.
    """
    # Handle quantum entanglement (old system)
    if captured_piece.get("entangled_with"):
        for partner_qubit_id in captured_piece["entangled_with"]:
            for p in board.pieces:
                if p["qubit_id"] == partner_qubit_id:
                    if captured_piece["qubit_id"] in p["entangled_with"]:
                        p["entangled_with"].remove(captured_piece["qubit_id"])
        captured_piece["entangled_with"] = []
    
    # Handle movement group (new system)
    group_id = captured_piece.get("entanglement_group")
    if group_id is not None:
        from entanglement_rules import break_entanglement
        msg = break_entanglement(captured_piece, board)
        return msg if msg else ""
    
    return ""


# ---------------------------------------------------------------------------
# Collapse / force-measure
# ---------------------------------------------------------------------------

def collapse_piece(board: Board, engine: QuantumBackend, piece: dict) -> str:
    """
    Force-measure a superposed piece, collapsing it to one square.

    Runs the H+measure circuit (via QuantumEngine.measure()), then
    discards the square the piece did NOT collapse to.

    If the piece is not superposed, this is a no-op.

    Returns a log string.
    """
    if not piece["superposed"]:
        return f"{piece['type'].capitalize()} is not in superposition."

    sq_a, sq_b = piece["positions"][0], piece["positions"][1]
    result = engine.measure_superposition(piece["qubit_id"])   # 0 → sq_a, 1 → sq_b
    collapsed_to = sq_a if result == 0 else sq_b

    piece["positions"] = [collapsed_to]
    piece["superposed"] = False
    board._rebuild_map()

    symbol = piece["type"].capitalize()
    color  = piece["color"].capitalize()
    return f"{color} {symbol} collapsed -> {collapsed_to}"


# ---------------------------------------------------------------------------
# Capture of a superposed piece
# ---------------------------------------------------------------------------

def capture_superposed(board: Board, engine: QuantumBackend,
                       attacker: dict, target_piece: dict,
                       capture_sq: str) -> str:
    """
    Attempt to capture a superposed piece.

    Triggers a quantum measurement on target_piece:
      - If target_piece collapses TO capture_sq  → capture succeeds,
        target_piece is removed from the board.
      - If target_piece collapses to the OTHER square → capture fails,
        target_piece survives at the other square as a classical piece.

    Returns a log string describing the outcome.
    """
    if not target_piece["superposed"]:
        # Classical capture — handled by board.move_piece normally.
        return ""

    sq_a, sq_b = target_piece["positions"][0], target_piece["positions"][1]
    result = engine.measure_superposition(target_piece["qubit_id"])
    collapsed_to = sq_a if result == 0 else sq_b

    target_piece["positions"] = [collapsed_to]
    target_piece["superposed"] = False

    atk_sym = attacker["type"].capitalize()
    tgt_sym = target_piece["type"].capitalize()
    tgt_col = target_piece["color"].capitalize()

    if collapsed_to == capture_sq:
        board.remove_piece(target_piece)
        board.move_piece(attacker, capture_sq)
        return (f"{atk_sym} captures {tgt_col} {tgt_sym} -- "
                f"collapsed to {capture_sq} [success]")
    else:
        board._rebuild_map()
        return (f"Capture failed -- {tgt_col} {tgt_sym} collapsed to "
                f"{collapsed_to}, not {capture_sq}")


# =========================================================================
# Standalone test — run with:  python quantum_rules.py
# =========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  quantum_rules.py — Quantum Rules Tests")
    print("=" * 60)

    # --- Test 1: superposition_move ---
    b = Board()
    e = QuantumBackend()  # Use unified QuantumBackend
    knight = b.piece_at("b1")

    log = superposition_move(b, e, knight, "b1", "c3")
    assert knight["superposed"] is True
    assert knight["positions"] == ["b1", "c3"]
    assert e.is_superposed(knight["qubit_id"])
    assert b.piece_at("b1") is knight
    assert b.piece_at("c3") is knight
    print(f"\n[PASS] Superposition move: {log}")

    # --- Test 2: cannot superpose an already-superposed piece ---
    log2 = superposition_move(b, e, knight, "b1", "a3")
    assert "already" in log2
    print(f"[PASS] Double superposition blocked: {log2}")

    # --- Test 3: collapse_piece ---
    collapse_results = set()
    for _ in range(40):
        b2 = Board()
        e2 = QuantumBackend()
        p2 = b2.piece_at("g1")   # white knight on g1
        superposition_move(b2, e2, p2, "g1", "f3")
        log3 = collapse_piece(b2, e2, p2)
        assert not p2["superposed"]
        assert len(p2["positions"]) == 1
        assert p2["positions"][0] in ("g1", "f3")
        collapse_results.add(p2["positions"][0])
    assert collapse_results == {"g1", "f3"}, "Should collapse to both squares across runs"
    print(f"[PASS] collapse_piece: observed both collapse outcomes")

    # --- Test 4: collapse on non-superposed piece is a no-op ---
    b4 = Board()
    e4 = QuantumBackend()
    pawn = b4.piece_at("e2")
    log4 = collapse_piece(b4, e4, pawn)
    assert "not in superposition" in log4
    print(f"[PASS] Collapse no-op on classical piece: {log4}")

    # --- Test 5: capture_superposed — success case ---
    captures = 0
    fails    = 0
    for _ in range(60):
        b5 = Board()
        e5 = QuantumBackend()
        # Put white knight into superposition between b1 and c3
        wknight = b5.piece_at("b1")
        superposition_move(b5, e5, wknight, "b1", "c3")
        # Black attacker on d5 tries to capture on c3
        attacker = b5._make_piece("bishop", "black", "d5")
        b5.add_piece(attacker)
        log5 = capture_superposed(b5, e5, attacker, wknight, "c3")
        if "[success]" in log5:
            captures += 1
            assert b5.piece_at("c3") is attacker
        else:
            fails += 1
            assert wknight in b5.pieces
    assert captures > 0 and fails > 0, "Should see both capture outcomes"
    print(f"[PASS] capture_superposed: {captures} successes, {fails} failures over 60 runs")

    # --- Test 6: entangle_move (real implementation) ---
    b6 = Board()
    e6 = QuantumBackend()
    pa = b6.piece_at("a1")  # white rook
    pb = b6.piece_at("h1")  # white rook
    log6 = entangle_move(b6, e6, pa, pb)
    assert "Entangled" in log6
    assert pa["entangled_with"] == [pb["qubit_id"]]
    assert pb["entangled_with"] == [pa["qubit_id"]]
    assert e6.is_entangled(pa["qubit_id"])
    print(f"[PASS] entangle_move: {log6}")

    # --- Test 7: entangled pieces collapse together ---
    b7 = Board()
    e7 = QuantumBackend()
    p7a = b7.piece_at("a2")
    p7b = b7.piece_at("b2")
    entangle_move(b7, e7, p7a, p7b)
    # Measure entangled pair - both should collapse to same outcome
    outcome_a, outcomes = e7.measure_entangled(p7a["qubit_id"])
    assert outcomes[p7a["qubit_id"]] == outcomes[p7b["qubit_id"]], "Entangled pieces should have same outcome"
    print(f"[PASS] Entangled measurement: both collapsed to {outcome_a}")

    print("\n" + "=" * 60)
    print("  All quantum_rules.py tests passed!")
    print("=" * 60)
