import pygame
import neat
import os
import random
from time import sleep
from game_config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from game_logics import LevelGenerator
from sprites import Frog, Line, Texture


generation = 0

# Helper to reorder lines for all game instances
def reorder_lines(lines):
    for i, line in enumerate(lines):
        line.goto_level(i)

def hitbox_collision(sprite_a, sprite_b):
    return sprite_a.hitbox.colliderect(sprite_b.rect)

class SingleSimulation:
    """Manages a single Frog's game state within the population."""
    def __init__(self, genome, config, seed):
        self.genome = genome
        self.net = neat.nn.FeedForwardNetwork.create(genome, config)
        self.frog = Frog()

        # 1. CREATE ISOLATED RNG WITH THE SHARED SEED
        self.rng = random.Random(seed)

        # Each frog starts with the same initial 5-line setup
        self.lines = [
            Line(Texture.GRASS, rng=self.rng),
            Line(Texture.ASPHALT, rng=self.rng),
            Line(Texture.ASPHALT, rng=self.rng),
            Line(Texture.GRASS, rng=self.rng),
            Line(Texture.WATER, rng=self.rng)
        ]
        reorder_lines(self.lines)
        for line in self.lines:
            line.rect.y = line.target_y
            
        self.all_sprites = pygame.sprite.Group(self.lines)
        # We need a local generator for each frog to keep their worlds independent
        self.gen = LevelGenerator(self.lines, rng=self.rng)
        
        self.alive = True
        self.frames_survived = 0
        self.distance_score = 0
        self.stagnation_timer = 0
        self.max_stagnation_frames = FPS * 3  # 3 seconds to make a step, then fitness will decrease
        self.max_stagnation_frames_to_death = FPS * 7  # if the frog doesn't move for 7 seconds it dies

    def get_inputs(self):
        inputs = []
        for line in self.lines:
            # 1. Type & Speed
            type_val = 0 # 0 if it's grass
            if line.texture_type == Texture.WATER:
                type_val = -1
            elif line.texture_type == Texture.ASPHALT:
                type_val = 1
            inputs.extend([type_val, line.speed / 5.0])
            
            # 2. Closest Obstacles (finding two closest relative to frog)
            obstacles = sorted(line.obstacles, key=lambda o: abs(o.rect.centerx - self.frog.rect.centerx))
            for i in range(2):
                if i < len(obstacles):
                    if obstacles[i].rect.centerx < self.frog.rect.centerx:
                        rel_x = (obstacles[i].rect.right - self.frog.rect.left) / SCREEN_WIDTH
                    else:
                        rel_x = (obstacles[i].rect.left - self.frog.rect.right) / SCREEN_WIDTH
                    rel_y = (obstacles[i].rect.centery - self.frog.rect.centery) / SCREEN_HEIGHT
                    inputs.extend([rel_x, rel_y])
                else:
                    inputs.extend([1.0, 1.0]) 
        return inputs

    def update(self):
        if not self.alive:
            return

        self.frames_survived += 1
        self.stagnation_timer += 1
        
        # 1. Decision Making
        inputs = self.get_inputs()
        output = self.net.activate(inputs)
        decision = output.index(max(output))
        
        if decision == 0 and self.frog.can_move():
            self.frog.face_north()
            self.frog.jump()
            self.gen.spawn_new_line(self.all_sprites)
            reorder_lines(self.lines)
            
            self.distance_score += 1
            self.genome.fitness += 20  # Increased reward for forward progress
            self.stagnation_timer = 0  # Reset timer because it moved forward
            
        elif decision == 1:
            self.frog.move_horizontal(-1)
        elif decision == 2:
            self.frog.move_horizontal(1)

        self.all_sprites.update()
        
        # 2. Death Condition: Side Edges
        # If the frog center goes off-screen, it's a death
        if self.frog.rect.centerx < 0 or self.frog.rect.centerx > SCREEN_WIDTH:
            self.genome.fitness -= 5 # Penalty for falling off the side
            self.alive = False

        # 3. Death Condition: Stagnation (Waiting too long)
        if self.stagnation_timer > self.max_stagnation_frames:
            # Gradually drain fitness for staying still
            self.genome.fitness -= 4 * 1/FPS 
            
            # If the frog is absolutely useless, kill it
            if self.stagnation_timer > self.max_stagnation_frames_to_death:
                self.alive = False
            if self.genome.fitness < -10:
                self.alive = False

        # 4. Standard Death Conditions (Water/Cars)
        current_lane = self.lines[0]
        hits = pygame.sprite.spritecollide(self.frog, current_lane.obstacles, False, collided=hitbox_collision)
        self.frog.hitbox.center = self.frog.rect.center

        if current_lane.texture_type == Texture.WATER:
            if hits:
                self.frog.stay_on_platform(current_lane.speed)
            elif abs(current_lane.rect.y - current_lane.target_y) < 5:
                self.genome.fitness -= 15 # Penalty for drowning
                self.alive = False 
        elif current_lane.texture_type == Texture.ASPHALT and hits:
            self.genome.fitness -= 15 # Penalty for getting hit
            self.alive = False

def eval_genomes(genomes, config):
    global generation
    generation += 1
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    
    if generation == 1:
        sleep(30) # This is for me for starting filming

    # Initialize simulations
    sims = []
    for genome_id, genome in genomes:
        genome.fitness = 0
        sims.append(SingleSimulation(genome, config, seed=generation))

    generation_running = True
    while generation_running and len(sims) > 0:
        # Handle Pygame events so window doesn't freeze
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()

        # Update all active simulations
        for sim in sims[:]:
            sim.update()
            if not sim.alive:
                sims.remove(sim)

        # RENDERING (Swarm View)
        screen.fill((30, 30, 30)) # Dark background
        
        if len(sims) > 0:
            # We draw the world of the BEST current frog as the background
            # Sorting by fitness to find the leader
            leader = max(sims, key=lambda s: s.genome.fitness)
            
            for line in leader.lines:
                screen.blit(line.image, line.rect)
                line.obstacles.draw(screen)
            
            # Draw frogs
            for sim in sims:                
                # Only draw if it's actually on screen
                if sim.distance_score == leader.distance_score:
                    sim.frog.draw(screen)
                    if sim is leader:
                        pygame.draw.circle(screen, (255, 215, 0), sim.frog.rect.center, 20, 2)


        pygame.display.set_caption(
            f"Generation: {generation}"
            f" | Frogs Alive: {len(sims)}"
            f" | Best Fitness: {int(leader.genome.fitness) if sims else 0}"
        )
        pygame.display.update()
        clock.tick(FPS)

def run_neat(config_file):
    config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction,
                         neat.DefaultSpeciesSet, neat.DefaultStagnation,
                         config_file)

    p = neat.Population(config)
    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)

    winner = p.run(eval_genomes, 150)
    print('\nBest genome:\n{!s}'.format(winner))

if __name__ == '__main__':
    run_neat('neat-config.txt')