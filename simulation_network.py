import pygame
import neat
import matplotlib.pyplot as plt
# import networkx as nx  # Optional, but makes layout 10x easier. Standard in data science.

import asyncio
import os
import math
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

def print_genome_topology(genome, config, file_path: str | None = None):
    print("\n" + "="*40)
    print(" BEST GENOME TOPOLOGY ")
    print("="*40)
    
    # Define readable names for your 21 inputs
    input_names = {}
    idx = -1 # NEAT inputs are usually negative indices starting from -1 down to -num_inputs
    input_names[idx]   = "Time"
    input_names[idx]   = "Near_Edge"
    idx -= 2
    for i in range(2): # 5 Lanes
        lane_name = f"L{i}" # L0 is closest, L4 is furthest
        input_names[idx] = f"{lane_name}_Road"
        input_names[idx-1] = f"{lane_name}_Water"
        input_names[idx-2] = f"{lane_name}_Speed"
        input_names[idx-3] = f"{lane_name}_Obs1_X"
        input_names[idx-4] = f"{lane_name}_Obs2_X"
        idx -= 5
    lane_name = f"L{2}" # L0 is closest, L4 is furthest
    input_names[idx] = f"{lane_name}_Road"
    input_names[idx-1] = f"{lane_name}_Water"
    input_names[idx-2] = f"{lane_name}_Speed"
    input_names[idx-3] = f"{lane_name}_Obs1_X"
    idx -= 4
    for i in range(2): # 5 Lanes
        lane_name = f"L{i}" # L0 is closest, L4 is furthest
        input_names[idx] = f"{lane_name}_Road"
        input_names[idx-1] = f"{lane_name}_Water"
        idx -= 2
    
    output_names = {0: 'FORWARD', 1: 'LEFT', 2: 'RIGHT', 3: 'REST'}

    print(f"Nodes: {len(genome.nodes)}")
    print(f"Connections: {len(genome.connections)}")
    print("-" * 40)
    
    # Sort connections by absolute weight to see strongest drivers first
    sorted_conns = sorted(genome.connections.values(), key=lambda c: abs(c.weight), reverse=True)
    
    for conn in sorted_conns:
        if not conn.enabled:
            continue
            
        # Resolve Source Name
        src = input_names.get(conn.key[0], f"Node {conn.key[0]}")
        
        # Resolve Target Name
        tgt = output_names.get(conn.key[1], f"Node {conn.key[1]}")
        
        # Visual weight
        weight_bar = "+" * int(conn.weight) if conn.weight > 0 else "-" * int(abs(conn.weight))
        print(f"{src:>15}  -->  {tgt:<10}  [{conn.weight:+.2f}] {weight_bar}")

    # Image Generation (Matplotlib)
    if file_path:
        print(f"\nGenerating network graph -> {file_path}...")
        
        # Create a figure without a window (headless)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.set_title(f"Winner Genome (Fit: {int(genome.fitness)})")
        
        # Separate nodes by type
        inputs = []
        outputs = []
        hidden = []
        
        active_nodes = set()
        for c in sorted_conns:
            active_nodes.add(c.key[0])
            active_nodes.add(c.key[1])
            
        for n in active_nodes:
            if n < 0: inputs.append(n)
            elif n < 4: outputs.append(n)
            else: hidden.append(n)
            
        # Determine Positions (Layered Layout)
        pos = {}
        
        # Inputs on Left (x=0)
        inputs.sort(reverse=True) # Keep logical order (L0 top, L4 bottom)
        for i, n in enumerate(inputs):
            y = 1.0 - (i / max(1, len(inputs)-1))
            pos[n] = (0, y)
            
        # Outputs on Right (x=1)
        outputs.sort()
        for i, n in enumerate(outputs):
            y = 1.0 - (i / max(1, len(outputs)-1))
            pos[n] = (1, y)
            
        # Hidden in Center (x=0.5) - Simple vertical distribution
        hidden.sort()
        for i, n in enumerate(hidden):
            y = 1.0 - (i / max(1, len(hidden)-1)) if len(hidden) > 1 else 0.5
            pos[n] = (0.5, y)

        # Draw Edges
        for c in sorted_conns:
            src, dst = c.key
            if src in pos and dst in pos:
                x_vals = [pos[src][0], pos[dst][0]]
                y_vals = [pos[src][1], pos[dst][1]]
                
                color = 'green' if c.weight > 0 else 'red'
                width = min(abs(c.weight) * 1.8, 3.6) # Cap thickness
                alpha = min(abs(c.weight)/3.0 + 0.1, 0.9)
                
                ax.plot(x_vals, y_vals, c=color, lw=width, alpha=alpha, zorder=1)

        # Draw Nodes
        for n, (x, y) in pos.items():
            # Colors: Input=Blue, Output=Orange, Hidden=Grey
            color = 'lightblue' if n < 0 else ('orange' if n < 4 else 'lightgrey')
            
            circle = plt.Circle((x, y), 0.1, color=color, ec='black', zorder=2)
            ax.add_patch(circle)
            
            # Text Label
            lbl = input_names.get(n, output_names.get(n, str(n)))
            ax.text(x, y, lbl, fontsize=6, ha='center', va='center', fontweight='bold', zorder=3)

        ax.axis('off')
        ax.set_aspect('equal')
        
        # Save and Close
        plt.tight_layout()
        plt.savefig(file_path, dpi=150)
        plt.close(fig)
        print("Graph saved successfully.")

class LiveVisualizer:
    def __init__(self, config):
        self.config = config
        self.fig, self.ax = plt.subplots(figsize=(8, 5))
        plt.ion()  # Turn on interactive mode
        self.fig.suptitle("Leader Brain Topology")
        
        # --- 1. Define Node Names (Matching your get_inputs logic) ---
        self.node_names = {}
        idx = -1 
        
        # Global Inputs
        self.node_names[idx] = "Time"; idx -= 1
        self.node_names[idx] = "Edge"; idx -= 1
        
        # L0 (Closest)
        self.node_names[idx] = "L0_Asph"; idx -= 1
        self.node_names[idx] = "L0_Watr"; idx -= 1
        self.node_names[idx] = "L0_Spd";  idx -= 1
        self.node_names[idx] = "L0_Ob1";  idx -= 1
        self.node_names[idx] = "L0_Ob2";  idx -= 1
        
        # L1
        self.node_names[idx] = "L1_Asph"; idx -= 1
        self.node_names[idx] = "L1_Watr"; idx -= 1
        self.node_names[idx] = "L1_Spd";  idx -= 1
        self.node_names[idx] = "L1_Ob1";  idx -= 1
        self.node_names[idx] = "L1_Ob2";  idx -= 1
        
        # L2
        self.node_names[idx] = "L2_Asph"; idx -= 1
        self.node_names[idx] = "L2_Watr"; idx -= 1
        self.node_names[idx] = "L2_Spd";  idx -= 1
        self.node_names[idx] = "L2_Ob1";  idx -= 1
        
        # L3
        self.node_names[idx] = "L3_Asph"; idx -= 1
        self.node_names[idx] = "L3_Watr"; idx -= 1
        
        # L4
        self.node_names[idx] = "L4_Asph"; idx -= 1
        self.node_names[idx] = "L4_Watr"; idx -= 1
        
        # Outputs
        self.node_names[0] = "FWD"
        self.node_names[1] = "LEFT"
        self.node_names[2] = "RIGHT"
        self.node_names[3] = "REST"

    async def update(self, genome):
        self.ax.clear()
        
        # 1. Build Graph
        # We separate nodes by layers for visual clarity
        inputs = []
        outputs = []
        hidden = []
        
        # Collect nodes from genome connections
        active_nodes = set()
        for key, conn in genome.connections.items():
            if conn.enabled:
                active_nodes.add(key[0])
                active_nodes.add(key[1])
        
        for n in active_nodes:
            if n < 0: inputs.append(n)
            elif n < 4: outputs.append(n)
            else: hidden.append(n)
            
        # 2. Assign Positions (Manual Layout)
        pos = {}
        
        # Inputs: x=0, distributed vertically
        inputs.sort(reverse=True) # Sort to keep order consistent
        for i, node in enumerate(inputs):
            y = (i / (len(inputs) - 1)) if len(inputs) > 1 else 0.5
            pos[node] = (-1, y)
            
        # Outputs: x=1, distributed vertically
        outputs.sort()
        for i, node in enumerate(outputs):
            y = (i / (len(outputs) - 1)) if len(outputs) > 1 else 0.5
            pos[node] = (1, y)
            
        # Hidden: x=0, distributed randomly or by ID
        # (Simple heuristic: place them in a column in the middle)
        hidden.sort()
        for i, node in enumerate(hidden):
            y = (i / (len(hidden) + 1))  # Avoid 0 and 1
            pos[node] = (0, y + 0.1) # Slight offset

        # 3. Draw Edges
        for key, conn in genome.connections.items():
            if not conn.enabled: continue
            
            src, dst = key
            if src not in pos or dst not in pos: continue
            
            # Style based on weight
            color = 'green' if conn.weight > 0 else 'red'
            width = min(abs(conn.weight) * 1.8, 3.6) # Cap thickness
            alpha = min(abs(conn.weight) / 3.0 + 0.1, 0.9)
            
            # Draw line
            x_vals = [pos[src][0], pos[dst][0]]
            y_vals = [pos[src][1], pos[dst][1]]
            self.ax.plot(x_vals, y_vals, color=color, linewidth=width, alpha=alpha, zorder=1)

        # 4. Draw Nodes
        for node, (x, y) in pos.items():
            # Color logic
            c = 'skyblue' if node < 0 else ('orange' if node < 4 else 'lightgrey')
            self.ax.add_patch(plt.Circle((x, y), 0.1, color=c, zorder=2))
            
            # Label
            lbl = self.node_names.get(node, str(node))
            self.ax.text(x, y, lbl, fontsize=6, ha='center', va='center', zorder=3, fontweight='bold')

        self.ax.set_xlim(-1.2, 1.2)
        self.ax.set_ylim(-0.1, 1.1)
        self.ax.axis('off')
        self.ax.set_aspect('equal')
        
        # CRITICAL: This updates the window without blocking
        plt.pause(0.001)


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
        self.max_stagnation_frames = 180 # FPS * 3  # 3 seconds to make a step, then fitness will decrease
        self.max_stagnation_frames_to_death = 480 # FPS * 8  # if the frog doesn't move for 7 seconds it dies

    def get_inputs(self) -> list[float]:
        """Returns a list of the inputs for the first layer of the network.
        - stagnation time (log-transformed)
        - a variable that is 
            -1 if the frog is near the left edge,
            1 if it is close to the right edge
            0 othewise
        - lane speed (3x nearest lanes)
        - one hot encoding for type of ground (10x inputs)
        - 2 x-nearest vehicles for the 0th level
        - 2 x-nearest vehicles for the 1st level
        - 1 x-nearest vehicle for the 2nd level
        Total: 20 inputs
        """
        how_long_has_been_resting_lognormalized = (
            -1 + 2*math.log2(self.stagnation_timer+1)/math.log2(480)
        )
        frogh = 0
        if self.frog.rect.centerx - self.frog.step_size < 0:
            frogh = -1
        elif self.frog.rect.centerx + self.frog.step_size > SCREEN_WIDTH:
            frogh = 1
        inputs = [how_long_has_been_resting_lognormalized, frogh]
        for lev, line in enumerate(self.lines):
            # print(line.texture_type)
            # 1. Type & Speed
            # type_val = 0 # 0 if it's grass
            # if line.texture_type == Texture.WATER:
            #     type_val = -1
            # elif line.texture_type == Texture.ASPHALT:
            #     type_val = 1
            is_asphalt = 1.0 if line.texture_type == Texture.ASPHALT else 0.0
            is_water = 1.0 if line.texture_type == Texture.WATER else 0.0
            inputs.extend([is_asphalt, is_water])
            if lev < 3:
                inputs.append(line.speed / 5.0)
            
            # 2. Closest Obstacles (finding two closest relative to frog)
            obstacles = sorted(line.obstacles, key=lambda o: abs(o.rect.centerx - self.frog.rect.centerx))
            how_many_obstacles = [2, 2, 1, 0, 0] # not all obstacles are measured, to save nodes
            for i in range(how_many_obstacles[lev]):
                if i < len(obstacles):
                    if obstacles[i].rect.centerx < self.frog.rect.centerx:
                        rel_x = (obstacles[i].rect.right - self.frog.rect.left) / SCREEN_WIDTH
                    else:
                        rel_x = (obstacles[i].rect.left - self.frog.rect.right) / SCREEN_WIDTH
                    # rel_y = (obstacles[i].rect.centery - self.frog.rect.centery) / SCREEN_HEIGHT
                    inputs.append(rel_x)
                    # inputs.append(rel_y)
                else:
                    inputs.append(-1.0 * line.speed)
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
        self.frog.update()
        
        # 2. Death Condition: Side Edges
        # If the frog center goes off-screen, it's a death
        if self.frog.rect.centerx < 0 or self.frog.rect.centerx > SCREEN_WIDTH:
            self.genome.fitness -= 5 # Penalty for falling off the side
            self.alive = False

        # 3. Death Condition: Stagnation (Waiting too long)
        if self.stagnation_timer > self.max_stagnation_frames:
            # Gradually drain fitness for staying still
            self.genome.fitness -= 0.05 # 3 * 1/FPS 
            
            # If the frog is absolutely useless, kill it
            if self.stagnation_timer > self.max_stagnation_frames_to_death:
                self.alive = False
            if self.genome.fitness < -5:
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
        # We store it in a global or passing it around if needed, 
        # but creating it here is fine for the session.
        # Note: If you close the plot window, it might crash, so keep it open.
        global viz
        viz = LiveVisualizer(config)
        sleep(10) # This is for me for starting filming

    # Initialize simulations
    sims = []
    for genome_id, genome in genomes:
        genome.fitness = 0
        sims.append(SingleSimulation(genome, config, seed=generation))

    generation_running = True
    frame_count = 0 # To throttle graph updates
    while generation_running and len(sims) > 0:
        frame_count += 1
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

            # --- UPDATE GRAPH (Throttle: Once every 30 frames) ---
            if frame_count % FPS == 1:
                asyncio.run(viz.update(leader.genome))
            
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

    winner = p.run(eval_genomes, 200)
    print('\nBest genome:\n{!s}'.format(winner))
    print_genome_topology(winner, config, file_path='final_network.png')

if __name__ == '__main__':
    run_neat('neat-config.txt')