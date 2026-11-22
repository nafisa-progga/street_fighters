import json
import os
import random
import socket
import sys
import threading
import time
import pygame
from fighter import Fighter
from pygame import mixer


def get_base_dir():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.abspath(".")


def get_writable_dir():
    """Directory next to the executable (or current working folder when run via Python)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(".")


def load_env_file():
    env_path = os.path.join(get_base_dir(), ".env")
    if not os.path.exists(env_path):
        env_path = os.path.join(get_writable_dir(), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


load_env_file()

SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5555"))
PROFILE_FILE = os.path.join(get_writable_dir(), "Brawler_profile.json")
RECONNECT_GRACE_SECONDS = 180.0


def load_local_profile():
    if not os.path.exists(PROFILE_FILE):
        return {"code": "", "name": "Player"}
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {
                "code": (data.get("code") or "").strip().upper(),
                "name": ((data.get("name") or "Player").strip()[:16]) or "Player",
            }
    except (OSError, json.JSONDecodeError):
        pass
    return {"code": "", "name": "Player"}


def save_local_profile(code, name):
    try:
        with open(PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "code": (code or "").strip().upper(),
                    "name": ((name or "Player").strip()[:16]) or "Player",
                },
                f,
                indent=2,
            )
    except OSError:
        pass


def resource_path(relative_path):
    return os.path.join(get_base_dir(), relative_path)


class OnlineClient:
    """Background TCP client handling friend codes, online/offline status, invites, and match sync."""

    def __init__(self, host=SERVER_HOST, port=SERVER_PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        self.lock = threading.Lock()

        saved_profile = load_local_profile()
        self.my_code = saved_profile["code"]
        self.my_name = saved_profile["name"]
        self.friends = []
        self.incoming_invites = []
        self.status_message = ""
        self.pending_match_start = None
        self.pending_match_rejoin = None
        self.remote_input = {}
        self.opponent_disconnected = False
        self.opponent_disc_name = ""
        self.opponent_disc_deadline = 0.0
        self.opponent_reconnected_banner = ""
        self.opponent_reconnected_until = 0.0
        self.opponent_timeout_reason = None

    def connect(self, player_name):
        with self.lock:
            self.my_name = (player_name or self.my_name or "Player").strip()[:16] or "Player"
            current_code = self.my_code
            current_name = self.my_name
        save_local_profile(current_code, current_name)

        if self.connected:
            self.send({"type": "set_name", "name": current_name})
            with self.lock:
                self.status_message = f"Name set to '{current_name}'."
            return True
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4.0)
            s.connect((self.host, self.port))
            s.settimeout(None)
            self.sock = s
            self.connected = True
            with self.lock:
                self.status_message = "Connected; registering..."

            t = threading.Thread(target=self._listen_loop, daemon=True)
            t.start()
            self.send({"type": "register", "name": current_name, "code": current_code})
            return True
        except OSError as exc:
            with self.lock:
                self.connected = False
                self.status_message = f"Could not reach {self.host}:{self.port} ({exc})"
            return False

    def send(self, payload):
        if not self.connected or not self.sock:
            return
        try:
            raw = (json.dumps(payload) + "\n").encode("utf-8")
            self.sock.sendall(raw)
        except OSError as exc:
            with self.lock:
                self.connected = False
                self.status_message = f"Send failed / disconnected: {exc}"

    def _listen_loop(self):
        buf = ""
        disconnect_reason = "Server closed connection."
        try:
            while self.connected and self.sock:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    mtype = msg.get("type")

                    code_to_save = None
                    name_to_save = None
                    with self.lock:
                        if mtype == "registered":
                            self.my_code = (msg.get("code") or self.my_code).strip().upper()
                            self.my_name = (msg.get("name") or self.my_name).strip()[:16] or "Player"
                            self.status_message = f"Online as {self.my_name} ({self.my_code})"
                            code_to_save = self.my_code
                            name_to_save = self.my_name
                        elif mtype == "name_updated":
                            self.my_name = (msg.get("name") or self.my_name).strip()[:16] or "Player"
                            self.status_message = f"Name updated to {self.my_name}"
                            code_to_save = self.my_code
                            name_to_save = self.my_name
                        elif mtype == "friends_list":
                            self.friends = msg.get("friends", [])
                        elif mtype == "invite_received":
                            inv = msg.get("invite")
                            if inv and all(x.get("from_code") != inv.get("from_code") for x in self.incoming_invites):
                                self.incoming_invites.append(inv)
                                self.status_message = f"Match invite from {inv.get('from_name')}!"
                        elif mtype == "status_msg":
                            self.status_message = msg.get("text", "")
                        elif mtype == "match_start":
                            self.pending_match_start = msg
                            self.opponent_disconnected = False
                            self.opponent_disc_name = ""
                            self.opponent_disc_deadline = 0.0
                            self.opponent_timeout_reason = None
                            self.remote_input = {}
                        elif mtype == "match_rejoined":
                            self.pending_match_rejoin = msg
                            self.opponent_timeout_reason = None
                            self.remote_input = {}
                        elif mtype == "relay":
                            self.remote_input = msg.get("data", {})
                        elif mtype == "opponent_temp_disconnected":
                            rem = float(msg.get("remaining_seconds", RECONNECT_GRACE_SECONDS))
                            self.opponent_disconnected = True
                            self.opponent_disc_name = msg.get("name") or "Opponent"
                            self.opponent_disc_deadline = time.time() + max(0.0, rem)
                        elif mtype == "opponent_reconnected":
                            r_name = msg.get("name") or self.opponent_disc_name or "Opponent"
                            self.opponent_disconnected = False
                            self.opponent_disc_name = ""
                            self.opponent_disc_deadline = 0.0
                            self.opponent_reconnected_banner = f"{r_name} reconnected! Resuming match..."
                            self.opponent_reconnected_until = time.time() + 3.0
                        elif mtype == "opponent_reconnect_timeout":
                            self.opponent_disconnected = False
                            self.opponent_disc_name = ""
                            self.opponent_disc_deadline = 0.0
                            self.opponent_timeout_reason = msg.get("text") or "Opponent did not reconnect within 3 minutes."

                    if code_to_save or name_to_save:
                        save_local_profile(code_to_save or "", name_to_save or "Player")
        except OSError as exc:
            disconnect_reason = f"Connection lost: {exc}"
        finally:
            try:
                if self.sock:
                    self.sock.close()
            except OSError:
                pass
            with self.lock:
                self.sock = None
                self.connected = False
                self.status_message = disconnect_reason
                for f in self.friends:
                    f["online"] = False


class ActionKeyMap:
    """Key-like mapping for bot or remote player actions."""

    def __init__(self, active_actions):
        self.active = set(active_actions or [])

    def __getitem__(self, key_code):
        if key_code in (pygame.K_a, pygame.K_LEFT):
            return "left" in self.active
        if key_code in (pygame.K_d, pygame.K_RIGHT):
            return "right" in self.active
        if key_code in (pygame.K_w, pygame.K_UP):
            return "jump" in self.active
        if key_code in (pygame.K_e, pygame.K_DOWN):
            return "atk1" in self.active
        if key_code in (pygame.K_q, pygame.K_RCTRL):
            return "atk2" in self.active
        return False


pygame.init()
mixer.init()

screen_width = 1000
screen_height = 600

screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Brawler")

# set framerate
clock = pygame.time.Clock()
fps = 60

# define colors
red = (255, 0, 0)
yellow = (255, 255, 0)
white = (255, 255, 255)
black = (0, 0, 0)
green = (0, 180, 0)
cyan = (80, 210, 255)
dark_panel = (18, 22, 34)
gray = (150, 160, 180)

# define game variables
screen_mode = "MAIN_MENU"  # MAIN_MENU, ONLINE_LOBBY, INSTRUCTIONS, BATTLE
match_type = "LOCAL_2P"  # LOCAL_2P, LOCAL_BOT, ONLINE
my_online_slot = 1  # 1 or 2 when match_type == "ONLINE"

p1_display_name = "Player 1"
p2_display_name = "Player 2"
p1_char_key = "warrior"
p2_char_key = "wizard"

round_banner_duration = 1000
round_start_time = pygame.time.get_ticks()
intro_count = 3
last_count_update = pygame.time.get_ticks()
score = [0, 0] # player scores [p1, p2] (no of rounds won)
max_rounds = 3
current_round = 1
round_over = False
round_over_cooldown = 2000
match_over = False

# define fighter variables
# warrior
warrior_size = 162
warrior_scale = 4
warrior_offset = [72, 56]
warrior_data = [warrior_size, warrior_scale, warrior_offset]

# wizard
wizard_size = 250
wizard_scale = 3
wizard_offset = [112, 107]
wizard_data = [wizard_size, wizard_scale, wizard_offset]

# load music and sounds
pygame.mixer.music.load(resource_path("assests/audio/bg_music.mp3"))
pygame.mixer.music.set_volume(0.5)
pygame.mixer.music.play(-1, 0.0, 5000)
warrior_attack_fx = pygame.mixer.Sound(resource_path("assests/audio/warrior_attack.wav"))
warrior_attack_fx.set_volume(0.5)
wizard_attack_fx = pygame.mixer.Sound(resource_path("assests/audio/wizard_attack.wav"))
wizard_attack_fx.set_volume(0.5)
die_fx = pygame.mixer.Sound(resource_path("assests/audio/die.wav"))
die_fx.set_volume(0.6)
victory_fx = pygame.mixer.Sound(resource_path("assests/audio/victory.wav"))
victory_fx.set_volume(0.6)

# load background image
bg_image = pygame.image.load(resource_path("assests/images/background/background.jpg")).convert_alpha()

# load victory image
victory_img = pygame.image.load(resource_path("assests/images/icons/victory.png")).convert_alpha()

# load spritesheets
warrior_sheet = pygame.image.load(resource_path("assests/images/warrior/Sprites/warrior.png")).convert_alpha()
wizard_sheet = pygame.image.load(resource_path("assests/images/wizard/Sprites/wizard.png")).convert_alpha()

# define number of steps in each animation
warrior_animation_steps = [10, 8, 1, 7, 7, 3, 7]
wizard_animation_steps = [8, 8, 1, 8, 8, 3, 7]

CHARACTER_POOL = {
    "warrior": {
        "label": "Warrior",
        "data": warrior_data,
        "sheet": warrior_sheet,
        "steps": warrior_animation_steps,
        "fx": warrior_attack_fx,
    },
    "wizard": {
        "label": "Wizard",
        "data": wizard_data,
        "sheet": wizard_sheet,
        "steps": wizard_animation_steps,
        "fx": wizard_attack_fx,
    },
}

# define fonts
count_font = pygame.font.SysFont("arial,freesansbold,dejavusans", 80, bold=True)
score_font = pygame.font.SysFont("arial,freesansbold,dejavusans", 30, bold=False)
ui_font = pygame.font.SysFont("arial,freesansbold,dejavusans", 22, bold=True)
small_font = pygame.font.SysFont("arial,freesansbold,dejavusans", 18, bold=False)

INSTRUCTION_LINES = [
    ("MODES", yellow),
    ("• LOCAL 2P: Two players fight on one keyboard (Best of 3 rounds).", white),
    ("• LOCAL 1P (BOT): Fight solo against the Wizard Bot.", white),
    ("• ONLINE: Invite a friend over network; Warrior & Wizard are randomly assigned.", white),
    ("CONTROLS", yellow),
    ("• Player 1 (Left / Online Slot 1): A/D Move, W Jump, E & Q Attack.", white),
    ("• Player 2 (Right / Online Slot 2): Left/Right Move, Up Jump, Down & Right Ctrl Attack.", white),
    ("ONLINE & USERNAME SAVE", yellow),
    ("• Type your name and click SAVE / JOIN (or Enter) — saved in Brawler_profile.json.", cyan),
    ("• Share your BR-XXXX code, add your friend's code, then click INVITE / ACCEPT.", white),
]


def draw_text(text, font, text_color, x, y):
    img = font.render(text, True, text_color)
    screen.blit(img, (x, y))


def draw_text_box(box_rect, text, font, is_active, placeholder=""):
    pygame.draw.rect(screen, (10, 13, 22), box_rect)
    pygame.draw.rect(screen, yellow if is_active else white, box_rect, 2)

    text_x = box_rect.x + 10
    text_y = box_rect.y + 8
    if text:
        img = font.render(text, True, white)
        screen.blit(img, (text_x, text_y))
        cursor_x = text_x + img.get_width() + 2
    else:
        if placeholder:
            ph_img = font.render(placeholder, True, gray)
            screen.blit(ph_img, (text_x, text_y))
        cursor_x = text_x

    if is_active and (pygame.time.get_ticks() // 500) % 2 == 0:
        cursor_top = box_rect.y + 7
        cursor_bottom = box_rect.y + box_rect.height - 7
        pygame.draw.line(screen, yellow, (cursor_x, cursor_top), (cursor_x, cursor_bottom), 2)


def draw_bg():
    scaled_bg = pygame.transform.scale(bg_image, (screen_width, screen_height))
    screen.blit(scaled_bg, (0, 0))


def draw_health_bar(health, x, y):
    ratio = health / 100
    pygame.draw.rect(screen, white, (x - 2, y - 2, 404, 34))
    pygame.draw.rect(screen, red, (x, y, 400, 30))
    pygame.draw.rect(screen, yellow, (x, y, 400 * ratio, 30)) #x,y,width, height


def create_fighter_pair(c1_key, c2_key, name1, name2):
    c1 = CHARACTER_POOL[c1_key]
    c2 = CHARACTER_POOL[c2_key]
    f1 = Fighter(1, 120, 310, False, c1["data"], c1["sheet"], c1["steps"], c1["fx"], die_fx, char_name=c1["label"], player_name=name1)
    f2 = Fighter(2, 760, 310, True, c2["data"], c2["sheet"], c2["steps"], c2["fx"], die_fx, char_name=c2["label"], player_name=name2)
    return f1, f2


def randomize_characters_for_match():
    return random.choice([
        ("warrior", "wizard"),
        ("wizard", "warrior"),
    ])


def compute_wizard_bot_actions(bot_fighter, target_fighter):
    actions = []
    if not bot_fighter.alive or not target_fighter.alive:
        return actions

    dx = target_fighter.rect.centerx - bot_fighter.rect.centerx
    dy = target_fighter.rect.centery - bot_fighter.rect.centery
    dist = abs(dx)
    attack_reach = 150

    if dist > attack_reach:
        actions.append("right" if dx > 0 else "left")
    elif dist < 75 and random.random() < 0.15:
        actions.append("left" if dx > 0 else "right")

    if dy < -60 and not bot_fighter.jump and random.random() < 0.04:
        actions.append("jump")

    if dist <= attack_reach + 15 and abs(dy) < 90 and bot_fighter.attack_cooldown == 0 and random.random() < 0.14:
        actions.append("atk1" if random.random() < 0.65 else "atk2")

    return actions


def collect_local_online_actions(slot):
    keys = pygame.key.get_pressed()
    actions = []
    if slot == 1:
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            actions.append("left")
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            actions.append("right")
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            actions.append("jump")
        if keys[pygame.K_e] or keys[pygame.K_DOWN]:
            actions.append("atk1")
        if keys[pygame.K_q] or keys[pygame.K_RCTRL]:
            actions.append("atk2")
    else:
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            actions.append("left")
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            actions.append("right")
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            actions.append("jump")
        if keys[pygame.K_DOWN] or keys[pygame.K_e]:
            actions.append("atk1")
        if keys[pygame.K_RCTRL] or keys[pygame.K_q]:
            actions.append("atk2")
    return actions


def begin_match(c1_key, c2_key, name1, name2, mode="LOCAL_2P", slot=1):
    global screen_mode, match_type, my_online_slot, p1_char_key, p2_char_key, p1_display_name, p2_display_name
    global round_start_time, intro_count, last_count_update, score, current_round, round_over, match_over
    global fighter_1, fighter_2

    match_type = mode
    my_online_slot = slot
    p1_char_key = c1_key
    p2_char_key = c2_key
    p1_display_name = name1
    p2_display_name = name2

    screen_mode = "BATTLE"
    round_start_time = pygame.time.get_ticks()
    intro_count = 3
    last_count_update = pygame.time.get_ticks()
    score = [0, 0]
    current_round = 1
    round_over = False
    match_over = False
    fighter_1, fighter_2 = create_fighter_pair(p1_char_key, p2_char_key, p1_display_name, p2_display_name)


def return_to_main_menu(send_online_leave=True):
    global match_type, round_over, match_over, screen_mode, intro_count
    global round_start_time, last_count_update, score, current_round, fighter_1, fighter_2

    if match_type == "ONLINE" and send_online_leave:
        net.send({"type": "leave_match"})
    with net.lock:
        net.opponent_disconnected = False
        net.opponent_disc_name = ""
        net.opponent_disc_deadline = 0.0
        net.opponent_reconnected_banner = ""
        net.opponent_reconnected_until = 0.0

    match_type = "LOCAL_2P"
    round_over = False
    match_over = False
    screen_mode = "MAIN_MENU"
    intro_count = 3
    round_start_time = pygame.time.get_ticks()
    last_count_update = pygame.time.get_ticks()
    score = [0, 0]
    current_round = 1
    fighter_1, fighter_2 = create_fighter_pair("warrior", "wizard", "Player 1", "Player 2")


# initial fighters (Warrior left, Wizard right)
fighter_1, fighter_2 = create_fighter_pair(p1_char_key, p2_char_key, p1_display_name, p2_display_name)

# online client
net = OnlineClient(SERVER_HOST, SERVER_PORT)
name_input = net.my_name
friend_code_input = ""
active_field = "name"  # "name" or "friend_code"

# main menu buttons
local_2p_button_rect = pygame.Rect(360, 165, 280, 50)
local_bot_button_rect = pygame.Rect(360, 223, 280, 50)
online_button_rect = pygame.Rect(360, 281, 280, 50)
instructions_button_rect = pygame.Rect(360, 339, 280, 50)
exit_button_rect = pygame.Rect(360, 397, 280, 50)

# lobby rects
name_box_rect = pygame.Rect(60, 120, 260, 40)
connect_btn_rect = pygame.Rect(335, 120, 150, 40)
friend_box_rect = pygame.Rect(60, 250, 260, 40)
add_friend_btn_rect = pygame.Rect(335, 250, 150, 40)
back_lobby_btn_rect = pygame.Rect(60, 525, 170, 45)
back_instructions_btn_rect = pygame.Rect(60, 525, 170, 45)

# in-battle quit button (top-center gap between health bars so it doesn't block view)
battle_quit_button_rect = pygame.Rect(455, 16, 90, 30)

# match over buttons
rematch_button_rect = pygame.Rect(295, 315, 195, 45)
main_menu_button_rect = pygame.Rect(510, 315, 195, 45)


# game loop
run = True
while run:

    clock.tick(fps)

    # draw background
    draw_bg()

    # check online match lifecycle events
    now_wall = time.time()
    with net.lock:
        started_msg = net.pending_match_start
        if started_msg:
            net.pending_match_start = None
        rejoined_msg = net.pending_match_rejoin
        if rejoined_msg:
            net.pending_match_rejoin = None

        opp_disc = net.opponent_disconnected
        opp_disc_name = net.opponent_disc_name
        opp_disc_rem = max(0, int(net.opponent_disc_deadline - now_wall)) if opp_disc else 0

        reconn_banner = ""
        if net.opponent_reconnected_banner and now_wall <= net.opponent_reconnected_until:
            reconn_banner = net.opponent_reconnected_banner
        elif net.opponent_reconnected_banner and now_wall > net.opponent_reconnected_until:
            net.opponent_reconnected_banner = ""

        timeout_reason = net.opponent_timeout_reason
        if timeout_reason:
            net.opponent_timeout_reason = None

    if started_msg:
        begin_match(
            started_msg.get("p1_char", "warrior"),
            started_msg.get("p2_char", "wizard"),
            started_msg.get("p1_name", "Player 1"),
            started_msg.get("p2_name", "Player 2"),
            mode="ONLINE",
            slot=started_msg.get("your_slot", 1),
        )

    if rejoined_msg:
        my_online_slot = rejoined_msg.get("your_slot", my_online_slot)
        p1_char_key = rejoined_msg.get("p1_char", p1_char_key)
        p2_char_key = rejoined_msg.get("p2_char", p2_char_key)
        p1_display_name = rejoined_msg.get("p1_name", p1_display_name)
        p2_display_name = rejoined_msg.get("p2_name", p2_display_name)
        fighter_1.player_name = p1_display_name
        fighter_2.player_name = p2_display_name
        match_type = "ONLINE"
        screen_mode = "BATTLE"

    if timeout_reason:
        with net.lock:
            net.status_message = timeout_reason
        if screen_mode == "BATTLE" and match_type == "ONLINE":
            return_to_main_menu(send_online_leave=False)

    if screen_mode == "MAIN_MENU":
        draw_text("BRAWLER", count_font, yellow, 310, 65)

        pygame.draw.rect(screen, white, (local_2p_button_rect.x - 2, local_2p_button_rect.y - 2, local_2p_button_rect.width + 4, local_2p_button_rect.height + 4))
        pygame.draw.rect(screen, green, local_2p_button_rect)
        draw_text("LOCAL 2P", score_font, white, local_2p_button_rect.x + 68, local_2p_button_rect.y + 8)

        pygame.draw.rect(screen, white, (local_bot_button_rect.x - 2, local_bot_button_rect.y - 2, local_bot_button_rect.width + 4, local_bot_button_rect.height + 4))
        pygame.draw.rect(screen, (200, 130, 20), local_bot_button_rect)
        draw_text("LOCAL 1P (BOT)", score_font, white, local_bot_button_rect.x + 30, local_bot_button_rect.y + 8)

        pygame.draw.rect(screen, white, (online_button_rect.x - 2, online_button_rect.y - 2, online_button_rect.width + 4, online_button_rect.height + 4))
        pygame.draw.rect(screen, (30, 110, 190), online_button_rect)
        draw_text("ONLINE", score_font, white, online_button_rect.x + 88, online_button_rect.y + 8)

        pygame.draw.rect(screen, white, (instructions_button_rect.x - 2, instructions_button_rect.y - 2, instructions_button_rect.width + 4, instructions_button_rect.height + 4))
        pygame.draw.rect(screen, (90, 60, 170), instructions_button_rect)
        draw_text("INSTRUCTIONS", ui_font, white, instructions_button_rect.x + 62, instructions_button_rect.y + 12)

        pygame.draw.rect(screen, white, (exit_button_rect.x - 2, exit_button_rect.y - 2, exit_button_rect.width + 4, exit_button_rect.height + 4))
        pygame.draw.rect(screen, red, exit_button_rect)
        draw_text("EXIT", score_font, white, exit_button_rect.x + 108, exit_button_rect.y + 8)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if local_2p_button_rect.collidepoint(event.pos):
                    begin_match("warrior", "wizard", "Player 1", "Player 2", mode="LOCAL_2P", slot=1)
                elif local_bot_button_rect.collidepoint(event.pos):
                    p_name = name_input.strip() or "Player 1"
                    begin_match("warrior", "wizard", p_name, "Wizard Bot", mode="LOCAL_BOT", slot=1)
                elif online_button_rect.collidepoint(event.pos):
                    screen_mode = "ONLINE_LOBBY"
                    net.connect(name_input)
                elif instructions_button_rect.collidepoint(event.pos):
                    screen_mode = "INSTRUCTIONS"
                elif exit_button_rect.collidepoint(event.pos):
                    run = False

        pygame.display.update()
        continue

    if screen_mode == "INSTRUCTIONS":
        panel = pygame.Surface((screen_width - 80, screen_height - 80), pygame.SRCALPHA)
        panel.fill((*dark_panel, 230))
        screen.blit(panel, (40, 40))
        pygame.draw.rect(screen, yellow, (40, 40, screen_width - 80, screen_height - 80), 2)

        draw_text("INSTRUCTIONS", score_font, yellow, 60, 60)

        iy = 105
        for line_txt, line_col in INSTRUCTION_LINES:
            is_header = line_txt in ("MODES", "CONTROLS", "ONLINE & USERNAME SAVE")
            font_to_use = ui_font if is_header else small_font
            draw_text(line_txt, font_to_use, line_col, 60, iy)
            iy += 32 if is_header else 34

        pygame.draw.rect(screen, red, back_instructions_btn_rect)
        draw_text("BACK", small_font, white, back_instructions_btn_rect.x + 62, back_instructions_btn_rect.y + 12)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if back_instructions_btn_rect.collidepoint(event.pos):
                    screen_mode = "MAIN_MENU"

        pygame.display.update()
        continue

    if screen_mode == "ONLINE_LOBBY":
        panel = pygame.Surface((screen_width - 80, screen_height - 80), pygame.SRCALPHA)
        panel.fill((*dark_panel, 225))
        screen.blit(panel, (40, 40))
        pygame.draw.rect(screen, yellow, (40, 40, screen_width - 80, screen_height - 80), 2)

        draw_text("ONLINE FRIENDS & INVITES", score_font, yellow, 60, 62)

        with net.lock:
            is_conn = net.connected
            my_code = net.my_code
            friends_snapshot = list(net.friends)
            invites_snapshot = list(net.incoming_invites)
            status_txt = net.status_message

        status_col = green if is_conn else red
        draw_text(f"Status: {'ONLINE' if is_conn else 'OFFLINE'}", ui_font, status_col, 530, 72)
        if my_code:
            draw_text(f"Your Friend Code: {my_code}", ui_font, cyan, 530, 105)

        # Your Name input
        draw_text("Your Name:", small_font, white, 60, 96)
        draw_text_box(name_box_rect, name_input, ui_font, active_field == "name", placeholder="Player")

        pygame.draw.rect(screen, green, connect_btn_rect)
        draw_text("SAVE / JOIN", small_font, white, connect_btn_rect.x + 22, connect_btn_rect.y + 10)

        # Add Friend by Code input
        draw_text("Add Friend by Code (e.g. BR-1234AB):", small_font, white, 60, 226)
        draw_text_box(friend_box_rect, friend_code_input, ui_font, active_field == "friend_code", placeholder="BR-1234AB")

        pygame.draw.rect(screen, (30, 110, 190), add_friend_btn_rect)
        draw_text("ADD FRIEND", small_font, white, add_friend_btn_rect.x + 24, add_friend_btn_rect.y + 10)

        # Friends list with Online/Offline status & Invite button
        draw_text("Friends List:", ui_font, yellow, 60, 315)
        invite_buttons = []
        if not friends_snapshot:
            draw_text("No friends added yet.", small_font, gray, 60, 350)
        else:
            for idx, f in enumerate(friends_snapshot[:4]):
                fy = 348 + idx * 42
                online_flag = f.get("online", False)
                state_label = "ONLINE" if online_flag else "OFFLINE"
                state_color = green if online_flag else red
                line = f"{f.get('name')} [{f.get('code')}] - {state_label}"
                draw_text(line, small_font, white, 60, fy + 8)
                pygame.draw.circle(screen, state_color, (375, fy + 17), 6)

                if online_flag and not f.get("in_match", False):
                    inv_rect = pygame.Rect(400, fy + 2, 100, 30)
                    pygame.draw.rect(screen, green, inv_rect)
                    draw_text("INVITE", small_font, white, inv_rect.x + 22, inv_rect.y + 5)
                    invite_buttons.append((inv_rect, f.get("code")))

        # Incoming Match Invites
        draw_text("Incoming Invites:", ui_font, yellow, 530, 200)
        accept_buttons = []
        decline_buttons = []
        if not invites_snapshot:
            draw_text("No pending invites.", small_font, gray, 530, 235)
        else:
            for idx, inv in enumerate(invites_snapshot[:4]):
                iy = 235 + idx * 46
                draw_text(f"{inv.get('from_name')} ({inv.get('from_code')})", small_font, white, 530, iy + 8)
                acc_rect = pygame.Rect(775, iy + 3, 82, 30)
                dec_rect = pygame.Rect(864, iy + 3, 76, 30)
                pygame.draw.rect(screen, green, acc_rect)
                pygame.draw.rect(screen, red, dec_rect)
                draw_text("ACCEPT", small_font, white, acc_rect.x + 11, acc_rect.y + 5)
                draw_text("DECLINE", small_font, white, dec_rect.x + 8, dec_rect.y + 5)
                accept_buttons.append((acc_rect, inv.get("from_code")))
                decline_buttons.append((dec_rect, inv.get("from_code")))

        if status_txt:
            draw_text(status_txt, small_font, yellow, 250, 536)

        pygame.draw.rect(screen, red, back_lobby_btn_rect)
        draw_text("BACK", small_font, white, back_lobby_btn_rect.x + 62, back_lobby_btn_rect.y + 12)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if name_box_rect.collidepoint(event.pos):
                    active_field = "name"
                elif friend_box_rect.collidepoint(event.pos):
                    active_field = "friend_code"
                elif connect_btn_rect.collidepoint(event.pos):
                    net.connect(name_input)
                elif add_friend_btn_rect.collidepoint(event.pos):
                    if not net.connected:
                        net.connect(name_input)
                    net.send({"type": "add_friend", "friend_code": friend_code_input.strip().upper()})
                    friend_code_input = ""
                elif back_lobby_btn_rect.collidepoint(event.pos):
                    screen_mode = "MAIN_MENU"
                else:
                    for rect, f_code in invite_buttons:
                        if rect.collidepoint(event.pos):
                            net.send({"type": "send_invite", "target_code": f_code})
                    for rect, from_code in accept_buttons:
                        if rect.collidepoint(event.pos):
                            net.send({"type": "respond_invite", "from_code": from_code, "accept": True})
                    for rect, from_code in decline_buttons:
                        if rect.collidepoint(event.pos):
                            net.send({"type": "respond_invite", "from_code": from_code, "accept": False})

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    if active_field == "name":
                        name_input = name_input[:-1]
                    else:
                        friend_code_input = friend_code_input[:-1]
                elif event.key == pygame.K_RETURN:
                    if active_field == "name":
                        net.connect(name_input)
                    elif active_field == "friend_code" and friend_code_input.strip():
                        if not net.connected:
                            net.connect(name_input)
                        net.send({"type": "add_friend", "friend_code": friend_code_input.strip().upper()})
                        friend_code_input = ""
                elif event.unicode and event.unicode.isprintable():
                    if active_field == "name" and len(name_input) < 16:
                        name_input += event.unicode
                    elif active_field == "friend_code" and len(friend_code_input) < 12:
                        friend_code_input += event.unicode.upper()

        pygame.display.update()
        continue

    # show player stats & character + player names
    draw_health_bar(fighter_1.health, 20, 20)
    draw_health_bar(fighter_2.health, 580, 20)
    draw_text(f"P1-{fighter_1.char_name} Rounds won: {score[0]}", score_font, red, 20, 60)
    draw_text(fighter_1.player_name, small_font, white, 20, 95)

    draw_text(f"P2-{fighter_2.char_name} Rounds won: {score[1]}", score_font, red, 580, 60)
    draw_text(fighter_2.player_name, small_font, white, 580, 95)

    # non-intrusive QUIT button in top-center gap between health bars
    pygame.draw.rect(screen, white, (battle_quit_button_rect.x - 1, battle_quit_button_rect.y - 1, battle_quit_button_rect.width + 2, battle_quit_button_rect.height + 2))
    pygame.draw.rect(screen, red, battle_quit_button_rect)
    draw_text("QUIT", small_font, white, battle_quit_button_rect.x + 23, battle_quit_button_rect.y + 5)

    is_online_paused = (match_type == "ONLINE" and opp_disc and not match_over)

    # update countdown / gameplay (paused while online opponent is temporarily disconnected)
    if is_online_paused:
        last_count_update = pygame.time.get_ticks()
    elif pygame.time.get_ticks() - round_start_time < round_banner_duration:
        round_text = "ROUND " + str(current_round)
        round_img = count_font.render(round_text, True, red)
        screen.blit(round_img, ((screen_width - round_img.get_width()) // 2, screen_height / 3))
        last_count_update = pygame.time.get_ticks()
    elif intro_count <= 0:
        if match_type == "LOCAL_2P":
            fighter_1.move(screen_width, screen_height, screen, fighter_2, round_over or match_over)
            fighter_2.move(screen_width, screen_height, screen, fighter_1, round_over or match_over)
        elif match_type == "LOCAL_BOT":
            fighter_1.move(screen_width, screen_height, screen, fighter_2, round_over or match_over)
            bot_actions = compute_wizard_bot_actions(fighter_2, fighter_1)
            fighter_2.move(screen_width, screen_height, screen, fighter_1, round_over or match_over, override_keys=ActionKeyMap(bot_actions))
        else:
            local_actions = collect_local_online_actions(my_online_slot)
            net.send({"type": "relay", "data": {"actions": local_actions}})
            with net.lock:
                remote_actions = net.remote_input.get("actions", [])

            if my_online_slot == 1:
                fighter_1.move(screen_width, screen_height, screen, fighter_2, round_over or match_over)
                fighter_2.move(screen_width, screen_height, screen, fighter_1, round_over or match_over, override_keys=ActionKeyMap(remote_actions))
            else:
                fighter_1.move(screen_width, screen_height, screen, fighter_2, round_over or match_over, override_keys=ActionKeyMap(remote_actions))
                fighter_2.move(screen_width, screen_height, screen, fighter_1, round_over or match_over)
    else:
        # display count timer
        draw_text(str(intro_count), count_font, red, screen_width / 2, screen_height / 3)
        # update count timer
        if (pygame.time.get_ticks() - last_count_update) >= 1000:
            intro_count -= 1
            last_count_update = pygame.time.get_ticks()

    # update fighters
    if not match_over and not is_online_paused:
        fighter_1.update()
        fighter_2.update()

    # draw fighters and player names below each character
    fighter_1.draw(screen)
    fighter_2.draw(screen)

    p1_name_tag = small_font.render(fighter_1.player_name, True, yellow)
    screen.blit(p1_name_tag, (fighter_1.rect.centerx - p1_name_tag.get_width() // 2, fighter_1.rect.bottom + 6))

    p2_name_tag = small_font.render(fighter_2.player_name, True, yellow)
    screen.blit(p2_name_tag, (fighter_2.rect.centerx - p2_name_tag.get_width() // 2, fighter_2.rect.bottom + 6))

    # show reconnect / disconnection notice if applicable
    if is_online_paused:
        mins = opp_disc_rem // 60
        secs = opp_disc_rem % 60
        disc_banner = pygame.Surface((660, 74), pygame.SRCALPHA)
        disc_banner.fill((*dark_panel, 220))
        bx = (screen_width - 660) // 2
        by = 120
        screen.blit(disc_banner, (bx, by))
        pygame.draw.rect(screen, yellow, (bx, by, 660, 74), 2)
        msg_line = f"{opp_disc_name} disconnected — waiting to reconnect ({mins}:{secs:02d} left)"
        m_img = small_font.render(msg_line, True, yellow)
        screen.blit(m_img, (bx + (660 - m_img.get_width()) // 2, by + 26))
    elif reconn_banner and not match_over:
        r_img = ui_font.render(reconn_banner, True, green)
        screen.blit(r_img, ((screen_width - r_img.get_width()) // 2, 125))

    # check for player defeat
    if match_over == False:
        if not is_online_paused:
            if round_over == False:
                if fighter_1.alive == False:
                    score[1] += 1 # if player1 dies, player2 gets score
                    round_over = True
                    round_over_time = pygame.time.get_ticks()
                    if current_round >= max_rounds:
                        match_over = True
                        if victory_fx:
                            victory_fx.play()
                        if score[0] > score[1]:
                            fighter_1.set_match_end_pose(1.3)
                            fighter_2.set_match_end_pose(0.75)
                        elif score[1] > score[0]:
                            fighter_2.set_match_end_pose(1.3)
                            fighter_1.set_match_end_pose(0.75)
                        else:
                            fighter_1.set_match_end_pose(1.0)
                            fighter_2.set_match_end_pose(1.0)
                elif fighter_2.alive == False:
                    score[0] += 1 # if player2 dies, player1 gets score
                    round_over = True
                    round_over_time = pygame.time.get_ticks()
                    if current_round >= max_rounds:
                        match_over = True
                        if victory_fx:
                            victory_fx.play()
                        if score[0] > score[1]:
                            fighter_1.set_match_end_pose(1.3)
                            fighter_2.set_match_end_pose(0.75)
                        elif score[1] > score[0]:
                            fighter_2.set_match_end_pose(1.3)
                            fighter_1.set_match_end_pose(0.75)
                        else:
                            fighter_1.set_match_end_pose(1.0)
                            fighter_2.set_match_end_pose(1.0)
            else:
                if pygame.time.get_ticks() - round_over_time > round_over_cooldown:
                    round_over = False
                    intro_count = 3
                    current_round += 1
                    round_start_time = pygame.time.get_ticks()
                    last_count_update = pygame.time.get_ticks()
                    fighter_1, fighter_2 = create_fighter_pair(p1_char_key, p2_char_key, p1_display_name, p2_display_name)
    else:
        # display victory image
        victory_x = (screen_width - victory_img.get_width()) // 2
        screen.blit(victory_img, (victory_x, 150))
        if score[0] > score[1]:
            winner_text = f"Winner: {fighter_1.player_name} ({fighter_1.char_name})"
        elif score[1] > score[0]:
            winner_text = f"Winner: {fighter_2.player_name} ({fighter_2.char_name})"
        else:
            winner_text = "Match Draw!"
        winner_img = score_font.render(winner_text, True, black)
        screen.blit(winner_img, ((screen_width - winner_img.get_width()) // 2, 260))

        pygame.draw.rect(screen, white, (rematch_button_rect.x - 2, rematch_button_rect.y - 2, rematch_button_rect.width + 4, rematch_button_rect.height + 4))
        pygame.draw.rect(screen, green, rematch_button_rect)
        draw_text("REMATCH", score_font, white, rematch_button_rect.x + 28, rematch_button_rect.y + 6)

        pygame.draw.rect(screen, white, (main_menu_button_rect.x - 2, main_menu_button_rect.y - 2, main_menu_button_rect.width + 4, main_menu_button_rect.height + 4))
        pygame.draw.rect(screen, red, main_menu_button_rect)
        draw_text("MAIN MENU", score_font, white, main_menu_button_rect.x + 14, main_menu_button_rect.y + 6)

    # event handler
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not match_over and battle_quit_button_rect.collidepoint(event.pos):
                return_to_main_menu(send_online_leave=True)
            elif match_over:
                if rematch_button_rect.collidepoint(event.pos):
                    if match_type == "ONLINE":
                        p1_char_key, p2_char_key = randomize_characters_for_match()
                    begin_match(p1_char_key, p2_char_key, p1_display_name, p2_display_name, mode=match_type, slot=my_online_slot)
                elif main_menu_button_rect.collidepoint(event.pos):
                    return_to_main_menu(send_online_leave=True)

    # update display
    pygame.display.update()


# exit game
pygame.quit()