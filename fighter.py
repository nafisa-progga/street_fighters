import pygame


class Fighter:
    def __init__(self, x, y):
        self.rect = pygame.Rect((x, y, 80, 180)) #x, y, width, height
        self.vel_y = 0
        self.jum = False
        self.attacking = False
        self.attack_type = 0

    def move(self, screen_width, screen_height, surface, target):
        speed = 10
        gravity = 2
        dx = 0
        dy = 0

        #get key presses
        key = pygame.key.get_pressed()

        #can only perform other actions if not currently attacking
        if self.attacking == False:
            #movement
            if key[pygame.K_a]: #left
                dx = - speed
            if key[pygame.K_d]: #right
                dx =  speed
            if key[pygame.K_w] and self.jump == False: #jump
                self.vel_y =  -30
                self.jump = True

            #attack
            if key[pygame.K_e] or key[pygame.K_q]:
                self.attack(surface, target)
                #determine which type of attack was used
                if key[pygame.K_e]:
                    self.attack_type = 1
                if key[pygame.K_q]:
                    self.attack_type = 2
        
        #else:

        #apply gravity
        self.vel_y += gravity
        dy += self.vel_y


        #ensure player stays on screen
        if self.rect.left + dx <0:
            dx = - self.rect.left
        if self.rect.right +dx > screen_width:
            dx = screen_width - self.rect.right
        if self.rect.bottom +dy > screen_height - 110:
            self.vel_y = 0
            self.jump = False
            dy = screen_height - 110 - self.rect.bottom


        #update player position
        self.rect.x += dx
        self.rect.y += dy

    def attack(self, surface, target):
        self.attacking = True
        attacking_rect = pygame.Rect(self.rect.centerx, self.rect.y, 2*self.rect.width, self.rect.height)
        if attacking_rect.colliderect(target.rect):
            print("Hit")

        pygame.draw.rect(surface, (0, 255, 0), attacking_rect)


    def draw(self, surface):
        pygame.draw.rect(surface, (255, 0, 0), self.rect)