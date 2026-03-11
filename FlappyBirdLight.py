import pygame
import random

# Initialize Pygame
pygame.init()

# Screen dimensions
SCREEN_WIDTH = 400
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Flappy Bird")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)

# Bird properties
BIRD_WIDTH = 40
BIRD_HEIGHT = 30
bird_x = 50
bird_y = SCREEN_HEIGHT // 2
bird_velocity = 0
gravity = 0.5  # Gravity
flap_strength = -7  # Moderate flap strength

# Pipe properties
PIPE_WIDTH = 70
PIPE_HEIGHT = 500
PIPE_GAP = 200  # Pipe gap
pipe_velocity = -2  # Pipe velocity
pipes = []

# Game variables
score = 0
clock = pygame.time.Clock()
flap_cooldown = 0  # Time before the bird can flap again

def draw_bird():
   pygame.draw.rect(screen, BLACK, (bird_x, bird_y, BIRD_WIDTH, BIRD_HEIGHT))

def draw_pipes():
   for pipe in pipes:
      pygame.draw.rect(screen, GREEN, pipe['top'])
      pygame.draw.rect(screen, GREEN, pipe['bottom'])

def check_collision():
   global score
   bird_rect = pygame.Rect(bird_x, bird_y, BIRD_WIDTH, BIRD_HEIGHT)
   for pipe in pipes:
      if bird_rect.colliderect(pipe['top']) or bird_rect.colliderect(pipe['bottom']):
         return True
   if bird_y > SCREEN_HEIGHT or bird_y < 0:
      return True
   return False

def update_pipes():
   global score
   for pipe in pipes:
      pipe['top'].x += pipe_velocity
      pipe['bottom'].x += pipe_velocity
      if pipe['top'].x + PIPE_WIDTH < 0:
         pipes.remove(pipe)
         score += 1
   if len(pipes) == 0 or pipes[-1]['top'].x < SCREEN_WIDTH - 300:
      pipe_height = random.randint(100, SCREEN_HEIGHT - PIPE_GAP - 100)
      pipes.append({
         'top': pygame.Rect(SCREEN_WIDTH, 0, PIPE_WIDTH, pipe_height),
         'bottom': pygame.Rect(SCREEN_WIDTH, pipe_height + PIPE_GAP, PIPE_WIDTH, SCREEN_HEIGHT - pipe_height - PIPE_GAP)
      })

# Game loop
running = True
while running:
   for event in pygame.event.get():
      if event.type == pygame.QUIT:
         running = False
      if event.type == pygame.KEYDOWN:
         if event.key == pygame.K_SPACE and flap_cooldown <= 0:
            bird_velocity = flap_strength
            flap_cooldown = 10  # Set cooldown to prevent rapid flapping
      if event.type == pygame.MOUSEBUTTONDOWN and flap_cooldown <= 0:
         bird_velocity = flap_strength
         flap_cooldown = 10  # Set cooldown to prevent rapid flapping
    
   # Update bird position
   bird_velocity += gravity
   bird_y += bird_velocity

   # Update pipes
   update_pipes()

   # Check for collision
   if check_collision():
      running = False

   # Manage flap cooldown
   if flap_cooldown > 0:
      flap_cooldown -= 1

   # Draw everything
   screen.fill(WHITE)
   draw_bird()
   draw_pipes()

   # Display the score
   font = pygame.font.SysFont(None, 36)
   score_text = font.render(f'Score: {score}', True, BLACK)
   screen.blit(score_text, (10, 10))

   pygame.display.flip()
   clock.tick(30)

pygame.quit()