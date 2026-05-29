import pygame

from settings import BLACK, CYAN, ORANGE, RED, WHITE, YELLOW


class Projectile(pygame.sprite.Sprite):
    def __init__(
        self,
        x,
        y,
        width,
        height,
        direction,
        speed=7,
        color=YELLOW,
        owner="player",
        velocity_x=None,
        velocity_y=0.0,
        damage=1,
        lifetime=120,
        gravity=0.0,
        variant="bullet",
        pierce=0,
    ):
        super().__init__()
        self.width = width
        self.height = height
        self.owner = owner
        self.damage = damage
        self.gravity = gravity
        self.variant = variant
        self.pierce = pierce
        self.lifetime = lifetime
        self.age = 0
        self.direction = 1 if direction >= 0 else -1
        self.float_x = float(x)
        self.float_y = float(y)
        self.velocity_x = float(speed * self.direction if velocity_x is None else velocity_x)
        self.velocity_y = float(velocity_y)
        self.base_color = tuple(color[:3]) if isinstance(color, (tuple, list)) else color
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(int(round(x)), int(round(y))))
        self._draw()

    def _with_alpha(self, color, alpha):
        if isinstance(color, pygame.Color):
            return (color.r, color.g, color.b, alpha)
        return (*color, alpha)

    def _draw_bullet(self):
        glow = pygame.Surface((self.width + 8, self.height + 8), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, self._with_alpha(self.base_color, 90), glow.get_rect())
        self.image.blit(glow, (-4, -4))
        capsule = pygame.Rect(2, 2, self.width - 4, self.height - 4)
        pygame.draw.ellipse(self.image, self.base_color, capsule)
        pygame.draw.ellipse(self.image, self._with_alpha(WHITE, 220), capsule.inflate(-self.width // 3, -self.height // 2))

    def _draw_orb(self):
        center = (self.width // 2, self.height // 2)
        radius = max(4, min(self.width, self.height) // 2 - 2)
        pygame.draw.circle(self.image, self._with_alpha(self.base_color, 70), center, radius + 4)
        pygame.draw.circle(self.image, self.base_color, center, radius)
        pygame.draw.circle(self.image, WHITE, (center[0] - 2, center[1] - 2), max(2, radius // 3))

    def _draw_wave(self):
        outer = pygame.Rect(1, self.height // 2 - 5, self.width - 2, 10)
        inner = outer.inflate(-8, -4)
        pygame.draw.ellipse(self.image, self._with_alpha(CYAN, 110), outer)
        pygame.draw.ellipse(self.image, self.base_color, inner)
        pygame.draw.line(self.image, WHITE, (inner.x + 6, inner.centery), (inner.right - 6, inner.centery), 2)

    def _draw_ember(self):
        center = (self.width // 2, self.height // 2)
        points = [
            (center[0], 1),
            (self.width - 2, center[1]),
            (center[0], self.height - 2),
            (1, center[1]),
        ]
        pygame.draw.polygon(self.image, self._with_alpha(ORANGE, 70), points)
        pygame.draw.polygon(self.image, self.base_color, [(x, y) for x, y in points])
        pygame.draw.circle(self.image, WHITE, center, max(2, self.width // 6))

    def _draw_fireball(self):
        center = (self.width // 2, self.height // 2)
        tail_dir = -1 if self.direction > 0 else 1
        for index, alpha in enumerate((90, 70, 46)):
            tail_x = center[0] + tail_dir * (8 + index * 5)
            tail_radius = max(4, self.height // 3 - index)
            pygame.draw.circle(self.image, self._with_alpha(ORANGE, alpha), (tail_x, center[1]), tail_radius)
        radius = max(7, min(self.width, self.height) // 2 - 3)
        pygame.draw.circle(self.image, self._with_alpha(RED, 96), center, radius + 5)
        pygame.draw.circle(self.image, ORANGE, center, radius)
        pygame.draw.circle(self.image, YELLOW, (center[0] - 2 * self.direction, center[1] - 2), max(4, radius - 4))
        pygame.draw.circle(self.image, WHITE, (center[0] - 4 * self.direction, center[1] - 4), max(2, radius // 3))

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        if self.variant == "fireball":
            self._draw_fireball()
        elif self.variant == "orb":
            self._draw_orb()
        elif self.variant == "wave":
            self._draw_wave()
        elif self.variant == "ember":
            self._draw_ember()
        else:
            self._draw_bullet()

    def impact(self):
        if self.pierce > 0:
            self.pierce -= 1
            return
        self.kill()

    def update(self, walls, enemies, projectiles, player=None):
        self.age += 1
        if self.age >= self.lifetime:
            self.kill()
            return

        self.velocity_y += self.gravity
        self.float_x += self.velocity_x
        self.float_y += self.velocity_y
        self.rect.centerx = int(round(self.float_x))
        self.rect.centery = int(round(self.float_y))

        if pygame.sprite.spritecollide(self, walls, False):
            self.kill()
            return

        if self.owner == "enemy" and player and self.rect.colliderect(player.rect):
            push = -7 if self.velocity_x < 0 else 7
            lift = -11 if self.velocity_y <= 2 else -8
            player.handle_damage(push, lift, damage=self.damage)
            self.impact()
            return

        if self.rect.right < -80 or self.rect.left > 9000 or self.rect.bottom < -80 or self.rect.top > 2200:
            self.kill()
