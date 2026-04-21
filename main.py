# Entry point, game loop
import pygame
import sys
import argparse
from constants import WINDOW_WIDTH, WINDOW_HEIGHT
from renderer import render_frame
from game_manager import GameManager
from Entanglement import QuantumBackend

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Quantum Chess")
parser.add_argument(
    "--mode", 
    choices=["simulated", "aer", "ibm"],
    default="simulated",
    help="Quantum backend: simulated (default), aer (Qiskit Aer), ibm (IBM Quantum)"
)
parser.add_argument(
    "--backend",
    type=str,
    default=None,
    help="IBM Quantum backend name (default: ibm_brisbane, set in config.py)"
)
args = parser.parse_args()

pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Quantum Chess")
clock = pygame.time.Clock()

# Create game manager with specified quantum backend
gm = GameManager(quantum_mode=args.mode, ibm_backend=args.backend)

if args.mode == "ibm" and not gm.engine.is_ibm_connected():
    print("Warning: IBM Quantum connection failed, using simulated mode")
tick = 0

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            x, y = pygame.mouse.get_pos()
            gm.handle_click(x, y)

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                gm.set_quantum_mode("superposition")
            elif event.key == pygame.K_m:
                gm.set_quantum_mode("measure")
            elif event.key == pygame.K_e:
                gm.set_quantum_mode("entangle")
            elif event.key == pygame.K_ESCAPE:
                gm._cancel_quantum_mode()

    game_state = gm.get_game_state()
    render_frame(screen, game_state, tick)

    pygame.display.flip()
    clock.tick(60)
    tick += 1
