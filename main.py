import pygame
from fighter import Fighter
from pygame import mixer

pygame.init()
mixer.init()

screen_width = 1000
screen_height = 600

screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Brawler")

#set framerate
clock = pygame.time.Clock()
fps = 60

#define colors
red = (255, 0, 0)
yellow = (255, 255, 0)
white = (255, 255, 255)
black = (0, 0, 0)
green = (0, 180, 0)

#define game variables
in_main_menu = True
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

#define fighter variables
#warrior
warrior_size = 162
warrior_scale = 4
warrior_offset = [72, 56]
warrior_data = [warrior_size, warrior_scale, warrior_offset]

#wizard
wizard_size = 250
wizard_scale = 3
wizard_offset = [112, 107]
wizard_data = [wizard_size, wizard_scale, wizard_offset]

#load music and sounds
pygame.mixer.music.load("assests/audio/bg_music.mp3")
pygame.mixer.music.set_volume(0.5)
pygame.mixer.music.play(-1, 0.0, 5000)
warrior_attack_fx = pygame.mixer.Sound("assests/audio/warrior_attack.wav")
warrior_attack_fx.set_volume(0.5)
wizard_attack_fx = pygame.mixer.Sound("assests/audio/wizard_attack.wav")
wizard_attack_fx.set_volume(0.5)
die_fx = pygame.mixer.Sound("assests/audio/die.wav")
die_fx.set_volume(0.6)
victory_fx = pygame.mixer.Sound("assests/audio/victory.wav")
victory_fx.set_volume(0.6)

#load background image
bg_image = pygame.image.load("assests/images/background/background.jpg").convert_alpha()

#load victory image
victory_img = pygame.image.load("assests/images/icons/victory.png").convert_alpha()

#load spritesheets
warrior_sheet = pygame.image.load("assests/images/warrior/Sprites/warrior.png").convert_alpha()
wizard_sheet = pygame.image.load("assests/images/wizard/Sprites/wizard.png").convert_alpha()

#define number of steps in each animation
warrior_animation_steps = [10, 8, 1, 7, 7, 3, 7]
wizard_animation_steps = [8, 8, 1, 8, 8, 3, 7]

#define fonts
count_font = pygame.font.SysFont("arial,freesansbold,dejavusans", 80, bold=True)
score_font = pygame.font.SysFont("arial,freesansbold,dejavusans", 30, bold=False)

#function for drawing text
def draw_text(text, font, text_color, x, y):
    img = font.render(text, True, text_color)
    screen.blit(img, (x, y))

#function for drawing background
def draw_bg():
    scaled_bg = pygame.transform.scale(bg_image, (screen_width, screen_height))
    screen.blit(scaled_bg, (0,0))

#function for drawing fighther health bars
def draw_health_bar(health, x, y):
    ratio = health/ 100
    pygame.draw.rect(screen, white, (x-2, y-2, 404, 34))
    pygame.draw.rect(screen, red, (x, y, 400, 30))
    pygame.draw.rect(screen, yellow, (x, y, 400 * ratio, 30)) #x,y,width, height


#create two instances of fighters
fighter_1 = Fighter(1, 120, 310, False, warrior_data, warrior_sheet, warrior_animation_steps, warrior_attack_fx, die_fx)
fighter_2 = Fighter(2, 760, 310, True, wizard_data, wizard_sheet, wizard_animation_steps, wizard_attack_fx, die_fx)

#main menu buttons
start_button_rect = pygame.Rect(380, 240, 240, 65)
exit_button_rect = pygame.Rect(380, 330, 240, 65)

#match over buttons
rematch_button_rect = pygame.Rect(295, 315, 195, 45)
main_menu_button_rect = pygame.Rect(510, 315, 195, 45)


#game loop
run = True
while run:

    clock.tick(fps)
    
    #draw background
    draw_bg()

    if in_main_menu:
        draw_text("BRAWLER", count_font, yellow, 310, 110)
        pygame.draw.rect(screen, white, (start_button_rect.x - 2, start_button_rect.y - 2, start_button_rect.width + 4, start_button_rect.height + 4))
        pygame.draw.rect(screen, green, start_button_rect)
        draw_text("START", score_font, white, start_button_rect.x + 72, start_button_rect.y + 15)

        pygame.draw.rect(screen, white, (exit_button_rect.x - 2, exit_button_rect.y - 2, exit_button_rect.width + 4, exit_button_rect.height + 4))
        pygame.draw.rect(screen, red, exit_button_rect)
        draw_text("EXIT", score_font, white, exit_button_rect.x + 88, exit_button_rect.y + 15)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if start_button_rect.collidepoint(event.pos):
                    in_main_menu = False
                    round_start_time = pygame.time.get_ticks()
                    intro_count = 3
                    last_count_update = pygame.time.get_ticks()
                    score = [0, 0]
                    current_round = 1
                    round_over = False
                    match_over = False
                    fighter_1 = Fighter(1, 120, 310, False, warrior_data, warrior_sheet, warrior_animation_steps, warrior_attack_fx, die_fx)
                    fighter_2 = Fighter(2, 760, 310, True, wizard_data, wizard_sheet, wizard_animation_steps, wizard_attack_fx, die_fx)
                elif exit_button_rect.collidepoint(event.pos):
                    run = False

        pygame.display.update()
        continue
    
    #show player stats
    draw_health_bar(fighter_1.health, 20, 20)
    draw_health_bar(fighter_2.health, 580, 20)
    draw_text("P1-Warrior Rounds won: " + str(score[0]), score_font, red, 20, 60 )
    draw_text("P2-Wizard Rounds won: " + str(score[1]), score_font, red, 580, 60 )
    
    #update coountdown
    if pygame.time.get_ticks() - round_start_time < round_banner_duration:
        round_text = "ROUND " + str(current_round)
        round_img = count_font.render(round_text, True, red)
        screen.blit(round_img, ((screen_width - round_img.get_width()) // 2, screen_height / 3))
        last_count_update = pygame.time.get_ticks()
    elif intro_count <= 0:
        # move fighters
        fighter_1.move(screen_width, screen_height, screen, fighter_2, round_over or match_over)
        fighter_2.move(screen_width, screen_height, screen, fighter_1, round_over or match_over)
    else:
        # display count timer
        draw_text(str(intro_count), count_font, red, screen_width/2, screen_height/3)
        # update count timer
        if(pygame.time.get_ticks() - last_count_update) >= 1000:
            intro_count -= 1
            last_count_update = pygame.time.get_ticks()
    
    #update fighters
    if not match_over:
        fighter_1.update()
        fighter_2.update()
    
    #draw fighters
    fighter_1.draw(screen)
    fighter_2.draw(screen)
    
    #check for player defeat
    if match_over == False:
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
                fighter_1 = Fighter(1, 120, 310, False, warrior_data, warrior_sheet, warrior_animation_steps, warrior_attack_fx, die_fx)
                fighter_2 = Fighter(2, 760, 310, True, wizard_data, wizard_sheet, wizard_animation_steps, wizard_attack_fx, die_fx)
    else:
        #display victory image
        victory_x = (screen_width - victory_img.get_width()) // 2
        screen.blit(victory_img, (victory_x, 150))
        if score[0] > score[1]:
            winner_text = "Winner: P1-Warrior"
        elif score[1] > score[0]:
            winner_text = "Winner: P2-Wizard"
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
    
    #event handler
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False
        if match_over and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if rematch_button_rect.collidepoint(event.pos):
                round_over = False
                match_over = False
                intro_count = 3
                round_start_time = pygame.time.get_ticks()
                last_count_update = pygame.time.get_ticks()
                score = [0, 0]
                current_round = 1
                fighter_1 = Fighter(1, 120, 310, False, warrior_data, warrior_sheet, warrior_animation_steps, warrior_attack_fx, die_fx)
                fighter_2 = Fighter(2, 760, 310, True, wizard_data, wizard_sheet, wizard_animation_steps, wizard_attack_fx, die_fx)
            elif main_menu_button_rect.collidepoint(event.pos):
                round_over = False
                match_over = False
                in_main_menu = True
                intro_count = 3
                round_start_time = pygame.time.get_ticks()
                last_count_update = pygame.time.get_ticks()
                score = [0, 0]
                current_round = 1
                fighter_1 = Fighter(1, 120, 310, False, warrior_data, warrior_sheet, warrior_animation_steps, warrior_attack_fx, die_fx)
                fighter_2 = Fighter(2, 760, 310, True, wizard_data, wizard_sheet, wizard_animation_steps, wizard_attack_fx, die_fx)
    
    #update display
    pygame.display.update()
    

#exit game
pygame.quit()