import pygame
from fighter import Fighter


pygame.init()

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

#define game variables
intro_count = 3
last_count_update = pygame.time.get_ticks()
score = [0, 0] # player scores [p1, p2]
round_over = False
round_over_cooldown = 2000

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


#load background image
bg_image = pygame.image.load("assests/images/background/background.jpg").convert_alpha()

#load victory image
victory_img = pygame.image.load("assests/images/icons/victory.jpg").convert_alpha()

#load spritesheets
warrior_sheet = pygame.image.load("assests/images/warrior/Sprites/warrior.png").convert_alpha()
wizard_sheet = pygame.image.load("assests/images/wizard/Sprites/wizard.png").convert_alpha()

#define number of steps in each animation
warrior_animation_steps = [10, 8, 1, 7, 7, 3, 7]
wizard_animation_steps = [8, 8, 1, 8, 8, 3, 7]

#define fonts
count_font = pygame.font.Font("assests/fonts/turok.ttf", 80)
score_font = pygame.font.Font("assests/fonts/turok.ttf", 30)

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
fighter_1 = Fighter(1, 100, 310, False, warrior_data, warrior_sheet, warrior_animation_steps)
fighter_2 = Fighter(2, 650, 310, True, wizard_data, wizard_sheet, wizard_animation_steps)


#game loop
run = True
while run:

    clock.tick(fps)
    
    #draw background
    draw_bg()
    
    #show player stats
    draw_health_bar(fighter_1.health, 20, 20)
    draw_health_bar(fighter_2.health, 580, 20)
    draw_text("P1-Warrior: " + str(score[0]), score_font, red, 20, 60 )
    draw_text("P2-Wizard: " + str(score[1]), score_font, white, 580, 60 )
    
    #update coountdown
    if intro_count <= 0:
        # move fighters
        fighter_1.move(screen_width, screen_height, screen, fighter_2, round_over)
        fighter_2.move(screen_width, screen_height, screen, fighter_1, round_over)
    else:
        # display count timer
        draw_text(str(intro_count), count_font, red, screen_width/2, screen_height/3)
        # update count timer
        if(pygame.time.get_ticks() - last_count_update) >= 1000:
            intro_count -= 1
            last_count_update = pygame.time.get_ticks()
    
    #update fighters
    fighter_1.update()
    fighter_2.update()
    
    #draw fighters
    fighter_1.draw(screen)
    fighter_2.draw(screen)
    
    #check for player defeat
    if round_over == False:
        if fighter_1.alive == False:
            score[1] += 1 # if player1 dies, player2 gets score
            round_over = True
            round_over_time = pygame.time.get_ticks()
        elif fighter_2.alive == False:
            score[0] += 1 # if player2 dies, player1 gets score
            round_over = True
            round_over_time = pygame.time.get_ticks()
    else:
        #display victory image
        screen.blit(victory_img, (360, 150))
        if pygame.time.get_ticks() - round_over_time > round_over_cooldown:
            round_over = False
            intro_count = 3
            fighter_1.move(screen_width, screen_height, screen, fighter_2)
            fighter_2.move(screen_width, screen_height, screen, fighter_1)
    
    #event handler
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False
    
    #update display
    pygame.display.update()
    

#exit game
pygame.quit()