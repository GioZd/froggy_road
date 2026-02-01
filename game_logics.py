import pygame

import math
import random
from sprites import Line, Texture

class LevelGenerator:
    def __init__(self, initial_lines: list[Line], rng=None):
        self.lines = initial_lines
        self.steps_taken = 0
        self.rng = random if rng is None else rng

    def get_next_texture(self) -> Texture:
        self.steps_taken += 1
        last_texture = self.lines[-1].texture_type # We'll add this attribute to Line
        
        # 1. Calculate Probability of Grass
        # Using 1/log2(progress + 2) to avoid log(1) or log(0)
        p_grass = max(1.3 / math.log2(self.steps_taken + 2), 1/8)
        if last_texture == Texture.GRASS:
            p_grass = 0
            
        # 2. Determine remaining probability for Asphalt vs Water
        p_remaining = 1.0 - p_grass
        
        if last_texture == Texture.GRASS:
            # ASPHALT|GRASS = RIVER|GRASS = (1-GRASS|GRASS)/2
            p_asphalt = p_remaining / 2
        elif last_texture == Texture.ASPHALT:
            # ASPHALT|ASPHALT is 5x more likely than WATER|ASPHALT
            p_asphalt = (p_remaining / 6) * 5
            p_water = p_remaining / 6
        elif last_texture == Texture.WATER:
            # WATER|WATER is 3x more likely than ASPHALT|WATER
            p_water = (p_remaining / 4) * 3
            p_asphalt = p_remaining / 4
            
        # 3. Weighted Random Selection
        choice = self.rng.random()
        if choice < p_grass:
            return Texture.GRASS
        elif choice < (p_grass + p_asphalt):
            return Texture.ASPHALT
        else:
            return Texture.WATER

    def spawn_new_line(self, all_sprites: pygame.sprite.Group):
        # Remove oldest
        old_line = self.lines.pop(0)
        all_sprites.remove(old_line)
        
        # Create newest
        next_tex = self.get_next_texture()
        new_line = Line(next_tex, self.steps_taken, rng=self.rng)
        self.lines.append(new_line)
        all_sprites.add(new_line)