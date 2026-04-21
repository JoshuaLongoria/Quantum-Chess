# Entry point, game loop
import pygame
import sys
from constants import WINDOW_WIDTH, WINDOW_HEIGHT
from renderer import render_frame
from game_manager import GameManager

pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Quantum Chess")
clock = pygame.time.Clock()
gm = GameManager()
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
