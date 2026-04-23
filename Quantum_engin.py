# Qubit state management, H gate, measurement — runs on real IBM quantum hardware
"""
Quantum_engin.py

Quantum engine for Quantum Chess. Each measurement is executed as a real
circuit on IBM quantum hardware via QiskitRuntimeService and SamplerV2.

API key is loaded from  ../API - Feature Code/apikey.json  (outside the git
repo, so it is never committed).

Qubit states:
    classical  — piece is at one definite square (default)
    superposed — H gate applied; collapses on next measurement via IBM hardware
"""

import json
from pathlib import Path

from qiskit import QuantumCircuit
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager


def _load_api_key() -> str:
    key_path = Path(__file__).parent.parent / "API - Feature Code" / "apikey.json"
    with open(key_path, "r") as f:
        return json.load(f)["apikey"]


class QuantumEngine:
    """
    Quantum engine for Quantum Chess backed by real IBM quantum hardware.

    Each call to measure() on a superposed qubit builds a 1-qubit H+measure
    circuit, transpiles it for the selected backend, submits it via SamplerV2
    with shots=1, and returns the hardware result (0 or 1).

    Usage by quantum_rules.py:
        engine.apply_hadamard(piece["qubit_id"])
        result = engine.measure(piece["qubit_id"])
        # result — 0 or 1 (index into piece["positions"])
    """

    def __init__(self):
        api_key = _load_api_key()
        service = QiskitRuntimeService(channel="ibm_quantum", token=api_key)
        self.backend = service.least_busy(simulator=False, operational=True)
        self.pm = generate_preset_pass_manager(
            backend=self.backend, optimization_level=1
        )
        self._superposed: set[int] = set()
        # Entanglement manager wired in once Entanglement.py is complete
        self.entanglement = None

    # ------------------------------------------------------------------
    # Gate operations
    # ------------------------------------------------------------------

    def apply_hadamard(self, qubit_id: int):
        """Apply H gate: put qubit into equal superposition."""
        self._superposed.add(qubit_id)

    def apply_entanglement(self, qubit_a: int, qubit_b: int):
        """
        Register an entangled pair (Bell state).
        Circuit execution is delegated to EntanglementManager once available.
        """
        self._superposed.add(qubit_a)
        self._superposed.add(qubit_b)
        if self.entanglement is not None:
            self.entanglement.entangle(qubit_a, qubit_b)

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------

    def measure(self, qubit_id: int) -> int:
        """
        Measure a qubit and collapse it.

        Superposed qubits run a real 1-qubit H+measure circuit on IBM hardware.
        Classical qubits always return 0 without a hardware call.

        Returns 0 or 1 (index into piece["positions"]).
        """
        if qubit_id in self._superposed:
            return self._measure_superposed(qubit_id)
        return 0

    def _measure_superposed(self, qubit_id: int) -> int:
        """Run a 1-qubit H+measure circuit on IBM hardware and return the result."""
        qc = QuantumCircuit(1, 1)
        qc.h(0)
        qc.measure(0, 0)

        isa_circuit = self.pm.run(qc)

        with Sampler(mode=self.backend) as sampler:
            job = sampler.run([isa_circuit], shots=1)
            result = job.result()

        # SamplerV2 result: result[0].data contains the classical register
        counts = result[0].data.c.get_counts()
        outcome = int(list(counts.keys())[0])

        self._superposed.discard(qubit_id)
        return outcome

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_superposed(self, qubit_id: int) -> bool:
        """True if H gate has been applied and qubit has not been measured."""
        return qubit_id in self._superposed
