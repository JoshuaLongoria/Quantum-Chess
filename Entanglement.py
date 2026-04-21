"""
Entanglement.py — Unified Quantum Backend for Quantum Chess

Provides:
  - Superposition (H gate): split a piece across two squares
  - Entanglement (Bell state): link two pieces quantum-mechanically
  - Measurement: collapse superposition/entanglement to classical state

This replaces the stub in quantum_rules.py and integrates with the
existing board/quantum_rules architecture.
"""

from __future__ import annotations
import random
from typing import Optional

# Try to import Qiskit for real quantum execution; fall back to simulation
try:
    from qiskit import QuantumCircuit, transpile
    from qiskit_aer import AerSimulator
    HAS_QISKIT = True
except ImportError:
    HAS_QISKIT = False

# IBM Quantum Cloud support
try:
    from qiskit_ibm_runtime import QiskitRuntimeService
    HAS_IBM_QUANTUM = True
except ImportError:
    HAS_IBM_QUANTUM = False

# Load config (if available) — config.py should be in .gitignore
import os
import sys

# Add script's directory to path for config import
_config_dir = os.path.dirname(os.path.abspath(__file__))
if _config_dir not in sys.path:
    sys.path.insert(0, _config_dir)

try:
    from config import IBM_QUANTUM_TOKEN, IBM_BACKEND
except ImportError:
    IBM_QUANTUM_TOKEN = ""
    IBM_BACKEND = "ibm_brisbane"


class QuantumBackend:
    """
    Unified quantum engine for Quantum Chess.

    Supports three modes:
      - SIMULATED (default): Uses Python random to mirror quantum behavior
      - AER: Qiskit Aer simulator (local quantum simulation)
      - IBM: Real IBM Quantum cloud hardware (requires API token)

    The game interface is identical regardless of backend.
    """

    # Mode constants
    SIMULATED = "simulated"
    AER = "aer"
    IBM = "ibm"

    def __init__(self, mode: str = SIMULATED, ibm_token: str = None, ibm_backend: str = None):
        """
        Initialize quantum backend.

        Args:
            mode: "simulated", "aer", or "ibm"
            ibm_token: IBM Quantum API token (or set IBM_API_TOKEN env var)
            ibm_backend: IBM backend name (default: ibm_brisbane)
        """
        self._superposed: set[int] = set()      # qubits with H gate applied
        self._entangled: dict[int, set[int]] = {}  # qubit -> entangled partners
        self._next_qubit: int = 0
        self._mode = mode

        # Validate and set up backend
        if mode == QuantumBackend.IBM:
            if not HAS_IBM_QUANTUM:
                print("[QuantumBackend] IBM Quantum not available, falling back to simulated")
                self._mode = QuantumBackend.SIMULATED
            else:
                self._setup_ibm_backend(ibm_token, ibm_backend or IBM_BACKEND_NAME)
        elif mode == QuantumBackend.AER:
            if not HAS_QISKIT:
                print("[QuantumBackend] Qiskit not available, falling back to simulated")
                self._mode = QuantumBackend.SIMULATED
            else:
                self._simulator = AerSimulator()
                print("[QuantumBackend] Using Qiskit Aer simulator")
        else:
            print("[QuantumBackend] Using simulated quantum")

    def _setup_ibm_backend(self, token: str, backend_name: str):
        """Connect to IBM Quantum cloud."""
        # Priority: 1) explicit token param, 2) config.py, 3) environment variable
        if not token:
            token = IBM_QUANTUM_TOKEN
        if not token:
            import os
            token = os.environ.get("IBM_QUANTUM_TOKEN", "")

        if not token:
            print("[QuantumBackend] No IBM API token (set in config.py or IBM_QUANTUM_TOKEN env var)")
            self._mode = QuantumBackend.SIMULATED
            return

        try:
            self._service = QiskitRuntimeService(channel="ibm_quantum", token=token)
            self._backend = self._service.backend(backend_name)
            print(f"[QuantumBackend] Connected to IBM Quantum: {backend_name}")
        except Exception as e:
            print(f"[QuantumBackend] Failed to connect to IBM: {e}, falling back to simulated")
            self._mode = QuantumBackend.SIMULATED

    @property
    def mode(self) -> str:
        """Current backend mode."""
        return self._mode

    def is_ibm_connected(self) -> bool:
        """True if connected to real IBM Quantum hardware."""
        return self._mode == QuantumBackend.IBM and hasattr(self, '_backend')

    # -------------------------------------------------------------------------
    # Qubit allocation
    # -------------------------------------------------------------------------

    def allocate_qubit(self) -> int:
        """Allocate a new qubit ID for a piece."""
        qubit_id = self._next_qubit
        self._next_qubit += 1
        return qubit_id

    # -------------------------------------------------------------------------
    # Superposition (H gate)
    # -------------------------------------------------------------------------

    def apply_hadamard(self, qubit_id: int) -> None:
        """
        Apply H gate: put qubit into equal superposition (50/50).
        Used for superposition_move in quantum_rules.py.
        """
        self._superposed.add(qubit_id)

    def is_superposed(self, qubit_id: int) -> bool:
        """True if H gate applied and not yet measured."""
        return qubit_id in self._superposed

    def measure_superposition(self, qubit_id: int) -> int:
        """
        Measure a superposed qubit, collapsing to 0 or 1.

        Returns:
            0 or 1 — index into piece's positions list
            (0 = first position, 1 = second position)
        """
        if qubit_id not in self._superposed:
            return 0  # classical — stays at positions[0]

        if self._mode == QuantumBackend.IBM:
            result = self._run_ibm_circuit(self._create_hadamard_circuit())
        elif self._mode == QuantumBackend.AER:
            result = self._run_aer_circuit(self._create_hadamard_circuit())
        else:
            result = random.randint(0, 1)

        self._superposed.discard(qubit_id)
        return result

    def _create_hadamard_circuit(self) -> QuantumCircuit:
        """Create 1-qubit H-gate circuit."""
        qc = QuantumCircuit(1, 1)
        qc.h(0)
        qc.measure(0, 0)
        return qc

    def _run_aer_circuit(self, qc: QuantumCircuit) -> int:
        """Execute circuit on Aer simulator."""
        job = self._simulator.run(qc, shots=1)
        result = job.result().get_counts()
        return int(list(result.keys())[0])

    def _run_ibm_circuit(self, qc: QuantumCircuit) -> int:
        """Execute circuit on IBM Quantum hardware."""
        job = self._backend.run(qc, shots=1)
        result = job.result().get_counts()
        return int(list(result.keys())[0])

    # -------------------------------------------------------------------------
    # Entanglement (Bell state)
    # -------------------------------------------------------------------------

    def entangle(self, qubit_a: int, qubit_b: int) -> None:
        """
        Create Bell state entanglement between two pieces.

        After entangling:
          - Measuring either piece collapses both
          - Both pieces will have the SAME outcome (correlated)
        """
        if qubit_a not in self._entangled:
            self._entangled[qubit_a] = set()
        if qubit_b not in self._entangled:
            self._entangled[qubit_b] = set()

        self._entangled[qubit_a].add(qubit_b)
        self._entangled[qubit_b].add(qubit_a)

    def is_entangled(self, qubit_id: int) -> bool:
        """True if qubit is part of an entangled pair."""
        return qubit_id in self._entangled and len(self._entangled[qubit_id]) > 0

    def get_entangled_partners(self, qubit_id: int) -> set[int]:
        """Return set of qubit IDs entangled with this one."""
        return self._entangled.get(qubit_id, set())

    def measure_entangled(self, qubit_id: int) -> tuple[int, dict[int, int]]:
        """
        Measure an entangled qubit and collapse all entangled partners.

        Returns:
            tuple: (measured_value, {qubit_id: outcome, ...})
            All entangled qubits get the SAME outcome (Bell state correlation).
        """
        if self._mode == QuantumBackend.IBM:
            measured, outcomes = self._run_ibm_bell_circuit()
        elif self._mode == QuantumBackend.AER:
            measured, outcomes = self._run_aer_bell_circuit()
        else:
            measured = random.randint(0, 1)
            outcomes = {qubit_id: measured}

        # All entangled partners collapse to the same value
        partners = self.get_entangled_partners(qubit_id)
        for partner_id in partners:
            outcomes[partner_id] = measured

        # Clear entanglement state after measurement
        self._clear_entanglement(qubit_id)

        return measured, outcomes

    def _create_bell_circuit(self) -> QuantumCircuit:
        """Create 2-qubit Bell state circuit."""
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        return qc

    def _run_aer_bell_circuit(self) -> tuple[int, dict[int, int]]:
        """Execute Bell state circuit on Aer simulator."""
        qc = self._create_bell_circuit()
        job = self._simulator.run(qc, shots=1)
        result = job.result().get_counts()
        outcome_str = list(result.keys())[0]  # e.g., "00" or "11"
        measured = int(outcome_str[0])
        return measured, {0: measured}

    def _run_ibm_bell_circuit(self) -> tuple[int, dict[int, int]]:
        """Execute Bell state circuit on IBM Quantum hardware."""
        qc = self._create_bell_circuit()
        job = self._backend.run(qc, shots=1)
        result = job.result().get_counts()
        outcome_str = list(result.keys())[0]
        measured = int(outcome_str[0])
        return measured, {0: measured}

    def _clear_entanglement(self, qubit_id: int) -> None:
        """Remove all entanglement links for a qubit after measurement."""
        partners = self._entangled.get(qubit_id, set())
        for partner_id in partners:
            self._entangled[partner_id].discard(qubit_id)
        self._entangled.pop(qubit_id, None)

    # -------------------------------------------------------------------------
    # State queries (for game logic)
    # -------------------------------------------------------------------------

    def get_state(self, qubit_id: int) -> str:
        """Return human-readable state: 'classical', 'superposed', or 'entangled'."""
        if self.is_entangled(qubit_id):
            return "entangled"
        elif self.is_superposed(qubit_id):
            return "superposed"
        return "classical"


# Backwards compatibility: keep EntanglementManager as alias
EntanglementManager = QuantumBackend
