import pygame
from game_config import FPS, SCREEN_WIDTH, SCREEN_HEIGHT
from game_logics import LevelGenerator
from sprites import Frog, Line, Texture, Obstacle

def reorder_lines(lines: list[Line]):
    for i, line in enumerate(lines):
        line.goto_level(i)

def hitbox_collision(sprite_a: pygame.sprite.Sprite | Frog, 
                     sprite_b: pygame.sprite.Sprite | Obstacle):
    return sprite_a.hitbox.colliderect(sprite_b.rect)

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    running = True

    # 1. Setup Frog
    frog = Frog()
    
    # 2. Setup Initial Lines
    fivelines: list[Line] = [
        Line(Texture.GRASS),
        Line(Texture.ASPHALT),
        Line(Texture.ASPHALT),
        Line(Texture.GRASS),
        Line(Texture.WATER)
    ]
    
    # Position them and snap to target immediately for the start
    reorder_lines(fivelines)
    for line in fivelines:
        line.rect.y = line.target_y

    all_sprites = pygame.sprite.Group()
    all_sprites.add(fivelines)
    # Note: We don't add the frog to all_sprites if we want to draw it separately 
    # (to ensure it stays on top of everything), or add it last.
    # all_sprites.add(frog)

    gen = LevelGenerator(fivelines)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    if frog.can_move():
                        frog.jump() 
                        frog.face_north()
                        gen.spawn_new_line(all_sprites)
                        reorder_lines(gen.lines)
                elif event.key == pygame.K_LEFT:
                    frog.move_horizontal(-1)
                elif event.key == pygame.K_RIGHT:
                    frog.move_horizontal(1)

        # LOGIC UPDATE
        all_sprites.update()

        # --- LOGIC: Handle Platform Riding & Collisions ---
        # Level 0 is the lane the frog is currently in
        current_lane = gen.lines[0] 
        
        if abs(current_lane.rect.y - current_lane.target_y) < 5: 
        # this ensures that collisions are checked after sliding
            hits = pygame.sprite.spritecollide(frog, current_lane.obstacles, 
                                               False, collided=hitbox_collision)
            frog.hitbox.center = frog.rect.center
            # Check collision with obstacles in the current lane
            if current_lane.texture_type == Texture.WATER:
                if hits:
                    # The frog is on a log! Move it with the log's speed
                    # (Assuming all logs in a lane move at the same speed)
                    frog.stay_on_platform(current_lane.speed)
                else:
                    # Optional: Add a 'dead' flag here for NEAT to reset
                    print("DROWNED!")
            elif current_lane.texture_type == Texture.ASPHALT:
                if hits:
                    print("SMASHED!")

        # RENDERING
        screen.fill("black")

        # To draw obstacles correctly, we draw in layers
        for line in gen.lines:
            # Draw the lane background
            screen.blit(line.image, line.rect)
            # Draw the obstacles belonging to this specific lane
            line.obstacles.draw(screen)

        # Draw the frog last so it is on top of logs/cars
        frog.draw(screen)
        frog.update()

        pygame.display.update()
        clock.tick(FPS)

    pygame.quit()

if __name__=='__main__':
    main()
