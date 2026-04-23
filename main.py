# Entry point, game loop
import pygame
import sys
import argparse
from constants import WINDOW_WIDTH, WINDOW_HEIGHT
from renderer import render_frame
from game_manager import GameManager, pixel_to_square
from lobby import LobbyScreen
from network import NetworkManager
from ui_components import draw_hud, get_forfeit_button_rect

# ── CLI args ─────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Quantum Chess")
parser.add_argument(
    "--mode",
    choices=["simulated", "aer", "ibm"],
    default="simulated",
    help="Quantum backend: simulated (default), aer (Qiskit Aer), ibm (IBM Quantum)",
)
parser.add_argument(
    "--backend",
    type=str,
    default=None,
    help="IBM Quantum backend name (default: ibm_brisbane, set in config.py)",
)
args = parser.parse_args()

# ── Pygame init ───────────────────────────────────────────────────────────────
pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Quantum Chess")
clock = pygame.time.Clock()
tick  = 0

# ── Phase 1: Lobby ────────────────────────────────────────────────────────────
lobby  = LobbyScreen()
net: NetworkManager | None = None
my_color: str | None = None   # None = local; "white"/"black" in LAN mode

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        lobby.handle_event(event)

    result = lobby.update()
    if result:
        if result["mode"] == "lan":
            net      = result["network"]
            my_color = "white" if net.role == "server" else "black"
        # mode == "local" → net stays None, my_color stays None
        break

    lobby.render(screen, tick)
    pygame.display.flip()
    clock.tick(60)
    tick += 1

# ── Phase 2: Game setup ───────────────────────────────────────────────────────
gm = GameManager(quantum_mode=args.mode, ibm_backend=args.backend)

if args.mode == "ibm" and not gm.engine.is_ibm_connected():
    print("Warning: IBM Quantum connection failed, using simulated mode")

if net:
    role_label = "White" if my_color == "white" else "Black"
    gm.log(f"LAN — you are {role_label}  |  peer: {net.peer_ip}")

# ── Phase 3: Game loop ────────────────────────────────────────────────────────
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            if net:
                net.stop()
            pygame.quit()
            sys.exit()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if my_color is None or gm.current_turn == my_color:
                x, y = pygame.mouse.get_pos()

                forfeit_rect = get_forfeit_button_rect()

                if forfeit_rect.collidepoint(x, y):
                    gm.forfeit()
                    if net:
                        net.send({"type": "forfeit"})
                    continue

                sq = pixel_to_square(x, y)
                was_measure = (gm.quantum_mode == "measure")
                gm.handle_click(x, y)

                if net and sq:
                    measure_fired = was_measure and gm.quantum_mode is None
                    if measure_fired:
                        net.send({
                            "type": "measure_click",
                            "square": sq,
                            "result": gm.engine.last_result,
                        })
                    else:
                        net.send({"type": "click", "square": sq})

        elif event.type == pygame.KEYDOWN:
            # Gate quantum key presses on our turn in LAN mode
            if my_color is None or gm.current_turn == my_color:
                if event.key == pygame.K_q:
                    gm.set_quantum_mode("superposition")
                    if net:
                        net.send({"type": "key", "mode": "superposition"})
                elif event.key == pygame.K_m:
                    gm.set_quantum_mode("measure")
                    if net:
                        net.send({"type": "key", "mode": "measure"})
                elif event.key == pygame.K_e:
                    gm.set_quantum_mode("entangle")
                    if net:
                        net.send({"type": "key", "mode": "entangle"})
                elif event.key == pygame.K_ESCAPE:
                    gm._cancel_quantum_mode()
                    if net:
                        net.send({"type": "cancel"})

    # ── Apply incoming network messages ───────────────────────────────────────
    if net:
        for msg in net.poll():
            t = msg.get("type")
            if t == "click":
                gm.handle_square(msg.get("square"))
            elif t == "measure_click":
                # Seed the engine so both sides collapse to the same square
                gm.engine.seed_next_result(msg.get("result", 0))
                gm.handle_square(msg.get("square"))
            elif t == "key":
                gm.set_quantum_mode(msg.get("mode", ""))
            elif t == "cancel":
                gm._cancel_quantum_mode()
            elif t == "forfeit":
                gm.forfeit()

        # Show a warning if the peer disconnects mid-game
        if not net.connected and not gm.game_over:
            gm.log("⚠  LAN peer disconnected.")
            gm.game_over  = True
            gm.game_result = "Opponent disconnected."

    # ── Render ────────────────────────────────────────────────────────────────
    game_state = gm.get_game_state()
    render_frame(screen, game_state, tick)

    pygame.display.flip()
    clock.tick(60)
    tick += 1
