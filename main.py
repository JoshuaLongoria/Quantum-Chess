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
            x, y =pygame.mouse.get_pos()
            gm.handle_click(x, y)
            # YOUR JOB: get mouse position and call gm.handle_click()
            pass

    # YOUR JOB: get game state and call render_frame()
    game_state = gm.get_game_state()
    render_frame(screen, game_state, tick)
    
    pygame.display.flip()
    clock.tick(60)
    tick += 1