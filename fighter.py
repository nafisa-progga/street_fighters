import pygame


class Fighter:
    def __init__(self, x, y, flip, data, sprite_sheet, animation_steps):
        self.size = data[0]
        self.scale = data[1]
        self.offset = data[2]
        self.flip = flip
        self.animation_list = self.load_images(sprite_sheet, animation_steps)
        self.action = 0 # 0:idle, 1:run, 2:jump, 3:attack1, 4:attack2, 5:hit, 6:death
        self.frame_index = 0
        self.image = self.animation_list[self.action][self.frame_index]
        self.rect = pygame.Rect((x, y, 80, 180)) #x, y, width, height
        self.vel_y = 0
        self.jum = False
        self.attacking = False
        self.attack_type = 0
        self.health = 100
    
    
    def load_images(self, sprite_sheet, animation_steps):
        # extract images from spritesheet
        animation_list = []
        for y, animation in enumerate(animation_steps):
            temp_img_list = []
            for x in range(animation):
                temp_img = sprite_sheet.subsurface(x * self.size, y * self.size, self.size, self.size) #x,y, width, height
                scaled_temp_img = pygame.transform.scale(temp_img, (self.size * self.scale, self.size * self.scale))
                temp_img_list.append(scaled_temp_img)
            animation_list.append(temp_img_list)
        
        return animation_list
    
    
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


        #ensure players face each other
        if target.rect.centerx > self.rect.centerx:
            self.flip = False
        else:
            self.flip = True
        
        
        #update player position
        self.rect.x += dx
        self.rect.y += dy
    
    
    def attack(self, surface, target):
        self.attacking = True
        attacking_rect = pygame.Rect(self.rect.centerx - (2 * self.rect.width * self.flip), self.rect.y, 2*self.rect.width, self.rect.height)
        if attacking_rect.colliderect(target.rect):
            target.health -= 10

        pygame.draw.rect(surface, (0, 255, 0), attacking_rect)


    def draw(self, surface):
        img = pygame.transform.flip(self.image, self.flip, False) # image, x flip, y flip
        pygame.draw.rect(surface, (255, 0, 0), self.rect)
        surface.blit(self.img, (self.rect.x - (self.offset[0] * self.scale), self.rect.y - (self.offset[1] * self.scale) ))