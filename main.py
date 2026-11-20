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


#load background image
bg_image = pygame.image.load("assests/images/background/background.jpg").convert_alpha()



#function for drawing background
def draw_bg():
    scaled_bg = pygame.transform.scale(bg_image, (screen_width, screen_height))
    screen.blit(scaled_bg, (0,0))


#create two instances of fighters
fighter_1 = Fighter(100, 310)
fighter_2 = Fighter(650, 310)



#game loop
run = True
while run:

    clock.tick(fps)
    
    #draw background
    draw_bg()

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