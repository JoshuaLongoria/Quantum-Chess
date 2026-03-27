# ♛ Quantum Chess

> A quantum computing twist on classical chess — where pieces exist in **superposition**, captures trigger **real quantum measurements** on IBM hardware, and entangled pieces always collapse together.

**CS5331/4331 — Introduction to Quantum Computing | Texas Tech University**

---

## 📋 Table of Contents

- [Overview](#overview)
- [Quantum Mechanics Used](#quantum-mechanics-used)
- [Novelty Statement](#novelty-statement)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Team](#team)
- [Installation](#installation)
- [IBM Quantum Setup](#ibm-quantum-setup)
- [How to Play](#how-to-play)
- [Quantum Circuits](#quantum-circuits)
- [Development Timeline](#development-timeline)
- [References](#references)

---

## Overview

Quantum Chess extends classical chess with three quantum mechanics:

- **Superposition** — a piece can occupy two squares at once until observed
- **Collapse / Measurement** — attempting to capture a superposed piece triggers a real quantum measurement on IBM hardware; the piece collapses to one square (or disappears if it wasn't there)
- **Entanglement** — two pieces can be linked via a Bell state so that their collapses are always correlated

The result is a game where uncertainty is a first-class mechanic, not a gimmick and where the randomness comes from actual quantum hardware, not a pseudo-random number generator.

---

## Quantum Mechanics Used

| Mechanic | Gate | Game Event |
|---|---|---|
| Superposition | Hadamard (`H`) | Superposition move — piece splits across two squares |
| Entanglement | CNOT (`CX`) | Entangle move — two pieces linked into a Bell state |
| Measurement / Collapse | `Measure` | Capture attempt — collapses piece to one square |

---

## Novelty Statement

> Unlike Google's Quantum Chess (SplitInfinity), which uses a classical chess engine with quantum-inspired rules, **our version performs real quantum gate operations** (H, CNOT, Measure) on IBM Quantum hardware for the two most critical game events: piece collapse and entanglement resolution.
>
> The collapse mechanic is a **genuine quantum measurement** — not a simulation. This makes Quantum Chess a pedagogical quantum computing demo embedded in a game, not just a game with quantum-flavored rules.

---

## Tech Stack

| Component | Tool | Purpose |
|---|---|---|
| Quantum backend | `Qiskit` + IBM Quantum Runtime | Real H, CNOT, Measure gates on hardware |
| Quantum simulator | `Qiskit Aer` | Fast local fallback for dev and demo |
| Game logic | Python (custom) | Chess rules + quantum rule extensions |
| UI / Rendering | Pygame | Board, ghost pieces, collapse animations |
| Circuit diagrams | IBM Quantum Composer | Presentation slide visuals |

---

## Project Structure

```
quantum_chess/
├── quantum_engine.py       # Qubit state management, H gate, CNOT, measurement
├── entanglement.py         # Bell state creation, correlated collapse logic
├── board.py                # Classical board state, piece positions, move rules
├── quantum_rules.py        # Superposition move, entangle move, measure move
├── game_manager.py         # Turn flow, win condition, event orchestration
├── renderer.py             # Board drawing, ghost pieces, collapse animations
├── ui_components.py        # State panel, move history, quantum event log
└── main.py                 # Entry point, game loop
```

---

## Team

| Member | Role | Owns |
|---|---|---|
| Person A | Quantum Backend | `quantum_engine.py`, `entanglement.py` |
| Person B | Game Logic | `board.py`, `quantum_rules.py`, `game_manager.py` |
| Person C | UI & Visualization | `renderer.py`, `ui_components.py`, `main.py` |

### Shared Data Contract

> **Week 1 priority:** All three members must agree on the piece representation below *before* writing any module code. This is the contract that lets all three workstreams run in parallel.

```python
# Shared piece representation
piece = {
    "type":           "knight",
    "color":          "white",
    "positions":      ["e4"],           # classical: one square
    # OR
    "positions":      ["e4", "g5"],     # superposition: two squares
    "superposed":     True,
    "qubit_id":       3,                # index into the quantum register
    "entangled_with": [7],              # qubit IDs of entangled pieces (if any)
}
```

---

## Installation

### Prerequisites

- Python 3.9+
- Node.js (optional, for any JS tooling)
- A free [IBM Quantum account](https://quantum.ibm.com)

### Install dependencies

```bash
pip install qiskit qiskit-ibm-runtime qiskit-aer pygame
```

### Run the game

```bash
python main.py
```

### Run individual module tests

```bash
python quantum_engine.py    # Tests superposition + measurement
python entanglement.py      # Tests Bell state creation
python board.py             # Tests classical chess rules
```

---

## IBM Quantum Setup

### 1. Save your API token (one time only)

```python
from qiskit_ibm_runtime import QiskitRuntimeService

QiskitRuntimeService.save_account(
    channel="ibm_quantum",
    token="YOUR_IBM_QUANTUM_TOKEN"   # from quantum.ibm.com → account settings
)
```

### 2. Hardware vs. simulator strategy

Running every move on real hardware is impractical due to queue times. We use a hardware toggle:

| Game Event | Backend | Reason |
|---|---|---|
| Regular moves | Classical (instant) | No quantum needed |
| Superposition move | Qiskit Aer | Fast, no queue wait |
| Capture of superposed piece | IBM Real Hardware | Showcase moment — genuine randomness |
| Entanglement collapse | IBM Real Hardware | Demonstrates Bell state |
| Live demo / presentation fallback | Qiskit Aer | Reliable under time pressure |

### 3. Toggle pattern in code

```python
USE_REAL_HARDWARE = False  # Set True for showcase moments

def measure_qubit(circuit):
    if USE_REAL_HARDWARE:
        service = QiskitRuntimeService(channel="ibm_quantum")
        backend = service.least_busy(operational=True, simulator=False)
    else:
        from qiskit_aer import AerSimulator
        backend = AerSimulator()

    from qiskit_ibm_runtime import Sampler
    sampler = Sampler(backend)
    job = sampler.run([circuit], shots=1)
    return job.result()
```

---

## How to Play

### Standard moves
All classical chess moves are valid. The game follows standard FIDE rules for non-quantum moves.

### Quantum moves (new)

| Move | How to trigger | What happens |
|---|---|---|
| **Superposition move** | Select a piece, then select two destination squares | Piece enters superposition — shown as ghost pieces on both squares |
| **Entangle move** | Select two of your own pieces | Pieces become entangled — shown with a glowing link |
| **Measure move** | Select any superposed piece | Forces immediate collapse to one square |

### Capture rules
- Capturing a **classical piece** works as normal.
- Capturing a **superposed piece** triggers a quantum measurement:
  - If the piece collapses to the captured square → capture succeeds
  - If the piece collapses to the other square → capture fails, piece survives

### Entanglement collapse
- When one entangled piece collapses, the other collapses simultaneously.
- Their outcomes are correlated — if A collapses to its primary square, B collapses to its primary square too (Bell state `|00⟩` or `|11⟩`, never `|01⟩` or `|10⟩`).

---

## Quantum Circuits

### Superposition (Hadamard gate)

```python
from qiskit import QuantumCircuit

qc = QuantumCircuit(1, 1)
qc.h(0)           # |0⟩ → |+⟩ = (|0⟩ + |1⟩) / √2
qc.measure(0, 0)  # Collapses to |0⟩ or |1⟩ with equal probability
```

```
q_0: ─┤ H ├─┤M├
      └───┘ └╥┘
c: 1/════════╩═
             0
```

### Entanglement — Bell State (CNOT gate)

```python
qc = QuantumCircuit(2, 2)
qc.h(0)              # Piece A in superposition
qc.cx(0, 1)          # Entangle piece B with piece A → Bell state |Φ+⟩
qc.measure([0,1], [0,1])
# Result is always |00⟩ or |11⟩ — never |01⟩ or |10⟩
```

```
q_0: ─┤ H ├─■──┤M├───
      └───┘ │  └╥┘┌─┐
q_1: ───────┤X─┬╫─┤M├
            └──┘║ └╥┘
c: 2/═══════════╩══╩═
                0  1
```

> **Demo talking point:** Show your audience that entangled pieces *always* collapse together (00 or 11, never 01 or 10). This is the Bell state in action on real IBM quantum hardware — not a coin flip.

---

## Development Timeline

| Week | Goal |
|---|---|
| **1** | All three members agree on the shared data contract. No module code yet. |
| **2** | A: superposition + measurement working. B: classical board + legal moves. C: static board renders. |
| **3** | Integration sprint — A+B connect quantum events to game logic. C pulls live state from B. |
| **4** | All quantum rules working. Ghost pieces + collapse animations in UI. IBM Quantum integration tested. |
| **5** | Bug fixing, edge cases, demo polish. Presentation prepared and rehearsed. |

---

## References

- [IBM Quantum Composer](https://quantum.ibm.com/composer/files/new)
- [Qiskit Documentation](https://docs.quantum.ibm.com)
- [PennyLane](https://pennylane.ai) — alternative quantum backend
- [Quantum Odyssey / Quantum Chess (SplitInfinity)](https://store.steampowered.com/app/2802710/Quantum_Odyssey/) — original inspiration
- Nielsen & Chuang — *Quantum Computation and Quantum Information*, Ch. 1–2
- Course material: CS5331/4331, Texas Tech University

---

<div align="center">
  <sub>CS5331/4331 · Introduction to Quantum Computing · Texas Tech University</sub>
</div>
