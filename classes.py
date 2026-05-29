import math
import pygame

from settings import *


class Wall(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, color=BLUE, tag=None):
        super().__init__()
        self.width = width
        self.height = height
        self.color = resolve_color(color, BLUE)
        self.tag = tag
        self.kind = "wall"
        self.visible = True
        self.delta_x = 0
        self.delta_y = 0
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self._draw()

    def _shade(self, offset):
        return tuple(max(0, min(255, channel + offset)) for channel in self.color)

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        base_rect = self.image.get_rect()
        outer = self._shade(-58)
        inner = self._shade(-14)
        top_band = self._shade(30)
        pygame.draw.rect(self.image, outer, base_rect, border_radius=8)
        pygame.draw.rect(self.image, inner, base_rect.inflate(-6, -6), border_radius=7)
        pygame.draw.rect(self.image, top_band, (4, 4, self.width - 8, max(6, min(14, self.height // 4))), border_radius=6)

        if self.height >= 28 and self.width >= 28:
            tile_step = 18
            for x in range(12, self.width - 6, tile_step):
                pygame.draw.line(self.image, self._shade(-40), (x, 10), (x, self.height - 10), 2)
            for y in range(18, self.height - 8, tile_step):
                pygame.draw.line(self.image, self._shade(-34), (8, y), (self.width - 8, y), 2)

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def update(self):
        self.delta_x = 0
        self.delta_y = 0


class DynamicPlatform(Wall):
    def __init__(
        self,
        x,
        y,
        width,
        height,
        color=CYAN,
        movement="horizontal",
        distance=120,
        speed=2.0,
        start_offset=0,
        phase=0.0,
        tag=None,
    ):
        super().__init__(x, y, width, height, color=color, tag=tag)
        self.kind = "dynamic_platform"
        self.movement = movement
        self.distance = distance
        self.speed = speed
        self.base_x = x
        self.base_y = y
        self.phase = phase + start_offset * 0.02
        self.float_x = float(x)
        self.float_y = float(y)
        self._draw()

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        outline = self._shade(-76)
        fill = self._shade(-16)
        highlight = self._shade(36)
        warning = self._shade(82)
        pygame.draw.rect(self.image, outline, self.image.get_rect(), border_radius=10)
        pygame.draw.rect(self.image, fill, (4, 4, self.width - 8, self.height - 8), border_radius=9)
        pygame.draw.rect(self.image, highlight, (8, 6, self.width - 16, max(5, self.height // 3)), border_radius=8)
        arrow_y = self.height // 2
        step = 22
        for x in range(14, self.width - 8, step):
            points = [(x, arrow_y), (x + 8, arrow_y - 4), (x + 8, arrow_y + 4)]
            pygame.draw.polygon(self.image, warning, points)

    def update(self):
        old_x, old_y = self.rect.topleft
        self.phase += self.speed * 0.03
        offset = math.sin(self.phase) * self.distance
        if self.movement == "vertical":
            self.float_x = self.base_x
            self.float_y = self.base_y + offset
        else:
            self.float_x = self.base_x + offset
            self.float_y = self.base_y
        self.rect.x = int(round(self.float_x))
        self.rect.y = int(round(self.float_y))
        self.delta_x = self.rect.x - old_x
        self.delta_y = self.rect.y - old_y


class FallingPlatform(Wall):
    def __init__(self, x, y, width, height, color=ORANGE, delay=35, respawn_time=150, tag=None):
        super().__init__(x, y, width, height, color=color, tag=tag)
        self.kind = "falling_platform"
        self.delay = delay
        self.respawn_time = respawn_time
        self.origin = (x, y)
        self.float_y = float(y)
        self.triggered = False
        self.falling = False
        self.timer = 0
        self.velocity_y = 0.0
        self._draw()

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        outline = self._shade(-74)
        fill = self._shade(-18)
        highlight = self._shade(38)
        crack = self._shade(-96)
        pygame.draw.rect(self.image, outline, self.image.get_rect(), border_radius=9)
        pygame.draw.rect(self.image, fill, (4, 4, self.width - 8, self.height - 8), border_radius=8)
        pygame.draw.rect(self.image, highlight, (8, 6, self.width - 16, max(5, self.height // 3)), border_radius=7)

        crack_points = [
            (self.width * 0.22, self.height * 0.28),
            (self.width * 0.36, self.height * 0.58),
            (self.width * 0.49, self.height * 0.40),
            (self.width * 0.62, self.height * 0.72),
            (self.width * 0.76, self.height * 0.46),
        ]
        pygame.draw.lines(self.image, crack, False, crack_points, 3)
        pygame.draw.line(self.image, crack, (self.width * 0.57, 7), (self.width * 0.52, self.height - 7), 2)

    def trigger(self):
        if self.triggered or not self.visible:
            return
        self.triggered = True
        self.timer = 0

    def reset(self):
        self.visible = True
        self.triggered = False
        self.falling = False
        self.timer = 0
        self.velocity_y = 0.0
        self.float_y = float(self.origin[1])
        self.rect.topleft = self.origin
        self.delta_x = 0
        self.delta_y = 0

    def update(self):
        old_y = self.rect.y
        self.delta_x = 0
        self.delta_y = 0

        if not self.visible:
            self.timer += 1
            if self.timer >= self.respawn_time:
                self.reset()
            return

        if self.triggered and not self.falling:
            self.timer += 1
            if self.timer >= self.delay:
                self.falling = True
                self.timer = 0

        if self.falling:
            self.velocity_y = min(18.0, self.velocity_y + 0.95)
            self.float_y += self.velocity_y
            self.rect.y = int(round(self.float_y))
            self.delta_y = self.rect.y - old_y
            if self.rect.y > self.origin[1] + 460:
                self.visible = False
                self.timer = 0
                self.delta_y = 0


class FakeWall(Wall):
    def __init__(self, x, y, width, height, color=PURPLE, tag=None):
        super().__init__(x, y, width, height, color=color, tag=tag)
        self.kind = "fake_wall"
        self.triggered = False
        self.timer = 0
        self.fade_frames = 18
        self._draw(alpha=205)

    def _draw(self, alpha=205):
        self.image.fill((0, 0, 0, 0))
        outline = self._shade(-68)
        fill = self._shade(-8)
        shimmer = self._shade(54)
        pygame.draw.rect(self.image, (*outline, alpha), self.image.get_rect(), border_radius=8)
        pygame.draw.rect(self.image, (*fill, alpha), (4, 4, self.width - 8, self.height - 8), border_radius=7)
        for x in range(-self.height, self.width, 18):
            pygame.draw.line(self.image, (*shimmer, max(80, alpha - 40)), (x, self.height), (x + self.height, 0), 2)
        pygame.draw.rect(self.image, (*shimmer, min(255, alpha + 24)), (6, 6, self.width - 12, 6), border_radius=4)

    def trigger(self):
        if self.triggered:
            return
        self.triggered = True
        self.timer = 0

    def update(self):
        self.delta_x = 0
        self.delta_y = 0
        if not self.visible or not self.triggered:
            return
        self.timer += 1
        remaining = max(0, self.fade_frames - self.timer)
        alpha = int(205 * (remaining / max(1, self.fade_frames)))
        if alpha <= 0:
            self.visible = False
            return
        self._draw(alpha=alpha)


class ToggleWall(Wall):
    def __init__(self, x, y, width, height, color=BLUE, tag=None, initial_visible=False):
        super().__init__(x, y, width, height, color=color, tag=tag)
        self.kind = "toggle_wall"
        self.initial_visible = initial_visible
        self.visible = initial_visible
        self._draw()

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        outer = self._shade(-78)
        fill = self._shade(-10)
        glow = self._shade(60)
        pygame.draw.rect(self.image, outer, self.image.get_rect(), border_radius=8)
        pygame.draw.rect(self.image, fill, (4, 4, self.width - 8, self.height - 8), border_radius=7)
        for y in range(10, self.height - 6, 14):
            pygame.draw.line(self.image, glow, (10, y), (self.width - 10, y), 3)
        pygame.draw.rect(self.image, (*glow, 160), (6, 6, self.width - 12, 6), border_radius=4)


class Token(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, color=YELLOW, value=10):
        super().__init__()
        self.width = width
        self.height = height
        self.value = value
        self.color = resolve_color(color, YELLOW)
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self._draw()

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        center = (self.width // 2, self.height // 2)
        radius = min(self.width, self.height) // 2 - 1
        outer = tuple(max(0, channel - 60) for channel in self.color)
        inner = tuple(min(255, channel + 35) for channel in self.color)
        pygame.draw.circle(self.image, outer, center, radius)
        pygame.draw.circle(self.image, self.color, center, radius - 2)
        pygame.draw.circle(self.image, inner, (center[0] - 3, center[1] - 3), max(3, radius // 2))
        pygame.draw.circle(self.image, outer, center, max(3, radius // 3), 2)


class FireSkillPickup(pygame.sprite.Sprite):
    def __init__(self, x, y, width=52, height=42, message="获得火球术，按 F / J 向前投掷"):
        super().__init__()
        self.width = width
        self.height = height
        self.message = message
        self.kind = "fire_skill"
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self._draw()

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        pygame.draw.ellipse(self.image, (255, 146, 66, 86), (2, self.height - 12, self.width - 4, 10))
        center = (self.width // 2, self.height // 2 - 2)
        flame_points = [
            (center[0], 3),
            (center[0] + 15, center[1] - 2),
            (center[0] + 10, center[1] + 14),
            (center[0], self.height - 8),
            (center[0] - 11, center[1] + 13),
            (center[0] - 16, center[1] - 1),
        ]
        pygame.draw.polygon(self.image, (150, 54, 46), [(x, y + 2) for x, y in flame_points])
        pygame.draw.polygon(self.image, ORANGE, flame_points)
        inner_points = [
            (center[0] + 1, 10),
            (center[0] + 8, center[1] + 3),
            (center[0], self.height - 12),
            (center[0] - 7, center[1] + 4),
        ]
        pygame.draw.polygon(self.image, YELLOW, inner_points)
        pygame.draw.circle(self.image, WHITE, (center[0] - 3, center[1] - 1), 4)

    def collect(self, player):
        if player.has_fire_skill:
            return None
        player.equip_fire_skill()
        self.kill()
        return self.message


PistolPickup = FireSkillPickup


class BuffPickup(pygame.sprite.Sprite):
    def __init__(self, x, y, buff_type="burst", width=44, height=44, message="力量涌入", spawn_y=None):
        super().__init__()
        self.width = width
        self.height = height
        self.buff_type = buff_type
        self.message = message
        self.kind = "buff_pickup"
        self.target_y = float(y)
        self.float_y = float(spawn_y if spawn_y is not None else y)
        self.fall_speed = 7.0 if self.float_y < self.target_y else 0.0
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, int(round(self.float_y))))
        self._draw()

    def _palette(self):
        if self.buff_type == "rapid":
            return CYAN, WHITE
        if self.buff_type == "shield":
            return GREEN, WHITE
        return ORANGE, YELLOW

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        outer, inner = self._palette()
        center = (self.width // 2, self.height // 2)
        pygame.draw.circle(self.image, (*outer, 80), center, self.width // 2 - 2)
        pygame.draw.circle(self.image, outer, center, self.width // 2 - 8)
        if self.buff_type == "shield":
            pygame.draw.circle(self.image, WHITE, center, 9, 3)
        elif self.buff_type == "rapid":
            pygame.draw.polygon(self.image, inner, [(center[0], 8), (center[0] + 7, center[1]), (center[0] + 2, center[1]), (center[0] + 10, self.height - 8), (center[0] - 4, center[1] + 4), (center[0] + 1, center[1] + 4)])
        else:
            pygame.draw.circle(self.image, inner, center, 8)
            pygame.draw.circle(self.image, WHITE, (center[0] - 3, center[1] - 3), 3)

    def update(self):
        if self.float_y < self.target_y:
            self.float_y = min(self.target_y, self.float_y + self.fall_speed)
            self.fall_speed = min(12.0, self.fall_speed + 0.16)
        else:
            self.float_y += math.sin(pygame.time.get_ticks() * 0.01 + self.rect.centerx * 0.03) * 0.02
        self.rect.centery = int(round(self.float_y))

    def collect(self, player):
        if hasattr(player, "apply_buff"):
            player.apply_buff(self.buff_type)
        self.kill()
        return self.message


class Hazard(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, color=GREY, direction="up"):
        super().__init__()
        self.width = width
        self.height = height
        self.direction = direction
        self.color = resolve_color(color, GREY)
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self._draw()

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        spike = tuple(max(0, channel - 18) for channel in self.color)
        outline = tuple(max(0, channel - 80) for channel in self.color)
        count = max(1, self.width // 16 if self.direction in ("up", "down") else self.height // 16)
        if self.direction in ("up", "down"):
            slice_w = self.width / count
            for index in range(count):
                left = index * slice_w
                right = left + slice_w
                mid = (left + right) / 2
                if self.direction == "up":
                    points = [(left, self.height), (right, self.height), (mid, 0)]
                else:
                    points = [(left, 0), (right, 0), (mid, self.height)]
                pygame.draw.polygon(self.image, outline, points)
                inner = [(p[0], p[1]) for p in points]
                inner[0] = (inner[0][0] + 2, inner[0][1] - 2 if self.direction == "up" else inner[0][1] + 2)
                inner[1] = (inner[1][0] - 2, inner[1][1] - 2 if self.direction == "up" else inner[1][1] + 2)
                inner[2] = (inner[2][0], inner[2][1] + 4 if self.direction == "up" else inner[2][1] - 4)
                pygame.draw.polygon(self.image, spike, inner)
        else:
            slice_h = self.height / count
            for index in range(count):
                top = index * slice_h
                bottom = top + slice_h
                mid = (top + bottom) / 2
                if self.direction == "left":
                    points = [(self.width, top), (self.width, bottom), (0, mid)]
                else:
                    points = [(0, top), (0, bottom), (self.width, mid)]
                pygame.draw.polygon(self.image, outline, points)
                inner = [(p[0], p[1]) for p in points]
                inner[0] = (inner[0][0] - 2 if self.direction == "left" else inner[0][0] + 2, inner[0][1] + 2)
                inner[1] = (inner[1][0] - 2 if self.direction == "left" else inner[1][0] + 2, inner[1][1] - 2)
                inner[2] = (inner[2][0] + 4 if self.direction == "left" else inner[2][0] - 4, inner[2][1])
                pygame.draw.polygon(self.image, spike, inner)


class TriggerZone:
    def __init__(self, x, y, width, height, trigger_id, once=True, label=""):
        self.rect = pygame.Rect(x, y, width, height)
        self.trigger_id = trigger_id
        self.once = once
        self.label = label
        self.triggered = False


class Checkpoint(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, spawn_x, spawn_y, label="检查点"):
        super().__init__()
        self.width = width
        self.height = height
        self.label = label
        self.spawn_point = (spawn_x, spawn_y)
        self.active = False
        self.wave = 0.0
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self._draw()

    def set_active(self, active):
        self.active = active
        self._draw()

    def animate(self, frame_count):
        self.wave = math.sin(frame_count * 0.12)
        self._draw()

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        pole_x = self.width // 2
        pole_color = (220, 228, 242)
        banner_color = (96, 194, 255) if self.active else (255, 118, 118)
        glow_color = (145, 226, 255) if self.active else (255, 186, 146)
        pygame.draw.rect(self.image, pole_color, (pole_x - 3, 10, 6, self.height - 20), border_radius=3)
        pygame.draw.circle(self.image, glow_color, (pole_x, 10), 7)
        wave = int(self.wave * 5)
        banner = [(pole_x + 4, 18), (self.width - 10, 22 + wave), (pole_x + 4, 50)]
        pygame.draw.polygon(self.image, banner_color, banner)
        pygame.draw.line(self.image, tuple(max(0, c - 55) for c in banner_color), banner[0], banner[1], 2)
        pygame.draw.line(self.image, tuple(max(0, c - 55) for c in banner_color), banner[1], banner[2], 2)
        base = [(pole_x - 16, self.height - 12), (pole_x + 16, self.height - 12), (pole_x + 10, self.height - 4), (pole_x - 10, self.height - 4)]
        pygame.draw.polygon(self.image, (82, 98, 126), base)
        if self.active:
            pygame.draw.circle(self.image, (*glow_color, 70), (pole_x, 18), 14)


class ExitZone(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height):
        super().__init__()
        self.width = width
        self.height = height
        self.wave = 0.0
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self._draw()

    def animate(self, frame_count):
        self.wave = math.sin(frame_count * 0.09)
        self._draw()

    def _draw(self):
        self.image.fill((0, 0, 0, 0))
        glow = int(28 + abs(self.wave) * 32)
        pole_x = self.width // 2
        flag_color = (255, 213, 104)
        beam_color = (244, 248, 255)
        gate_color = (86, 128, 226)
        pygame.draw.circle(self.image, (255, 226, 128, 90), (pole_x, 18), 18 + glow // 6)
        pygame.draw.rect(self.image, beam_color, (pole_x - 4, 16, 8, self.height - 26), border_radius=4)
        flag_y = 28 + int(self.wave * 4)
        flag = [(pole_x + 5, flag_y), (self.width - 12, flag_y + 10), (pole_x + 5, flag_y + 36)]
        pygame.draw.polygon(self.image, flag_color, flag)
        pygame.draw.line(self.image, (174, 128, 40), flag[0], flag[1], 2)
        pygame.draw.line(self.image, (174, 128, 40), flag[1], flag[2], 2)
        gate_rect = pygame.Rect(8, self.height - 42, self.width - 16, 26)
        pygame.draw.rect(self.image, (35, 48, 78), gate_rect, border_radius=10)
        pygame.draw.rect(self.image, gate_color, gate_rect.inflate(-6, -8), border_radius=8)
        pygame.draw.rect(self.image, (160, 206, 255), (gate_rect.x + 10, gate_rect.y + 6, gate_rect.width - 20, 6), border_radius=3)
