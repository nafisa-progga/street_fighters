import pygame
from fighter import Fighter


pygame.init()


screen_width = 800
screen_height = int(screen_width * 0.8)

screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Brawler")


#set framerate
clock = pygame.time.Clock()
fps = 60

#define colors
red = (255, 0, 0)
yellow = (255, 255, 0)
white = (255, 255, 255)

#load background image
bg_image = pygame.image.load("assests/images/background/background.jpg").convert_alpha()



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
fighter_1 = Fighter(100, 310)
fighter_2 = Fighter(650, 310)



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