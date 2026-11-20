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


#define fighter variables
#warrior
warrior_size = 162
warrior_scale = 4
warrior_offset = [72, 56]
warrior_data = [warrior_size, warrior_scale, warrior_offset]

#wizard
wizard_size = 250
wizard_scale = 3
wizard_offset = [72, 56]
wizard_data = [wizard_size, wizard_scale, wizard_offset]


#load background image
bg_image = pygame.image.load("assests/images/background/background.jpg").convert_alpha()

#load spritesheets
warrior_sheet = pygame.image.load("assests/images/warrior/Sprites/warrior.jpg").convert_alpha()
wizard_sheet = pygame.image.load("assests/images/wizard/Sprites/wizard.jpg").convert_alpha()

#define number of steps in each animation
warrior_animation_steps = [10, 8, 1, 7, 7, 3, 7]
wizard_animation_steps = [8, 8, 1, 8, 8, 3, 7]


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
fighter_1 = Fighter(100, 310, False, warrior_data, warrior_sheet, warrior_animation_steps)
fighter_2 = Fighter(650, 310, True, wizard_data, wizard_sheet, wizard_animation_steps)


#game loop
run = True
while run:

    clock.tick(fps)
    
    #draw background
    draw_bg()
    
    #show player stats
    draw_health_bar(fighter_1.health, 20, 20)
    draw_health_bar(fighter_2.health, 580, 20)

    #move fighters
    fighter_1.move(screen_width, screen_height, screen, fighter_2)

    
    #draw fighters
    fighter_1.draw(screen)
    fighter_2.draw(screen)


    #event handler
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False
    
    #update display
    pygame.display.update()
    

#exit game
pygame.quit()