# Qubit state management, H gate, measurement
"""
Quantum_engin.py

Game-compatible quantum engine. Uses Python random to produce the same
probabilistic outcomes as the Qiskit H+measure circuit in
quantum_chess_engine.ipynb.

Scope: qubit state tracking, Hadamard gate, and measurement (superposition
collapse). 

Qubit states:
    classical  — piece is at one definite square (default)
    superposed — H gate applied: 50/50 collapse on measurement
"""
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit import QuantumCircuit
from entanglement import EntanglementManager 


class QuantumEngine:
    """
    Probabilistic quantum engine for Quantum Chess.

    Tracks which qubits are in superposition and returns randomised
    measurement outcomes that mirror the Qiskit H+measure circuit
    demonstrated in quantum_chess_engine.ipynb.

    Usage by quantum_rules.py:
        engine.apply_hadamard(piece["qubit_id"])
        result = engine.measure(piece["qubit_id"])
        # result — 0 or 1 (index into piece["positions"])
    """

    def __init__(self):
        self._superposed: set[int] = set()   # qubit IDs with H gate applied

    # ------------------------------------------------------------------
    # Gate operations
    # ------------------------------------------------------------------

    def apply_hadamard(self, qubit_id: int):
        """Apply H gate: put qubit into equal superposition."""
        self._superposed.add(qubit_id)
        
    def apply_entanglement(self, qubit_a: int, qubit_b: int):
        """Called by game_rules when a split move happens."""
        self._superposed.add(qubit_a)
        self._superposed.add(qubit_b)
        
        # Register the link in the manager
        self.entanglement.entangle(qubit_a, qubit_b)

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------

    def measure(self, qubit_id: int) -> int:
        """
        Measure a qubit and collapse it.

        Returns:
            0 or 1 (index into piece["positions"])
            Classical qubit always returns 0.
            Superposed qubit returns 0 or 1 with equal probability.
        """
        if qubit_id in self._superposed:
            return self._measure_superposed(qubit_id)
        return 0   # classical — piece stays at positions[0]

    def _measure_superposed(self, qubit_id: int) -> int:
        """50/50 collapse. Mirrors 1-qubit H+measure circuit."""
        result = random.randint(0, 1)
        self._superposed.discard(qubit_id)
        return result

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_superposed(self, qubit_id: int) -> bool:
        """True if H gate has been applied and qubit has not been measured."""
        return qubit_id in self._superposed


# =========================================================================
# Standalone test — run with:  python Quantum_engin.py
# =========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Quantum_engin.py — QuantumEngine Tests")
    print("=" * 60)

    # --- Test 1: classical qubit always returns 0 ---
    e = QuantumEngine()
    result = e.measure(0)
    assert result == 0
    print("\n[PASS] Classical qubit: measure() returns 0")

    # --- Test 2: superposition gives both 0 and 1 over many runs ---
    results = set()
    for _ in range(200):
        e2 = QuantumEngine()
        e2.apply_hadamard(0)
        assert e2.is_superposed(0)
        r = e2.measure(0)
        assert r in (0, 1)
        assert not e2.is_superposed(0)   # collapsed
        results.add(r)
    assert results == {0, 1}, "Should see both outcomes over 200 runs"
    print("[PASS] Superposed qubit: both 0 and 1 observed")

    # --- Test 3: state clears after measurement ---
    e3 = QuantumEngine()
    e3.apply_hadamard(3)
    e3.measure(3)
    assert not e3.is_superposed(3)
    print("[PASS] Superposition clears after measurement")

    print("\n" + "=" * 60)
    print("  All Quantum_engin.py tests passed!")
    print("=" * 60)
