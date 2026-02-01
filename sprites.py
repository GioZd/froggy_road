import pygame
from game_config import FPS, SCREEN_WIDTH, SCREEN_HEIGHT

from enum import Enum
import random

class Texture(Enum):
    GRASS = 0
    ASPHALT = 1
    WATER = 2

def load_image(path: str, 
               size: tuple[int, int] | None = None, 
               rotation: int = 0):
    img = pygame.image.load(path)
    if size:
        img = pygame.transform.rotate(img, rotation)
        img = pygame.transform.scale(img, size)
    return img

ASPHALT_TEXTURE = load_image("assets/roadline.png", 
                             size=(SCREEN_WIDTH, SCREEN_HEIGHT/5))
CAR = load_image("assets/cars/Sport/sport_red.png", 
                 size=(64, 0.6*SCREEN_HEIGHT/5), rotation=-90)
TRUCK = load_image("assets/cars/Truck/truck_blue.png", 
                 size=(90, 0.8*SCREEN_HEIGHT/5), rotation=-90)
SHORTLOG = load_image("assets/short-log.png", size=(72, 36))
LONGLOG = load_image("assets/long-log.png", size=(108, 36))

class Frog(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.original_image = load_image("assets/frog.png", size=(32,32))
        self.image = self.original_image
        self.rect = self.image.get_rect()
        self.rect.center = (SCREEN_WIDTH/2, SCREEN_HEIGHT-42)

        # Cooldown attributes
        # self.move_cooldown = 300  # 0.3 seconds in milliseconds
        # self.last_move_time = pygame.time.get_ticks()
        self.move_cooldown = 0
        self.cooldown_duration = 15
        self.hitbox = pygame.Rect(0, 0, 16, 16) # it's where collision actually happens

        self.step_size = SCREEN_WIDTH / 16 # for horizontal moving

    def can_move(self):
        # current_time = pygame.time.get_ticks()
        # return current_time - self.last_move_time >= self.move_cooldown
        return self.move_cooldown == 0
    
    def move_horizontal(self, direction):
        if self.can_move():
            self.move_cooldown = self.cooldown_duration # reset timer

            # Move the visual rect
            self.rect.x += direction * self.step_size
            
            # Keep on screen
            # if self.rect.left < 0: self.rect.left = 0
            # if self.rect.right > SCREEN_WIDTH: self.rect.right = SCREEN_WIDTH
            if self.rect.left < -64:
                self.rect.left = 0
            elif self.rect.right > SCREEN_WIDTH + 64:
                self.rect.right = SCREEN_WIDTH
            
            # Sync the hitbox!
            self.hitbox.center = self.rect.center
            
            # Rotate sprite (Optional: use pygame.transform.rotate)
            if direction > 0:
                # Face Right
                self.image = pygame.transform.rotate(self.original_image, -90)
            else:
                # Face Left
                self.image = pygame.transform.rotate(self.original_image, 90)
            
            # self.last_move_time = pygame.time.get_ticks()
    
    def jump(self):
        self.move_cooldown = self.cooldown_duration
        # self.last_move_time = pygame.time.get_ticks()

    def face_north(self):
        self.image = self.original_image

    def stay_on_platform(self, platform_speed):
        self.rect.x += platform_speed
        
        # Keep frog within screen bounds while riding
        if self.rect.left < -64:
            self.rect.left = 0
        elif self.rect.right > SCREEN_WIDTH + 64:
            self.rect.right = SCREEN_WIDTH
        
        self.hitbox.center = self.rect.center
    
    def draw(self, surface):
        surface.blit(self.image, self.rect)

    def update(self):
        # Decrement cooldown every frame
        if self.move_cooldown > 0:
            self.move_cooldown -= 1



class Obstacle(pygame.sprite.Sprite):
    def __init__(self, x, y, speed, is_car=True):
        super().__init__()
        self.speed = speed
        self.is_car = is_car # True for Car, False for Log
        
        if is_car:
            # Reuse your car sprite logic here
            self.image = pygame.transform.flip(CAR, 1, 0) if speed < 0 else CAR
        else:
            # Create a log shape using built-in rect
            self.image =  random.choice([SHORTLOG, LONGLOG])
            
        self.rect = self.image.get_rect(center=(x, y))

    def update(self, line_y):
        # Move horizontally
        self.rect.x += self.speed
        
        # Keep the obstacle locked to the vertical position of its line
        # This handles the "smooth sliding" automatically!
        self.rect.centery = line_y + (SCREEN_HEIGHT / 10) # Center of the lane

        # Wrap around screen
        if self.speed > 0 and self.rect.left > SCREEN_WIDTH:
            self.kill()
        elif self.speed < 0 and self.rect.right < 0:
            self.kill()



class Line(pygame.sprite.Sprite):
    def __init__(self, texture: Texture = Texture.GRASS, 
                 progress: int = 0, rng = None):
        super().__init__()
        self.size = (SCREEN_WIDTH, int(SCREEN_HEIGHT / 5))
        self.texture_type = texture
        self.safe_ground = True
        if texture == Texture.GRASS:
            self.__load_grass()
        elif texture == Texture.ASPHALT:
            self.__load_road()
        elif texture == Texture.WATER:
            self.__load_river()
            self.safe_ground = False
        self.rect = self.image.get_rect()
        self.target_y = 0

        self.rng = random if rng is None else rng
        ## Line is responsible for the cars/logs spawning
        self.obstacles = pygame.sprite.Group()

        if texture == Texture.ASPHALT:
            self.speed = self.rng.choice([-3, -2, 2, 3])
            self.spawn_rate = round(max(60, 150 - (progress * 0.6)))
            # round(max(800, 2500 - (progress * 10)) * FPS / 1000)
        elif texture == Texture.WATER:
            self.speed = self.rng.choice([-1.75, -1.5, -1.25, 1.25, 1.5, 1.75]) # Logs move slower
            self.spawn_rate = round(min(270, 108 + (progress * 1.2)))
            # round(min(5000, 1800 + (progress * 20)) * FPS / 1000) # Cap at 5s
        else: 
            self.speed = 0
            self.spawn_rate = 0
        self.spawn_timer = 0
        self.last_spawn_time = pygame.time.get_ticks()


    def __spawn_initial_obstacles(self, is_car: bool):
        """Place 2-3 obstacles initially so the road isn't empty
        (deprecated to a non-circular approach)
        """
        spacing = SCREEN_WIDTH / 2
        for i in range(2):
            obs = Obstacle(i * spacing + self.rng.randint(0, 15), self.rect.y, self.speed, is_car)
            self.obstacles.add(obs)

    def _spawn_single_obstacle(self):
        # Start at the edge based on speed direction
        x_start = -100 if self.speed > 0 else SCREEN_WIDTH + 100
        is_car = (self.texture_type == Texture.ASPHALT)
        new_obs = Obstacle(x_start, self.rect.y, self.speed, is_car)
        self.obstacles.add(new_obs)
 
    def __load_road(self):
        self.image = ASPHALT_TEXTURE
        self.rect = self.image.get_rect()

    def __load_river(self):
        self.image = pygame.Surface(self.size)
        self.image.fill("cyan")

    def __load_grass(self):
        self.image = pygame.Surface(self.size)
        self.image.fill("forestgreen")

    def goto_level(self, level: int):
        """"0th level: go to the bottom, 4th level: go to the top"""
        if level < 0 or level > 4:
            raise ValueError("Game is designed for 5 levels")
        
        # Calculate where the line SHOULD be
        # level 0 is the bottom, level 4 is the top
        self.target_y = SCREEN_HEIGHT - (level + 1) * (SCREEN_HEIGHT / 5)

    def update(self):
        """Slide backwards and move obstacles (Frame-based)"""
        # 1. Slide logic
        # This is already frame-based (moves a % of distance per frame)
        distance = self.target_y - self.rect.y
        if abs(distance) > 1:
            self.rect.y += distance * 0.2
        else:
            self.rect.y = self.target_y

        # 2. Check for Spawning (Frame-based counter)
        if self.spawn_rate > 0:
            # decrement our frame counter instead of checking system clock
            self.spawn_timer -= 1 
            
            if self.spawn_timer <= 0:
                self._spawn_single_obstacle()
                # Reset the timer. 
                # Note: You should adjust spawn_rate in __init__ to be 
                # a number of frames (e.g., 60 to 180) instead of ms.
                self.spawn_timer = self.spawn_rate + self.rng.randint(-5, 20)

        # 3. Update existing obstacles
        # Pass the current lane Y so obstacles stay aligned with the sliding lane
        self.obstacles.update(self.rect.y)

    # def update(self):
    #     """Slide backwards and move obstacles"""
    #     distance = self.target_y - self.rect.y
        
    #     if abs(distance) > 1:
    #         self.rect.y += distance * 0.2
    #     else:
    #         self.rect.y = self.target_y

    #     # 2. Check for Spawning
    #     if self.spawn_rate > 0:
    #         now = pygame.time.get_ticks()
    #         if now - self.last_spawn_time > self.spawn_rate:
    #             self._spawn_single_obstacle()
    #             self.last_spawn_time = now

    #     # 3. Update existing obstacles
    #     self.obstacles.update(self.rect.y)