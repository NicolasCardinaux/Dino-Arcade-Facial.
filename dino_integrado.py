import pygame
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import math
import random
import sys
import numpy as np

# Inicializar Pygame
pygame.init()

# --- Constantes del Juego ---
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 400
FPS = 60
GRAVITY = 0.6
JUMP_VELOCITY = -10.5
GAME_SPEED = 7

# Colores
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Configurar Ventana
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Integrated Chrome Dino con MediaPipe")
clock = pygame.time.Clock()

# --- Cargar y Recortar Sprites ---
try:
    sprite_sheet = pygame.image.load("sprite.png").convert()
    sprite_sheet.set_colorkey(WHITE) # Fondo transparente si es blanco
except pygame.error:
    print("Error: No se encontró 'sprite.png'.")
    sys.exit()

def get_sprite(x, y, w, h):
    sprite = pygame.Surface((w, h), pygame.SRCALPHA)
    sprite.blit(sprite_sheet, (0, 0), (x, y, w, h))
    sprite.set_colorkey(WHITE)
    return sprite

# Coordenadas exactas del sprite sheet original de Chrome (100% offline)
DINO_RUN1 = get_sprite(936, 2, 44, 47)
DINO_RUN2 = get_sprite(980, 2, 44, 47)
DINO_DUCK1 = get_sprite(1112, 2, 59, 47)
DINO_DUCK2 = get_sprite(1171, 2, 59, 47)
CACTUS_SMALL = [get_sprite(228, 2, 17, 35), get_sprite(245, 2, 17, 35), get_sprite(262, 2, 17, 35)]
CACTUS_LARGE = [get_sprite(332, 2, 25, 50), get_sprite(357, 2, 25, 50), get_sprite(382, 2, 25, 50)]
GROUND_SPRITE = get_sprite(2, 54, 1200, 12)

# --- Clases del Juego ---
class Dino:
    def __init__(self):
        self.x = 50
        self.y = 250
        self.y_base = 250
        self.vel_y = 0
        self.is_jumping = False
        self.is_ducking = False
        self.step_index = 0
        self.image = DINO_RUN1
        self.rect = self.image.get_rect(topleft=(self.x, self.y))

    def update(self):
        if self.is_ducking and not self.is_jumping:
            self.image = DINO_DUCK1 if self.step_index < 5 else DINO_DUCK2
            self.rect = self.image.get_rect(topleft=(self.x, self.y + 17)) # Bajar hitbox
        else:
            self.image = DINO_RUN1 if self.step_index < 5 else DINO_RUN2
            self.rect = self.image.get_rect(topleft=(self.x, self.y))
        
        if self.is_jumping:
            self.image = DINO_RUN1
            self.y += self.vel_y
            self.vel_y += GRAVITY
            if self.y >= self.y_base:
                self.y = self.y_base
                self.is_jumping = False
                self.vel_y = 0
                
        self.step_index += 1
        if self.step_index >= 10:
            self.step_index = 0
        
        self.rect.y = self.y if not self.is_ducking or self.is_jumping else self.y + 17

    def draw(self, surface):
        surface.blit(self.image, (self.rect.x, self.rect.y))

class Obstacle:
    def __init__(self):
        self.type = random.choice([0, 1]) # 0=Small, 1=Large
        if self.type == 0:
            self.image = random.choice(CACTUS_SMALL)
            self.rect = self.image.get_rect(topleft=(SCREEN_WIDTH, 260))
        else:
            self.image = random.choice(CACTUS_LARGE)
            self.rect = self.image.get_rect(topleft=(SCREEN_WIDTH, 245))

    def update(self):
        self.rect.x -= GAME_SPEED

    def draw(self, surface):
        surface.blit(self.image, (self.rect.x, self.rect.y))

# --- Inteligencia Artificial (MediaPipe) ---
base_options = python.BaseOptions(model_asset_path='face_landmarker.task')
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    num_faces=1,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
    min_tracking_confidence=0.5
)
detector = vision.FaceLandmarker.create_from_options(options)
cap = cv2.VideoCapture(0)

def get_distance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

# --- Variables de Calibración ---
mar_threshold = None
proximity_threshold = None
calibrated = False

font = pygame.font.SysFont("Courier", 20, bold=True)
big_font = pygame.font.SysFont("Courier", 30, bold=True)

# Instancias
dino = Dino()
obstacles = []
score = 0
ground_x = 0
game_over = False

def reset_game():
    global obstacles, score, game_over, GAME_SPEED
    obstacles = []
    score = 0
    GAME_SPEED = 7
    game_over = False
    dino.y = dino.y_base
    dino.is_jumping = False

# Bucle principal
running = True
while running:
    # Manejar eventos Pygame
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c and not calibrated:
                pass # Se maneja abajo con la cámara
            if event.key == pygame.K_r and game_over:
                reset_game()

    # 1. Capturar e Procesar Cámara
    success, frame = cap.read()
    if not success:
        continue
    
    frame = cv2.flip(frame, 1)
    h_cam, w_cam, _ = frame.shape
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    results = detector.detect(mp_image)
    
    is_mouth_open = False
    is_face_close = False
    
    if results.face_landmarks:
        face = results.face_landmarks[0]
        landmarks = [(int(lm.x * w_cam), int(lm.y * h_cam)) for lm in face]
        
        # MAR
        p_top, p_bottom, p_left, p_right = landmarks[13], landmarks[14], landmarks[78], landmarks[308]
        v_dist = get_distance(p_top, p_bottom)
        h_dist = get_distance(p_left, p_right)
        mar = v_dist / h_dist if h_dist > 0 else 0
        
        # Proximity
        f_top, f_bottom, f_left, f_right = landmarks[10], landmarks[152], landmarks[234], landmarks[454]
        proximity = math.hypot(get_distance(f_top, f_bottom), get_distance(f_left, f_right))
        
        cv2.rectangle(rgb_frame, (f_left[0], f_top[1]), (f_right[0], f_bottom[1]), (0, 255, 0), 2)
        cv2.circle(rgb_frame, p_top, 3, (255, 0, 0), -1)
        cv2.circle(rgb_frame, p_bottom, 3, (255, 0, 0), -1)

        keys = pygame.key.get_pressed()
        if not calibrated:
            cv2.putText(rgb_frame, "Mantener neutral y", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2)
            cv2.putText(rgb_frame, "apretar 'C'", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2)
            if keys[pygame.K_c]:
                mar_threshold = mar * 1.5
                proximity_threshold = proximity * 1.15
                calibrated = True
        else:
            is_mouth_open = mar > mar_threshold
            is_face_close = proximity > proximity_threshold
            
            # Conexión directa al Dino
            if not game_over:
                if is_mouth_open and not dino.is_jumping:
                    dino.is_jumping = True
                    dino.vel_y = JUMP_VELOCITY
                
                dino.is_ducking = is_face_close

    # Convertir OpenCV a Superficie Pygame
    rgb_frame = np.rot90(rgb_frame) # Pygame usa coordenadas transpuetas
    cam_surface = pygame.surfarray.make_surface(rgb_frame)
    # Escalar la cámara a Picture-in-Picture (por ej. 250x180)
    pip_w, pip_h = 240, 180
    cam_surface = pygame.transform.scale(cam_surface, (pip_w, pip_h))

    # 2. Lógica del Juego
    screen.fill(WHITE)
    
    if not calibrated:
        text = big_font.render("CALIBRACIÓN REQUERIDA (Mira la cámara)", True, BLACK)
        screen.blit(text, (SCREEN_WIDTH//2 - 300, SCREEN_HEIGHT//2))
    elif not game_over:
        # Actualizar suelo
        ground_x -= GAME_SPEED
        if ground_x <= -1200:
            ground_x = 0
        screen.blit(GROUND_SPRITE, (ground_x, 280))
        screen.blit(GROUND_SPRITE, (ground_x + 1200, 280))
        
        # Generar obstáculos
        if len(obstacles) == 0 or obstacles[-1].rect.x < SCREEN_WIDTH - random.randint(300, 600):
            obstacles.append(Obstacle())
        
        # Actualizar y dibujar
        dino.update()
        dino.draw(screen)
        
        for obs in obstacles[:]:
            obs.update()
            obs.draw(screen)
            if obs.rect.x < -50:
                obstacles.remove(obs)
            
            # Colisión con menor hitbox para hacerlo más jugable
            dino_hitbox = dino.rect.inflate(-15, -15) 
            obs_hitbox = obs.rect.inflate(-10, -10)
            if dino_hitbox.colliderect(obs_hitbox):
                game_over = True
                
        score += 0.1
        GAME_SPEED += 0.001
        
        score_text = font.render(f"Puntos: {int(score)}", True, BLACK)
        screen.blit(score_text, (20, 20))
    else:
        # Game Over
        text = big_font.render("GAME OVER - APRETA 'R' PARA REINICIAR", True, BLACK)
        screen.blit(text, (SCREEN_WIDTH//2 - 250, SCREEN_HEIGHT//2))
        screen.blit(GROUND_SPRITE, (ground_x, 280))
        dino.draw(screen)
        for obs in obstacles: obs.draw(screen)

    # 3. Dibujar Cámara PiP en la esquina
    screen.blit(cam_surface, (SCREEN_WIDTH - pip_w - 20, 20))
    pygame.draw.rect(screen, BLACK, (SCREEN_WIDTH - pip_w - 20, 20, pip_w, pip_h), 2)

    pygame.display.flip()
    clock.tick(FPS)

cap.release()
pygame.quit()
