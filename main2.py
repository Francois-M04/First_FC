import pgzero, pgzrun, pygame
import math, sys, random
from enum import Enum
from pygame.math import Vector2

# Check Python version number.
if sys.version_info < (3,5):
    print("This game requires at least version 3.5 of Python. Please download it from www.python.org")
    sys.exit()

# Check Pygame Zero version.
pgzero_version = [int(s) if s.isnumeric() else s for s in pgzero.__version__.split('.')]
if pgzero_version < [1,2]:
    print("This game requires at least version 1.2 of Pygame Zero. You have version {0}. Please upgrade using the command 'pip3 install --upgrade pgzero'".format(pgzero.__version__))
    sys.exit()

WIDTH = 800
HEIGHT = 480
TITLE = "Substitute Soccer"

HALF_WINDOW_W = WIDTH / 2

# Size of level, including both the pitch and the boundary surrounding it
LEVEL_W = 1000
LEVEL_H = 1400
HALF_LEVEL_W = LEVEL_W // 2
HALF_LEVEL_H = LEVEL_H // 2

HALF_PITCH_W = 442
HALF_PITCH_H = 622

GOAL_WIDTH = 186
GOAL_DEPTH = 20
HALF_GOAL_W = GOAL_WIDTH // 2

PITCH_BOUNDS_X = (HALF_LEVEL_W - HALF_PITCH_W, HALF_LEVEL_W + HALF_PITCH_W)
PITCH_BOUNDS_Y = (HALF_LEVEL_H - HALF_PITCH_H, HALF_LEVEL_H + HALF_PITCH_H)

GOAL_BOUNDS_X = (HALF_LEVEL_W - HALF_GOAL_W, HALF_LEVEL_W + HALF_GOAL_W)
GOAL_BOUNDS_Y = (HALF_LEVEL_H - HALF_PITCH_H - GOAL_DEPTH,
                 HALF_LEVEL_H + HALF_PITCH_H + GOAL_DEPTH)

PITCH_RECT = pygame.rect.Rect(PITCH_BOUNDS_X[0], PITCH_BOUNDS_Y[0], HALF_PITCH_W * 2, HALF_PITCH_H * 2)
GOAL_0_RECT = pygame.rect.Rect(GOAL_BOUNDS_X[0], GOAL_BOUNDS_Y[0], GOAL_WIDTH, GOAL_DEPTH)
GOAL_1_RECT = pygame.rect.Rect(GOAL_BOUNDS_X[0], GOAL_BOUNDS_Y[1] - GOAL_DEPTH, GOAL_WIDTH, GOAL_DEPTH)

AI_MIN_X = 78
AI_MAX_X = LEVEL_W - 78
AI_MIN_Y = 98
AI_MAX_Y = LEVEL_H - 98

PLAYER_START_POS = [(350, 550), (650, 450), (200, 850), (500, 750), (800, 950), (350, 1250), (650, 1150)]

LEAD_DISTANCE_1 = 10
LEAD_DISTANCE_2 = 50

DRIBBLE_DIST_X, DRIBBLE_DIST_Y = 18, 16

# Speeds for players in various situations.
PLAYER_DEFAULT_SPEED = 2
CPU_PLAYER_WITH_BALL_BASE_SPEED = 2.6
PLAYER_INTERCEPT_BALL_SPEED = 2.75
LEAD_PLAYER_BASE_SPEED = 2.9
HUMAN_PLAYER_WITH_BALL_SPEED = 3
HUMAN_PLAYER_WITHOUT_BALL_SPEED = 3.3

DEBUG_SHOW_LEADS = False
DEBUG_SHOW_TARGETS = False
DEBUG_SHOW_PEERS = False
DEBUG_SHOW_SHOOT_TARGET = False
DEBUG_SHOW_COSTS = False

# Position fixe après un but - juste à côté du ballon au centre
GOAL_RESET_POSITION = Vector2(HALF_LEVEL_W - 60, HALF_LEVEL_H)

class Difficulty:
    def __init__(self, goalie_enabled, second_lead_enabled, speed_boost, holdoff_timer):
        self.goalie_enabled = goalie_enabled
        self.second_lead_enabled = second_lead_enabled
        self.speed_boost = speed_boost
        self.holdoff_timer = holdoff_timer

# On garde seulement la difficulté Easy (index 0)
DIFFICULTY = [Difficulty(False, False, 0, 120)]

# Custom sine/cosine functions for angles of 0 to 7
def sin(x):
    return math.sin(x*math.pi/4)

def cos(x):
    return sin(x+2)

def vec_to_angle(vec):
    return int(4 * math.atan2(vec.x, -vec.y) / math.pi + 8.5) % 8

def angle_to_vec(angle):
    return Vector2(sin(angle), -cos(angle))

def dist_key(pos):
    return lambda p: (p.vpos - pos).length()

def safe_normalise(vec):
    length = vec.length()
    if length == 0:
        return Vector2(0,0), 0
    else:
        return vec.normalize(), length

class MyActor(Actor):
    def __init__(self, img, x=0, y=0, anchor=None):
        super().__init__(img, (0, 0), anchor=anchor)
        self.vpos = Vector2(x, y)

    def draw(self, offset_x, offset_y):
        self.pos = (self.vpos.x - offset_x, self.vpos.y - offset_y)
        super().draw()

# Ball physics model parameters
KICK_STRENGTH = 11.5
DRAG = 0.98

def ball_physics(pos, vel, bounds):
    pos += vel
    if pos < bounds[0] or pos > bounds[1]:
        pos, vel = pos - vel, -vel
    return pos, vel * DRAG

def steps(distance):
    steps, vel = 0, KICK_STRENGTH
    while distance > 0 and vel > 0.25:
        distance, steps, vel = distance - vel, steps + 1, vel * DRAG
    return steps

class Goal(MyActor):
    def __init__(self, team):
        x = HALF_LEVEL_W
        y = 0 if team == 0 else LEVEL_H
        super().__init__("goal" + str(team), x, y)
        self.team = team

    def active(self):
        return abs(game.ball.vpos.y - self.vpos.y) < 500

def targetable(target, source):
    v0, d0 = safe_normalise(target.vpos - source.vpos)
    if not game.teams[source.team].human():
        for p in game.players:
            v1, d1 = safe_normalise(p.vpos - source.vpos)
            if p.team != target.team and d1 > 0 and d1 < d0 and v0*v1 > 0.8:
                return False
    return target.team == source.team and d0 > 0 and d0 < 300 and v0 * angle_to_vec(source.dir) > 0.8

def avg(a, b):
    return b if abs(b-a) < 1 else (a+b)/2

def on_pitch(x, y):
    return PITCH_RECT.collidepoint(x,y) or GOAL_0_RECT.collidepoint(x,y) or GOAL_1_RECT.collidepoint(x,y)

class Ball(MyActor):
    def __init__(self):
        super().__init__("ball", HALF_LEVEL_W, HALF_LEVEL_H)
        self.vel = Vector2(0, 0)
        self.owner = None
        self.timer = 0
        self.shadow = MyActor("balls")
        self.score = 0  # Compteur de buts
        self.goal_timer = 0  # Timer pour l'animation après un but

    def collide(self, p):
        return p.timer < 0 and (p.vpos - self.vpos).length() <= DRIBBLE_DIST_X

    def update(self):
        self.timer -= 1
        self.goal_timer -= 1

        if self.owner:
            new_x = avg(self.vpos.x, self.owner.vpos.x + DRIBBLE_DIST_X * sin(self.owner.dir))
            new_y = avg(self.vpos.y, self.owner.vpos.y - DRIBBLE_DIST_Y * cos(self.owner.dir))

            if on_pitch(new_x, new_y):
                self.vpos = Vector2(new_x, new_y)
            else:
                self.owner.timer = 60
                self.vel = angle_to_vec(self.owner.dir) * 3
                self.owner = None
        else:
            if abs(self.vpos.y - HALF_LEVEL_H) > HALF_PITCH_H:
                bounds_x = GOAL_BOUNDS_X
            else:
                bounds_x = PITCH_BOUNDS_X

            if abs(self.vpos.x - HALF_LEVEL_W) < HALF_GOAL_W:
                bounds_y = GOAL_BOUNDS_Y
            else:
                bounds_y = PITCH_BOUNDS_Y

            self.vpos.x, self.vel.x = ball_physics(self.vpos.x, self.vel.x, bounds_x)
            self.vpos.y, self.vel.y = ball_physics(self.vpos.y, self.vel.y, bounds_y)

        self.shadow.vpos = Vector2(self.vpos)

        for target in game.players:
            if (not self.owner or self.owner.team != target.team) and self.collide(target):
                if self.owner:
                    self.owner.timer = 60
                self.timer = game.difficulty.holdoff_timer
                game.teams[target.team].active_control_player = self.owner = target

        if self.owner:
            team = game.teams[self.owner.team]
            targetable_players = [p for p in game.players + game.goals if p.team == self.owner.team and targetable(p, self.owner)]

            if len(targetable_players) > 0:
                target = min(targetable_players, key=dist_key(self.owner.vpos))
                game.debug_shoot_target = target.vpos
            else:
                target = None

            if team.human():
                do_shoot = team.controls.shoot()
            else:
                do_shoot = self.timer <= 0 and target and cost(target.vpos, self.owner.team) < cost(self.owner.vpos, self.owner.team)

            if do_shoot:
                # Son supprimé
                # game.play_sound("kick", 4)

                if target:
                    r = 0
                    iterations = 8 if team.human() and isinstance(target, Player) else 1

                    for i in range(iterations):
                        t = target.vpos + angle_to_vec(self.owner.dir) * r
                        vec, length = safe_normalise(t - self.vpos)
                        r = HUMAN_PLAYER_WITHOUT_BALL_SPEED * steps(length)
                else:
                    vec = angle_to_vec(self.owner.dir)
                    target = min([p for p in game.players if p.team == self.owner.team],
                                 key=dist_key(self.vpos + (vec * 250)))

                if isinstance(target, Player):
                    game.teams[self.owner.team].active_control_player = target

                self.owner.timer = 10
                self.vel = vec * KICK_STRENGTH
                self.owner = None

        # Vérifier si le ballon est dans le but (au-delà de la ligne de but)
        if abs(self.vpos.y - HALF_LEVEL_H) > HALF_PITCH_H and self.goal_timer <= 0:
            self.score += 1
            self.goal_timer = 60  # Timer de 60 frames avant de réinitialiser
            
            # Réinitialiser le ballon au centre
            self.vpos = Vector2(HALF_LEVEL_W, HALF_LEVEL_H)
            self.vel = Vector2(0, 0)
            self.owner = None
            self.timer = 60
            
            # Réinitialiser la position du joueur à une position fixe près du ballon
            if len(game.players) > 0:
                player = game.players[0]
                player.vpos = Vector2(GOAL_RESET_POSITION)
                player.dir = 0  # Face vers le haut
                game.teams[0].active_control_player = player

def allow_movement(x, y):
    if abs(x - HALF_LEVEL_W) > HALF_LEVEL_W:
        return False
    elif abs(x - HALF_LEVEL_W) < HALF_GOAL_W + 20:
        return abs(y - HALF_LEVEL_H) < HALF_PITCH_H
    else:
        return abs(y - HALF_LEVEL_H) < HALF_LEVEL_H

def cost(pos, team, handicap=0):
    own_goal_pos = Vector2(HALF_LEVEL_W, 78 if team == 1 else LEVEL_H - 78)
    inverse_own_goal_distance = 3500 / (pos - own_goal_pos).length()

    result = inverse_own_goal_distance \
            + sum([4000 / max(24, (p.vpos - pos).length()) for p in game.players if p.team != team]) \
            + ((pos.x - HALF_LEVEL_W)**2 / 200 \
            - pos.y * (4 * team - 2)) \
            + handicap

    return result, pos

class Player(MyActor):
    ANCHOR = (25,37)

    def __init__(self, x, y, team):
        kickoff_y = (y / 2) + 550 - (team * 400)
        super().__init__("blank", x, kickoff_y, Player.ANCHOR)
        self.home = Vector2(x, y)
        self.team = team
        self.dir = 0
        self.anim_frame = -1
        self.timer = 0
        self.debug_target = Vector2(0, 0)
        self.anim_counter = 0
        self.current_frame = 1

    def active(self):
        return abs(game.ball.vpos.y - self.home.y) < 400

    def update(self):
        self.timer -= 1
        target = Vector2(self.home)
        speed = PLAYER_DEFAULT_SPEED

        my_team = game.teams[self.team]
        pre_kickoff = game.kickoff_player != None
        i_am_kickoff_player = self == game.kickoff_player
        ball = game.ball

        if self == game.teams[self.team].active_control_player and my_team.human() and (not pre_kickoff or i_am_kickoff_player):
            if ball.owner == self:
                speed = HUMAN_PLAYER_WITH_BALL_SPEED
            else:
                speed = HUMAN_PLAYER_WITHOUT_BALL_SPEED
            target = self.vpos + my_team.controls.move(speed)

        elif ball.owner != None:
            if ball.owner == self:
                costs = [cost(self.vpos + angle_to_vec(self.dir + d) * 3, self.team, abs(d)) for d in range(-2, 3)]
                _, target = min(costs, key=lambda element: element[0])
                speed = CPU_PLAYER_WITH_BALL_BASE_SPEED + game.difficulty.speed_boost

            elif ball.owner.team == self.team:
                if self.active():
                    direction = -1 if self.team == 0 else 1
                    target.x = (ball.vpos.x + target.x) / 2
                    target.y = (ball.vpos.y + 400 * direction + target.y) / 2
            else:
                if self.lead is not None:
                    target = ball.owner.vpos + angle_to_vec(ball.owner.dir) * self.lead
                    target.x = max(AI_MIN_X, min(AI_MAX_X, target.x))
                    target.y = max(AI_MIN_Y, min(AI_MAX_Y, target.y))
                    other_team = 1 if self.team == 0 else 0
                    speed = LEAD_PLAYER_BASE_SPEED
                    if game.teams[other_team].human():
                        speed += game.difficulty.speed_boost
                elif self.mark and self.mark.active():
                    if my_team.human():
                        target = Vector2(ball.vpos)
                    else:
                        vec, length = safe_normalise(ball.vpos - self.mark.vpos)
                        if isinstance(self.mark, Goal):
                            length = min(150, length)
                        else:
                            length /= 2
                        target = self.mark.vpos + vec * length
        else:
            if (pre_kickoff and i_am_kickoff_player) or (not pre_kickoff and self.active()):
                target = Vector2(ball.vpos)
                vel = Vector2(ball.vel)
                frame = 0

                while (target - self.vpos).length() > PLAYER_INTERCEPT_BALL_SPEED * frame + DRIBBLE_DIST_X and vel.length() > 0.5:
                    target += vel
                    vel *= DRAG
                    frame += 1

                speed = PLAYER_INTERCEPT_BALL_SPEED
            elif pre_kickoff:
                target.y = self.vpos.y

        vec, distance = safe_normalise(target - self.vpos)
        self.debug_target = Vector2(target)

        if distance > 0:
            distance = min(distance, speed)
            target_dir = vec_to_angle(vec)

            if allow_movement(self.vpos.x + vec.x * distance, self.vpos.y):
                self.vpos.x += vec.x * distance
            if allow_movement(self.vpos.x, self.vpos.y + vec.y * distance):
                self.vpos.y += vec.y * distance

            self.anim_frame = (self.anim_frame + max(distance, 1.0)) % 72
        else:
            target_dir = vec_to_angle(ball.vpos - self.vpos)
            self.anim_frame = -1

        dir_diff = (target_dir - self.dir)
        self.dir = (self.dir + [0, 1, 1, 1, 1, 7, 7, 7][dir_diff % 8]) % 8

        # Animation
        dir_mapping = {
            0: "up", 1: "up", 2: "right", 3: "down",
            4: "down", 5: "down", 6: "left", 7: "up"
        }
        
        dir_name = dir_mapping[self.dir]
        
        if distance > 1:
            self.anim_counter += distance / 4
            if self.anim_counter >= 2:
                self.anim_counter = 0
                self.current_frame = 1 if self.current_frame == 2 else 2
            suffix = dir_name + str(self.current_frame)
        else:
            suffix = dir_name + "_idle"
            self.current_frame = 1
            self.anim_counter = 0
        
        self.image = "player" + str(self.team) + "_" + suffix

class Team:
    def __init__(self, controls):
        self.controls = controls
        self.active_control_player = None
        self.score = 0

    def human(self):
        return self.controls != None

class Game:
    def __init__(self, p1_controls=None, p2_controls=None, difficulty=0):
        self.teams = [Team(p1_controls), Team(p2_controls)]
        self.difficulty = DIFFICULTY[difficulty]

        # MUSIQUE SUPPRIMÉE
        # try:
        #     if self.teams[0].human():
        #         music.fadeout(1)
        #         sounds.crowd.play(-1)
        #         sounds.start.play()
        #     else:
        #         music.play("theme")
        #         sounds.crowd.stop()
        # except Exception:
        #     pass

        self.score_timer = 0
        self.scoring_team = 1
        self.reset()

    def reset(self):
        # UN SEUL JOUEUR - player0
        self.players = []
        random_offset = lambda x: x + random.randint(-32, 32)
        # On crée seulement un joueur pour l'équipe 0
        self.players.append(Player(random_offset(PLAYER_START_POS[0][0]), random_offset(PLAYER_START_POS[0][1]), 0))

        # On crée quand même les deux goals pour la détection
        self.goals = [Goal(i) for i in range(2)]

        self.teams[0].active_control_player = self.players[0]
        self.teams[1].active_control_player = None  # Pas de joueur pour l'équipe 1

        other_team = 1 if self.scoring_team == 0 else 0
        self.kickoff_player = self.players[0]

        self.kickoff_player.vpos = Vector2(HALF_LEVEL_W - 30, HALF_LEVEL_H)

        self.ball = Ball()
        self.ball.score = 0  # Réinitialiser le score

        self.camera_focus = Vector2(self.ball.vpos)
        self.debug_shoot_target = None

    def update(self):
        self.score_timer -= 1

        if self.score_timer == 0:
            self.reset()

        # Reset mark et lead
        for b in self.players:
            b.mark = None
            b.lead = None
            b.debug_target = None

        self.debug_shoot_target = None

        # Mise à jour des joueurs et de la balle
        for obj in self.players + [self.ball]:
            obj.update()

        # Gestion du changement de joueur contrôlé
        for team_num in range(2):
            team_obj = self.teams[team_num]
            if team_obj.human() and team_obj.controls.shoot():
                def dist_key_weighted(p):
                    return (p.vpos - self.ball.vpos).length()
                self.teams[team_num].active_control_player = min([p for p in game.players if p.team == team_num],
                                                                 key=dist_key_weighted)

        # Caméra
        camera_ball_vec, distance = safe_normalise(self.camera_focus - self.ball.vpos)
        if distance > 0:
            self.camera_focus -= camera_ball_vec * min(distance, 8)

    def draw(self):
        offset_x = max(0, min(LEVEL_W - WIDTH, self.camera_focus.x - WIDTH / 2))
        offset_y = max(0, min(LEVEL_H - HEIGHT, self.camera_focus.y - HEIGHT / 2))
        offset = Vector2(offset_x, offset_y)

        screen.blit("pitch", (-offset_x, -offset_y))

        objects = sorted([self.ball] + self.players, key=lambda obj: obj.y)
        objects = [self.goals[0]] + objects + [self.goals[1]]

        for obj in objects:
            obj.draw(offset_x, offset_y)

        # AFFICHAGE DU SCORE (simple texte)
        screen.draw.text(f"Score: {self.ball.score}", 
                         (WIDTH // 2 - 50, 20), 
                         color="white", 
                         fontsize=40,
                         shadow=(1,1))

        if DEBUG_SHOW_LEADS:
            for p in self.players:
                if game.ball.owner and p.lead:
                    line_start = game.ball.owner.vpos - offset
                    line_end = p.vpos - offset
                    pygame.draw.line(screen.surface, (0,0,0), line_start, line_end)

        if DEBUG_SHOW_TARGETS:
            for p in self.players:
                line_start = p.debug_target - offset
                line_end = p.vpos - offset
                pygame.draw.line(screen.surface, (255,0,0), line_start, line_end)

        if DEBUG_SHOW_PEERS:
            for p in self.players:
                if hasattr(p, 'peer') and p.peer:
                    line_start = p.peer.vpos - offset
                    line_end = p.vpos - offset
                    pygame.draw.line(screen.surface, (0,0,255), line_start, line_end)

        if DEBUG_SHOW_SHOOT_TARGET:
            if self.debug_shoot_target and self.ball.owner:
                line_start = self.ball.owner.vpos - offset
                line_end = self.debug_shoot_target - offset
                pygame.draw.line(screen.surface, (255,0,255), line_start, line_end)

        if DEBUG_SHOW_COSTS and self.ball.owner:
            for x in range(0,LEVEL_W,60):
                for y in range(0, LEVEL_H, 26):
                    c = cost(Vector2(x,y), self.ball.owner.team)[0]
                    screen_pos = Vector2(x,y)-offset
                    screen_pos = (screen_pos.x,screen_pos.y)
                    screen.draw.text("{0:.0f}".format(c), center=screen_pos)

    # Fonction play_sound SUPPRIMÉE
    # def play_sound(self, name, c):
    #     if state != State.LANGUAGE and state != State.MENU and state != State.PAUSE:
    #         try:
    #             getattr(sounds, name+str(random.randint(0, c-1))).play()
    #         except:
    #             pass

# Dictionary to keep track of which keys are currently being held down
key_status = {}

def key_just_pressed(key):
    result = False
    prev_status = key_status.get(key, False)
    if not prev_status and keyboard[key]:
        result = True
    key_status[key] = keyboard[key]
    return result

class Controls:
    def __init__(self, player_num):
        if player_num == 0:
            self.key_up = keys.T
            self.key_down = keys.G
            self.key_left = keys.F
            self.key_right = keys.H
            self.key_shoot = keys.SPACE
        else:
            self.key_up = keys.W
            self.key_down = keys.S
            self.key_left = keys.A
            self.key_right = keys.D
            self.key_shoot = keys.LSHIFT

    def move(self, speed):
        dx, dy = 0, 0
        if keyboard[self.key_left]:
            dx = -1
        elif keyboard[self.key_right]:
            dx = 1
        if keyboard[self.key_up]:
            dy = -1
        elif keyboard[self.key_down]:
            dy = 1
        return Vector2(dx, dy) * speed

    def shoot(self):
        return key_just_pressed(self.key_shoot)

class State(Enum):
    LANGUAGE = 0
    MENU = 1
    PLAY = 2
    PAUSE = 3
    GAME_OVER = 4

class MenuState(Enum):
    LANGUAGE = 0
    NUM_PLAYERS = 1

class PauseState(Enum):
    RESUME = 0
    RESTART = 1
    QUIT = 2

# Variables globales
selected_language = 0
pause_selection = PauseState.RESUME

def update():
    global state, game, menu_state, menu_num_players, selected_language, pause_selection

    if state == State.LANGUAGE:
        selection_change = 0
        if key_just_pressed(keys.DOWN):
            selection_change = 1
        elif key_just_pressed(keys.UP):
            selection_change = -1
        
        if selection_change != 0:
            # SON SUPPRIMÉ
            # try:
            #     sounds.move.play()
            # except Exception:
            #     pass
            selected_language = (selected_language + selection_change) % 4
        
        if key_just_pressed(keys.SPACE):
            state = State.MENU
            menu_state = MenuState.NUM_PLAYERS

    elif state == State.MENU:
        if key_just_pressed(keys.SPACE):
            if menu_num_players == 1:
                state = State.PLAY
                menu_state = None
                game = Game(Controls(0), None, 0)
            else:
                state = State.PLAY
                menu_state = None
                game = Game(Controls(0), Controls(1), 0)
        else:
            selection_change = 0
            if key_just_pressed(keys.DOWN):
                selection_change = 1
            elif key_just_pressed(keys.UP):
                selection_change = -1
            if selection_change != 0:
                # SON SUPPRIMÉ
                # try:
                #     sounds.move.play()
                # except Exception:
                #     pass
                menu_num_players = 2 if menu_num_players == 1 else 1

        game.update()

    elif state == State.PLAY:
        if key_just_pressed(keys.ESCAPE):
            state = State.PAUSE
            pause_selection = PauseState.RESUME
            # SON SUPPRIMÉ
            # try:
            #     sounds.pause.play()
            # except Exception:
            #     pass
        else:
            game.update()

    elif state == State.PAUSE:
        selection_change = 0
        if key_just_pressed(keys.DOWN):
            selection_change = 1
        elif key_just_pressed(keys.UP):
            selection_change = -1
        
        if selection_change != 0:
            # SON SUPPRIMÉ
            # try:
            #     sounds.move.play()
            # except Exception:
            #     pass
            pause_selection = PauseState((pause_selection.value + selection_change) % 3)
        
        if key_just_pressed(keys.SPACE):
            if pause_selection == PauseState.RESUME:
                state = State.PLAY
            elif pause_selection == PauseState.RESTART:
                p1_controls = game.teams[0].controls
                p2_controls = game.teams[1].controls
                state = State.PLAY
                game = Game(p1_controls, p2_controls, 0)
            elif pause_selection == PauseState.QUIT:
                state = State.MENU
                menu_state = MenuState.NUM_PLAYERS
                game = Game()
        
        if key_just_pressed(keys.ESCAPE):
            state = State.PLAY
            pause_selection = PauseState.RESUME

def draw():
    game.draw()

    if state == State.LANGUAGE:
        image = "lang" + str(selected_language)
        screen.blit(image, (0, 0))

    elif state == State.MENU:
        image = "menu0" + str(menu_num_players)
        screen.blit(image, (0, 0))

    elif state == State.PAUSE:
        image = "pause" + str(pause_selection.value)
        screen.blit(image, (0, 0))

# Setup sonore SUPPRIMÉ
# try:
#     pygame.mixer.quit()
#     pygame.mixer.init(44100, -16, 2, 1024)
# except Exception:
#     pass

# Set the initial game state
state = State.LANGUAGE
menu_state = MenuState.LANGUAGE
menu_num_players = 1
selected_language = 0
pause_selection = PauseState.RESUME

game = Game()

pgzrun.go()