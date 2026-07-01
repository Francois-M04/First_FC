import pgzrun
import pygame
from pygame.math import Vector2

# Configuration de la fenêtre
WIDTH = 800
HEIGHT = 600
TITLE = "Test Animation Joueur"

# Position du joueur
player_pos = Vector2(400, 300)
player_dir = 0  # 0=haut, 2=droite, 4=bas, 6=gauche
player_frame = 1
anim_counter = 0
speed = 3
is_moving = False  # Pour savoir si le joueur bouge

# Mapping des directions
dir_mapping = {
    0: "up",
    1: "up",
    2: "right",
    3: "down",
    4: "down",
    5: "down",
    6: "left",
    7: "up"
}

def update():
    global player_pos, player_dir, player_frame, anim_counter, is_moving
    
    # Mouvement du joueur avec les touches T, F, G, H
    dx, dy = 0, 0
    is_moving = False
    
    # Touche F = gauche
    if keyboard.f:
        dx = -1
        is_moving = True
    # Touche H = droite
    elif keyboard.h:
        dx = 1
        is_moving = True
    
    # Touche T = haut
    if keyboard.t:
        dy = -1
        is_moving = True
    # Touche G = bas
    elif keyboard.g:
        dy = 1
        is_moving = True
    
    # Appliquer le mouvement
    if is_moving:
        # Normaliser le vecteur pour que la diagonale ne soit pas plus rapide
        if dx != 0 and dy != 0:
            dx = dx * 0.707
            dy = dy * 0.707
        
        player_pos.x += dx * speed
        player_pos.y += dy * speed
        
        # Calculer la direction (angle 0-7)
        # 0 = haut, 2 = droite, 4 = bas, 6 = gauche
        if dy < 0 and dx == 0:
            target_dir = 0  # haut
        elif dy < 0 and dx > 0:
            target_dir = 1  # haut-droite
        elif dy == 0 and dx > 0:
            target_dir = 2  # droite
        elif dy > 0 and dx > 0:
            target_dir = 3  # bas-droite
        elif dy > 0 and dx == 0:
            target_dir = 4  # bas
        elif dy > 0 and dx < 0:
            target_dir = 5  # bas-gauche
        elif dy == 0 and dx < 0:
            target_dir = 6  # gauche
        elif dy < 0 and dx < 0:
            target_dir = 7  # haut-gauche
        
        # Rotation progressive vers la direction cible
        dir_diff = (target_dir - player_dir)
        player_dir = (player_dir + [0, 1, 1, 1, 1, 7, 7, 7][dir_diff % 8]) % 8
        
        # Animation - changement de frame toutes les 8 frames
        anim_counter += 1
        if anim_counter >= 8:
            anim_counter = 0
            player_frame = 1 if player_frame == 2 else 2
    else:
        # Le joueur ne bouge pas - on réinitialise l'animation
        anim_counter = 0
        player_frame = 1  # Frame 1 pour l'idle

def draw():
    screen.clear()
    screen.fill((0,0,0))  # Fond vert comme un terrain
    
    # Déterminer le nom de la direction
    dir_name = dir_mapping[player_dir]
    
    # Construire le nom de l'image
    if is_moving:
        # En mouvement - utiliser frame 1 ou 2
        image_name = "player0_" + dir_name + str(player_frame)
    else:
        # À l'arrêt - utiliser l'image idle
        image_name = "player0_" + dir_name + "_idle"
    
    # Afficher le joueur
    player = Actor(image_name, (player_pos.x, player_pos.y), anchor=(25, 37))
    player.draw()
    
    # Afficher des informations à l'écran
    screen.draw.text("Touches: T(Haut) F(Gauche) G(Bas) H(Droite)", (10, 10), color="white", fontsize=30)
    screen.draw.text(f"Direction: {dir_name} ({player_dir})", (10, 50), color="white", fontsize=20)
    
    if is_moving:
        screen.draw.text(f"Frame: {player_frame} (en mouvement)", (10, 80), color="white", fontsize=20)
    else:
        screen.draw.text("IDLE (à l'arrêt)", (10, 80), color="yellow", fontsize=20)
    
    screen.draw.text(f"Position: ({int(player_pos.x)}, {int(player_pos.y)})", (10, 110), color="white", fontsize=20)

pgzrun.go()