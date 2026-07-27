import pygame, random, sys, os, json

pygame.init()
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
FPS = 60
BG_COLOR = (10, 10, 30)
TEXT_COLOR = (255, 255, 255)
BUTTON_COLOR = (70, 70, 200)
BUTTON_HOVER_COLOR = (100, 100, 255)

# تغییر مسیرها به صورت نسبی
BASE = os.path.dirname(os.path.abspath(__file__))
PL_IMG = os.path.join(BASE, "pl.png")
FUEL_IMG = os.path.join(BASE, "5998974.PNG")
JUMP_SOUND = os.path.join(BASE, "jump.mp3")
FALL_SOUND = os.path.join(BASE, "fall.mp3")
FONT_PATH = os.path.join(BASE, "The Visitor.otf")
METEORITE_IMG = os.path.join(BASE, "meteorite.png")

class Star:
    def __init__(self):
        self.x = random.randint(0, SCREEN_WIDTH)
        self.y = random.randint(0, SCREEN_HEIGHT)
        self.speed = random.uniform(0.2, 1)

    def move(self, offset_y):
        self.y += self.speed - min(offset_y * 0.05, 2)
        if self.y > SCREEN_HEIGHT:
            self.y = 0
            self.x = random.randint(0, SCREEN_WIDTH)

    def draw(self, screen):
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), 2)

class Meteorite(pygame.sprite.Sprite):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.image = pygame.image.load(METEORITE_IMG).convert_alpha()
        self.image = pygame.transform.scale(self.image, (40, 40))
        self.rect = self.image.get_rect()
        self.rect.x = random.randint(0, SCREEN_WIDTH - 40)
        self.rect.y = random.randint(-500, -50)
        self.speed = 4

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > SCREEN_HEIGHT:
            self.rect.x = random.randint(0, SCREEN_WIDTH - 40)
            self.rect.y = random.randint(-500, -50)

class Platform(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((100, 20))
        self.image.fill((200, 200, 200))
        self.rect = self.image.get_rect(center=(x, y))

class BluePlatform(Platform):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.image.fill((100, 100, 255))
        self.speed = 2
        self.direction = 1

    def update(self):
        self.rect.x += self.speed * self.direction
        if self.rect.left <= 0 or self.rect.right >= SCREEN_WIDTH:
            self.direction *= -1

class RedPlatform(Platform):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.image.fill((255, 80, 80))
        self.timer = random.randint(30, 90)
        self.timer_started = False

    def update(self):
        if self.timer_started:
            self.timer -= 1
            if self.timer <= 0:
                self.kill()

    def start_timer(self):
        self.timer_started = True

class Fuel(pygame.sprite.Sprite):
    def __init__(self, game):
        super().__init__()
        self.image = game.fuel_img
        while True:
            x = random.randint(50, SCREEN_WIDTH - 50)
            y = random.randint(game.camera_y - SCREEN_HEIGHT, game.camera_y)
            self.rect = self.image.get_rect(center=(x, y))
            if not any(self.rect.colliderect(p.rect) for p in game.platforms):
                break

class PowerUp(pygame.sprite.Sprite):
    def __init__(self, x, y, kind):
        super().__init__()
        self.kind = kind
        self.image = pygame.Surface((25, 25))
        if kind == "slow":
            self.image.fill((0, 255, 255))
        elif kind == "double":
            self.image.fill((255, 255, 0))
        elif kind == "super":
            self.image.fill((255, 0, 255))
        self.rect = self.image.get_rect(center=(x, y))

class Player(pygame.sprite.Sprite):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.original_img = game.player_img
        self.image = self.original_img
        self.flipped = False
        self.rect = self.image.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.velocity_y = 0
        self.speed_x = 5
        self.on_ground = False

    def jump(self):
        jump_power = -20 if self.game.super_jump_active else -15
        if self.on_ground or self.game.double_jump_available:
            self.velocity_y = jump_power
            self.on_ground = False
            self.game.jump_sound.play()
            self.game.score += 5
            self.game.jump_count += 1
            if not self.on_ground and self.game.double_jump_available:
                self.game.double_jump_available = False
        self.game.super_jump_active = False

    def update(self, keys):
        if keys[pygame.K_a]:
            self.rect.x -= self.speed_x
            if not self.flipped:
                self.image = pygame.transform.flip(self.original_img, True, False)
                self.flipped = True
        if keys[pygame.K_d]:
            self.rect.x += self.speed_x
            if self.flipped:
                self.image = self.original_img
                self.flipped = False

        self.velocity_y += 0.5
        self.rect.y += self.velocity_y
        self.on_ground = False

        for p in self.game.platforms:
            if (self.rect.colliderect(p.rect)) and \
               (self.velocity_y > 0) and \
               (self.rect.bottom <= p.rect.centery + 15):
                self.rect.bottom = p.rect.top
                self.velocity_y = 0
                self.on_ground = True
                if isinstance(p, RedPlatform):
                    p.start_timer()

        for f in self.game.fuels:
            if self.rect.colliderect(f.rect):
                f.kill()
                self.game.score += 10
                self.game.fuel_level = min(100, self.game.fuel_level + 30)

        for m in self.game.meteorites:
            if self.rect.colliderect(m.rect):
                self.game.fall_sound.play()
                self.game.game_over()

        if self.rect.top > SCREEN_HEIGHT:
            self.game.fall_sound.play()
            self.game.game_over()

        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH:
            self.rect.right = SCREEN_WIDTH

def generate_platform(x, y):
    type_ = random.choices(["normal", "blue", "red"], weights=[75, 15, 10])[0]
    if type_ == "blue":
        return BluePlatform(x, y)
    elif type_ == "red":
        return RedPlatform(x, y)
    else:
        return Platform(x, y)

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Space Jumper")
        self.clock = pygame.time.Clock()
        
        try:
            self.font = pygame.font.Font(FONT_PATH, 24)
            self.big_font = pygame.font.Font(FONT_PATH, 48)
        except:
            self.font = pygame.font.SysFont("Arial", 24)
            self.big_font = pygame.font.SysFont("Arial", 48)

        self.player_img = pygame.image.load(PL_IMG).convert_alpha()
        self.player_img = pygame.transform.scale(self.player_img, (50, 50))
        self.fuel_img = pygame.image.load(FUEL_IMG).convert_alpha()
        self.fuel_img = pygame.transform.scale(self.fuel_img, (30, 30))
        self.jump_sound = pygame.mixer.Sound(JUMP_SOUND)
        self.fall_sound = pygame.mixer.Sound(FALL_SOUND)

        self.username = ""
        self.score = 0
        self.jump_count = 0
        self.timer = 0
        self.fuel_level = 100
        self.double_jump_available = False
        self.super_jump_active = False
        self.slow_motion_active = False
        self.slow_timer = 0
        self.camera_y = 0
        self.game_active = False
        self.stars = [Star() for _ in range(100)]
        self.load_scores()

    def load_scores(self):
        try:
            if os.path.exists("scores.json"):
                with open("scores.json", "r") as f:
                    self.scores_data = json.load(f)
            else:
                self.scores_data = {"scores": []}
        except:
            self.scores_data = {"scores": []}

    def save_scores(self):
        with open("scores.json", "w") as f:
            json.dump(self.scores_data, f)

    def reset_game(self):
        self.score = 0
        self.jump_count = 0
        self.timer = 0
        self.fuel_level = 100
        self.double_jump_available = False
        self.super_jump_active = False
        self.slow_motion_active = False
        self.slow_timer = 0
        self.camera_y = 0

    def game_loop(self):
        self.reset_game()
        self.player = Player(self)
        self.platforms = pygame.sprite.Group()
        self.fuels = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.meteorites = pygame.sprite.Group()
        
        # ایجاد شهاب سنگ‌ها
        for _ in range(2):
            self.meteorites.add(Meteorite(self))

        for i in range(25):
            y = SCREEN_HEIGHT - i * 100
            x = random.randint(50, SCREEN_WIDTH - 50)
            self.platforms.add(generate_platform(x, y))
        for _ in range(2):
            self.fuels.add(Fuel(self))

        while self.game_active:
            dt = self.clock.tick(FPS) / 1000.0
            if self.slow_motion_active:
                dt *= 0.5
            self.timer += dt
            
            keys = pygame.key.get_pressed()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_SPACE:
                        self.player.jump()
                    if e.key == pygame.K_ESCAPE:
                        self.game_active = False
                        return  # بازگشت به منوی اصلی بدون شروع مجدد بازی

            self.player.update(keys)
            self.platforms.update()
            self.powerups.update()
            self.meteorites.update()

            if self.player.rect.top <= SCREEN_HEIGHT // 3:
                dy = SCREEN_HEIGHT // 3 - self.player.rect.top
                self.player.rect.y += dy
                self.camera_y += dy
                for g in [self.platforms, self.fuels, self.powerups, self.meteorites]:
                    for sprite in g:
                        sprite.rect.y += dy
                for s in self.stars:
                    s.move(offset_y=dy)

            while True:
                min_y = min(p.rect.y for p in self.platforms)
                if min_y > -200:
                    y = min_y - random.randint(120, 180)
                    x = random.randint(50, SCREEN_WIDTH - 50)
                    self.platforms.add(generate_platform(x, y))
                    if random.random() < 0.1:
                        kind = random.choice(["slow", "double", "super"])
                        self.powerups.add(PowerUp(x, y - 30, kind))
                else:
                    break

            while len(self.fuels) < 2:
                self.fuels.add(Fuel(self))

            for p in self.powerups:
                if self.player.rect.colliderect(p.rect):
                    if p.kind == "slow":
                        self.slow_motion_active = True
                        self.slow_timer = 5.0
                    elif p.kind == "double":
                        self.double_jump_available = True
                    elif p.kind == "super":
                        self.super_jump_active = True
                    p.kill()

            if self.slow_motion_active:
                self.slow_timer -= dt
                if self.slow_timer <= 0:
                    self.slow_motion_active = False

            fuel_consumption_rate = 5 * (0.5 if self.slow_motion_active else 1) * dt
            self.fuel_level -= fuel_consumption_rate
            if self.fuel_level <= 0:
                self.fall_sound.play()
                self.game_over()

            self.screen.fill(BG_COLOR)
            for s in self.stars:
                s.draw(self.screen)
            self.platforms.draw(self.screen)
            self.fuels.draw(self.screen)
            self.powerups.draw(self.screen)
            self.meteorites.draw(self.screen)
            self.screen.blit(self.player.image, self.player.rect)

            self.draw_text(f"Player: {self.username}", 20, 20)
            self.draw_text(f"Score: {self.score}", 20, 50)
            self.draw_text(f"Jumps: {self.jump_count}", 20, 80)
            self.draw_text(f"Time: {int(self.timer)}s", 20, 110)

            pygame.draw.rect(self.screen, (180, 180, 180), (20, 140, 200, 20))
            pygame.draw.rect(self.screen, (0, 255, 0), (20, 140, int(200 * (self.fuel_level / 100)), 20))

            progress = min(1, self.camera_y / 5000)
            pygame.draw.rect(self.screen, (255, 255, 255), (SCREEN_WIDTH - 40, 100, 10, 400))
            pygame.draw.rect(self.screen, (0, 200, 255), (SCREEN_WIDTH - 40, 100 + 400 * (1 - progress), 10, 400 * progress))

            pygame.display.flip()

        if self.username.strip() and self.score > 0:
            self.scores_data["scores"].append({
                "username": self.username,
                "score": self.score,
                "jumps": self.jump_count
            })
            self.save_scores()

    def draw_text(self, text, x, y, color=TEXT_COLOR, size=24, centered=False):
        font = self.font if size == 24 else self.big_font
        text_surface = font.render(text, True, color)
        if centered:
            x = x - text_surface.get_width() // 2
        self.screen.blit(text_surface, (x, y))

    def game_over(self):
        waiting = True
        while waiting:
            self.screen.fill(BG_COLOR)
            for s in self.stars:
                s.draw(self.screen)
            
            text = self.big_font.render("GAME OVER", True, (255, 50, 50))
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
            
            self.draw_text("Press ESC to return to menu", SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20, TEXT_COLOR, 24, True)
            
            pygame.display.flip()
            
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    waiting = False
                    self.game_active = False

    def show_guide(self):
        while True:
            self.screen.fill(BG_COLOR)
            for s in self.stars:
                s.draw(self.screen)
            
            title = self.big_font.render("Game Guide", True, TEXT_COLOR)
            self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 50))
            
            guide_texts = [
                "Controls:",
                "A/D - Move Left/Right",
                "SPACE - Jump",
                "ESC - Pause/Return to Menu",
                "",
                "Platform Types:",
                "Gray - Normal Platform",
                "Blue - Moving Platform",
                "Red - Disappearing Platform",
                "",

                "",
                "Collect Fuel to increase your fuel level",
                "",
                "Avoid meteorites - they will kill you!"
            ]
            
            y_pos = 120
            for text in guide_texts:
                if text:
                    self.draw_text(text, SCREEN_WIDTH//2, y_pos, TEXT_COLOR, 24, True)
                y_pos += 30
            
            # Back button
            mouse_pos = pygame.mouse.get_pos()
            back_btn = pygame.Rect(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT - 80, 200, 50)
            pygame.draw.rect(self.screen, BUTTON_HOVER_COLOR if back_btn.collidepoint(mouse_pos) else BUTTON_COLOR, back_btn, border_radius=10)
            self.draw_text("Back to Menu", SCREEN_WIDTH//2, SCREEN_HEIGHT - 65, TEXT_COLOR, 24, True)
            
            pygame.display.flip()
            
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN and back_btn.collidepoint(e.pos):
                    return
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return

    def show_menu(self):
        username_input = ""
        entering = False
        buttons = [
            ("Start New Game", 200),
            ("Enter Username", 270),
            ("Show Scores", 340),
            ("Game Guide", 410),
            ("Exit", 480)
        ]

        while True:
            self.screen.fill(BG_COLOR)
            for s in self.stars: 
                s.draw(self.screen)
                
            title = self.big_font.render("Space Jumper", True, TEXT_COLOR)
            self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 80))

            mouse_pos = pygame.mouse.get_pos()
            for idx, (txt, y) in enumerate(buttons):
                btn = pygame.Rect(300, y, 200, 50)
                pygame.draw.rect(self.screen, BUTTON_HOVER_COLOR if btn.collidepoint(mouse_pos) else BUTTON_COLOR, btn, border_radius=10)
                self.draw_text(txt, SCREEN_WIDTH//2, y + 15, TEXT_COLOR, 24, True)

            for e in pygame.event.get():
                if e.type == pygame.QUIT: 
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN:
                    for idx, (_, y) in enumerate(buttons):
                        btn = pygame.Rect(300, y, 200, 50)
                        if btn.collidepoint(e.pos):
                            if idx == 0 and self.username.strip(): 
                                self.game_active = True
                                self.game_loop()
                            elif idx == 1: 
                                entering = True
                            elif idx == 2: 
                                self.show_scores()
                            elif idx == 3:
                                self.show_guide()
                            elif idx == 4: 
                                pygame.quit()
                                sys.exit()
                if e.type == pygame.KEYDOWN and entering:
                    if e.key == pygame.K_RETURN:
                        self.username = username_input.strip()
                        entering = False
                    elif e.key == pygame.K_BACKSPACE:
                        username_input = username_input[:-1]
                    else:
                        if len(username_input) < 15:
                            username_input += e.unicode

            if entering:
                input_box = pygame.Rect(300, 150, 200, 40)
                pygame.draw.rect(self.screen, (255, 255, 255), input_box, 2)
                self.draw_text(username_input, input_box.x + 10, input_box.y + 5)

            pygame.display.flip()
            self.clock.tick(FPS)

    def show_scores(self):
        while True:
            self.screen.fill(BG_COLOR)
            for s in self.stars:
                s.draw(self.screen)
            
            self.draw_text("Scoreboard", SCREEN_WIDTH//2, 50, TEXT_COLOR, 40, True)
            
            y = 120
            for entry in sorted(self.scores_data["scores"], key=lambda x: x["score"], reverse=True)[:5]:
                self.draw_text(f"{entry['username']} - {entry['score']} pts", SCREEN_WIDTH//2, y, TEXT_COLOR, 24, True)
                y += 40
                
            # Back button
            mouse_pos = pygame.mouse.get_pos()
            back_btn = pygame.Rect(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT - 80, 200, 50)
            pygame.draw.rect(self.screen, BUTTON_HOVER_COLOR if back_btn.collidepoint(mouse_pos) else BUTTON_COLOR, back_btn, border_radius=10)
            self.draw_text("Back to Menu", SCREEN_WIDTH//2, SCREEN_HEIGHT - 65, TEXT_COLOR, 24, True)
            
            pygame.display.flip()
            
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN and back_btn.collidepoint(e.pos):
                    return
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return

def main():
    g = Game()
    while True:
        g.show_menu()

if __name__ == "__main__":
    main()