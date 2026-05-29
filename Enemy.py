import math

import pygame

from settings import BLACK, CYAN, GREEN, ORANGE, PURPLE, RED, WHITE, YELLOW, resolve_color
from classes import Token
from Projectile import Projectile


def clamp(value, low, high):
    return max(low, min(high, value))


def sign(value):
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def normalize(dx, dy, fallback=(1.0, 0.0)):
    length = math.hypot(dx, dy)
    if length <= 0.0001:
        return fallback
    return dx / length, dy / length


class Enemy(pygame.sprite.Sprite):
    def __init__(
        self,
        x,
        y,
        width,
        height,
        speed,
        direction,
        color=RED,
        enemy_type="walker",
        patrol_distance=140,
        hover_amplitude=36,
        hover_speed=0.1,
        health=2,
        config=None,
    ):
        super().__init__()
        self.width = width
        self.height = height
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.float_x = float(x)
        self.float_y = float(y)
        self.base_x = float(x)
        self.base_y = float(y)
        self.speed = float(speed)
        self.direction = 1 if direction >= 0 else -1
        self.enemy_type = enemy_type
        self.color = resolve_color(color, RED)
        self.config = config or {}
        self.gravity = 0.9
        self.max_fall_speed = 16
        self.x_vel = 0.0
        self.y_vel = 0.0
        self.on_ground = False
        self.hit_flash_timer = 0
        self.squished = False
        self.knockback_speed = 14
        self.hover_phase = (x + y) * 0.013
        self.hover_amplitude = hover_amplitude
        self.hover_speed = hover_speed
        self.patrol_distance = patrol_distance
        self.patrol_center_x = float(x)
        self.contact_damage = self.config.get("contact_damage", 1)
        self.score_value = self.config.get("score_value", 30 if enemy_type == "flyer" else 25)
        self.stomp_score = self.config.get("stomp_score", 10)
        self.max_health = max(1, int(health))
        self.health = self.max_health
        self.can_stomp = enemy_type != "flyer"
        self.pending_announcements = []
        self.pending_spawns = []
        self.frame_count = 0

        self.fly_state = "patrol"
        self.fly_timer = 0
        self.dive_cooldown = 80
        self.dive_target = (self.rect.centerx, self.rect.centery)

        self.is_boss = enemy_type == "boss"
        self.boss_name = self.config.get("boss_name", "天穹审判者")
        self.phase_names = {1: "压制模式", 2: "过载模式", 3: "狂怒模式"}
        self.vulnerable_timer = 0
        self.shielded = False
        self.attack_pattern_index = 0
        self.attack_cooldown = 60
        self.attack_state = "idle"
        self.attack_timer = 0
        self.attack_direction = self.direction
        self.summon_cooldown = 180
        self.meteor_timer = 0
        self.phase = 1
        self.phase_intro_done = False
        self.core_flash_timer = 0
        self.shield_flash_timer = 0
        self.orbit_angle = 0.0
        self.wind_timer = 0
        self.arena_left = self.config.get("arena_left", x - patrol_distance)
        self.arena_right = self.config.get("arena_right", x + patrol_distance + width)
        self.node_cycle = 0
        self.shield_nodes = []
        self._init_boss_state()
        self._draw()

    def _init_boss_state(self):
        if not self.is_boss:
            return
        self.contact_damage = self.config.get("contact_damage", 1)
        self.score_value = self.config.get("score_value", 200)
        self.can_stomp = True
        self.attack_cooldown = 84
        self.summon_cooldown = 260
        self.attack_pattern_index = 0
        self.phase_intro_done = False
        self._restore_shield(initial=True)
        self.pending_announcements.append(f"{self.boss_name} 已进入战场")

    def _shade(self, offset):
        return tuple(max(0, min(255, channel + offset)) for channel in self.color)

    def _boss_ratio(self):
        return self.health / max(1, self.max_health)

    def _boss_core_rect(self):
        return pygame.Rect(self.rect.x + self.width // 2 - 22, self.rect.y + self.height // 2 - 14, 44, 30)

    def _boss_node_layout(self):
        nodes = [
            {"name": "left", "offset": (-58, -18)},
            {"name": "right", "offset": (58, -18)},
        ]
        if self.phase >= 2:
            nodes.append({"name": "top", "offset": (0, -50)})
        return nodes

    def _restore_shield(self, initial=False):
        if not self.is_boss:
            return
        self.shielded = True
        self.vulnerable_timer = 0
        self.attack_state = "idle"
        self.attack_timer = 0
        self.attack_cooldown = 84 if self.phase == 1 else 68 if self.phase == 2 else 56
        node_health = 2 if self.phase == 1 else 3 if self.phase == 2 else 4
        self.shield_nodes = []
        for layout in self._boss_node_layout():
            center = (
                self.rect.centerx + layout["offset"][0],
                self.rect.centery + layout["offset"][1],
            )
            self.shield_nodes.append(
                {
                    "name": layout["name"],
                    "health": node_health,
                    "max_health": node_health,
                    "center": center,
                    "radius": 18 if layout["name"] != "top" else 16,
                    "pulse": self.node_cycle * 0.35 + len(self.shield_nodes),
                }
            )
        if not initial:
            self.pending_announcements.append("护盾已重建，先击碎肩部核心")
        self.node_cycle += 1

    def _enter_vulnerable_state(self):
        self.shielded = False
        self.vulnerable_timer = 360 if self.phase == 1 else 300 if self.phase == 2 else 260
        self.attack_state = "idle"
        self.attack_timer = 0
        self.core_flash_timer = 18
        self.pending_announcements.append("核心暴露，立刻集火")

    def get_phase_name(self):
        return self.phase_names.get(self.phase, "压制模式")

    def health_ratio(self):
        return self.health / max(1, self.max_health)

    def pop_announcements(self):
        messages = list(self.pending_announcements)
        self.pending_announcements.clear()
        return messages

    def pop_spawn_requests(self):
        requests = list(self.pending_spawns)
        self.pending_spawns.clear()
        return requests

    def is_stompable(self):
        if self.is_boss:
            return self.vulnerable_timer > 0
        return self.can_stomp

    def take_hit(self, amount=1, source_direction=0, hit_type="projectile"):
        if self.is_boss:
            if self.shielded and hit_type != "node":
                self.shield_flash_timer = 6
                return False
            scale = 5 if hit_type == "stomp" else 2
            self.health = max(0, self.health - amount * scale)
            self.hit_flash_timer = 8
            self.core_flash_timer = 10
            self.direction = -1 if source_direction > 0 else 1 if source_direction < 0 else self.direction
            if self.health <= 0:
                self.squished = True
            return True

        self.health = max(0, self.health - amount)
        self.hit_flash_timer = 6
        if self.enemy_type == "flyer":
            self.direction = -1 if source_direction > 0 else 1
            self.float_x += -source_direction * 18
            self.fly_state = "recover"
            self.fly_timer = 28
        else:
            self.x_vel = -self.knockback_speed if source_direction > 0 else self.knockback_speed
        if self.health <= 0:
            self.squished = True
        return True

    def _apply_horizontal_collisions(self, walls):
        self.float_x += self.x_vel
        self.rect.x = int(round(self.float_x))
        collisions = pygame.sprite.spritecollide(self, walls, False)
        for wall in collisions:
            if self.x_vel > 0:
                self.rect.right = wall.rect.left
            elif self.x_vel < 0:
                self.rect.left = wall.rect.right
            self.float_x = float(self.rect.x)
            self.direction *= -1
            self.x_vel = 0

    def _apply_vertical_collisions(self, walls):
        self.on_ground = False
        self.float_y += self.y_vel
        self.rect.y = int(round(self.float_y))
        collisions = pygame.sprite.spritecollide(self, walls, False)
        for wall in collisions:
            if self.y_vel > 0:
                self.rect.bottom = wall.rect.top
                self.on_ground = True
            elif self.y_vel < 0:
                self.rect.top = wall.rect.bottom
            self.float_y = float(self.rect.y)
            self.y_vel = 0

    def _should_turn_for_ledge(self, walls):
        if not self.on_ground or self.speed == 0:
            return False
        probe_x = self.rect.left - 4 if self.direction < 0 else self.rect.right
        probe = pygame.Rect(probe_x, self.rect.bottom + 1, 8, 8)
        return not any(probe.colliderect(wall.rect) for wall in walls)

    def _update_walker(self, walls, hazards):
        if self.speed:
            self.x_vel += self.speed * self.direction
            self.x_vel = clamp(self.x_vel, -self.speed, self.speed)

        self._apply_horizontal_collisions(walls)
        self.y_vel = clamp(self.y_vel + self.gravity, -self.max_fall_speed, self.max_fall_speed)
        self._apply_vertical_collisions(walls)

        if pygame.sprite.spritecollide(self, hazards, False):
            self.direction *= -1

        if self._should_turn_for_ledge(walls):
            self.direction *= -1

        self.x_vel *= 0.62

    def _fly_patrol_position(self):
        self.base_x += self.speed * self.direction
        left_limit = self.patrol_center_x - self.patrol_distance
        right_limit = self.patrol_center_x + self.patrol_distance
        if self.base_x < left_limit or self.base_x > right_limit:
            self.direction *= -1
            self.base_x = clamp(self.base_x, left_limit, right_limit)
        target_x = self.base_x
        target_y = self.base_y + math.sin(self.hover_phase) * self.hover_amplitude
        return target_x, target_y

    def _update_flyer(self, walls, hazards, player):
        self.hover_phase += self.hover_speed
        self.dive_cooldown = max(0, self.dive_cooldown - 1)

        if self.fly_state == "patrol":
            target_x, target_y = self._fly_patrol_position()
            self.float_x += (target_x - self.float_x) * 0.16
            self.float_y += (target_y - self.float_y) * 0.22
            if player:
                dx = player.rect.centerx - self.rect.centerx
                dy = player.rect.centery - self.rect.centery
                if abs(dx) < 280 and -140 < dy < 220 and self.dive_cooldown <= 0:
                    self.fly_state = "windup"
                    self.fly_timer = 18
                    self.dive_target = (player.rect.centerx, player.rect.centery - 14)

        elif self.fly_state == "windup":
            self.fly_timer -= 1
            self.float_y += math.sin(self.hover_phase * 4.0) * 1.2
            if self.fly_timer <= 0:
                self.fly_state = "dive"
                self.fly_timer = 34
                dx = self.dive_target[0] - self.rect.centerx
                dy = self.dive_target[1] - self.rect.centery
                nx, ny = normalize(dx, dy, fallback=(self.direction, 0.0))
                self.x_vel = nx * (5.8 + self.speed * 0.5)
                self.y_vel = ny * (5.0 + self.speed * 0.5)
                self.direction = 1 if self.x_vel >= 0 else -1

        elif self.fly_state == "dive":
            self.fly_timer -= 1
            self.float_x += self.x_vel
            self.float_y += self.y_vel
            self.y_vel *= 0.99
            if self.fly_timer <= 0:
                self.fly_state = "recover"
                self.fly_timer = 24
                self.dive_cooldown = 80

        elif self.fly_state == "recover":
            self.fly_timer -= 1
            target_x, target_y = self._fly_patrol_position()
            self.float_x += (target_x - self.float_x) * 0.18
            self.float_y += (target_y - self.float_y) * 0.2
            if self.fly_timer <= 0:
                self.fly_state = "patrol"

        self.rect.x = int(round(self.float_x))
        self.rect.y = int(round(self.float_y))

        if pygame.sprite.spritecollide(self, walls, False):
            self.direction *= -1
            self.base_x += self.direction * 18
            self.float_x += self.direction * 12
            self.fly_state = "recover"
            self.fly_timer = 20

        if pygame.sprite.spritecollide(self, hazards, False):
            self.direction *= -1
            self.base_y = max(80, self.base_y - 10)
            self.fly_state = "recover"
            self.fly_timer = 18

    def _maybe_shift_phase(self):
        if not self.is_boss:
            return
        ratio = self._boss_ratio()
        new_phase = 1
        if ratio <= 0.33:
            new_phase = 3
        elif ratio <= 0.66:
            new_phase = 2
        if new_phase != self.phase:
            self.phase = new_phase
            self.attack_pattern_index = 0
            self.pending_announcements.append(f"{self.boss_name} 切换到 {self.get_phase_name()}")
            self._restore_shield()

    def _update_boss_nodes(self):
        for node, layout in zip(self.shield_nodes, self._boss_node_layout()):
            node["center"] = (
                self.rect.centerx + layout["offset"][0],
                self.rect.centery + layout["offset"][1],
            )
            node["pulse"] += 0.08

    def _queue_flyer_spawn(self, side_direction, vertical_offset):
        spawn_x = self.rect.centerx + side_direction * 160
        spawn_y = self.rect.y + vertical_offset
        self.pending_spawns.append(
            {
                "x": spawn_x,
                "y": spawn_y,
                "width": 58,
                "height": 42,
                "speed": 2.1,
                "dir": -side_direction,
                "color": "PURPLE" if self.phase >= 3 else "CYAN",
                "enemy_type": "flyer",
                "health": 3 if self.phase < 3 else 4,
                "patrol_distance": 130,
                "hover_amplitude": 26,
                "hover_speed": 0.14,
                "score_value": 45,
            }
        )

    def _spawn_shockwaves(self, enemy_projectiles):
        for direction in (-1, 1):
            enemy_projectiles.add(
                Projectile(
                    self.rect.centerx,
                    self.rect.bottom - 12,
                    54,
                    20,
                    direction,
                    speed=9 + self.phase,
                    color=CYAN,
                    owner="enemy",
                    damage=1,
                    lifetime=88,
                    variant="wave",
                )
            )

    def _fire_spread(self, enemy_projectiles, player, count=3, speed=6.0):
        if not player:
            return
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - (self.rect.centery - 18)
        base_x, base_y = normalize(dx, dy, fallback=(self.direction, 0.0))
        spread = 0.18 if count <= 3 else 0.11
        for index in range(count):
            offset = index - (count - 1) / 2
            vx = (base_x + offset * spread) * speed
            vy = (base_y + offset * spread * 0.75) * speed
            enemy_projectiles.add(
                Projectile(
                    self.rect.centerx + self.direction * 24,
                    self.rect.centery - 12,
                    20,
                    20,
                    1 if vx >= 0 else -1,
                    color=ORANGE if self.phase >= 2 else YELLOW,
                    owner="enemy",
                    velocity_x=vx,
                    velocity_y=vy,
                    damage=1,
                    lifetime=110,
                    variant="orb",
                )
            )

    def _fire_meteor_pattern(self, enemy_projectiles, player):
        if not player:
            return
        anchor_x = player.rect.centerx
        offsets = (-220, -110, 0, 110, 220)
        for index, offset in enumerate(offsets):
            enemy_projectiles.add(
                Projectile(
                    anchor_x + offset,
                    self.rect.y - 120 - index * 34,
                    18,
                    24,
                    1,
                    color=ORANGE,
                    owner="enemy",
                    velocity_x=offset * 0.012,
                    velocity_y=6.0 + index * 0.4,
                    damage=1,
                    lifetime=120,
                    gravity=0.08,
                    variant="ember",
                )
            )

    def _fire_orbit_ring(self, enemy_projectiles):
        ring_count = 8 if self.phase >= 3 else 6
        speed = 5.4 if self.phase >= 3 else 4.8
        for index in range(ring_count):
            angle = self.orbit_angle + index * (math.tau / ring_count)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            enemy_projectiles.add(
                Projectile(
                    self.rect.centerx,
                    self.rect.centery - 10,
                    18,
                    18,
                    1 if vx >= 0 else -1,
                    color=ORANGE,
                    owner="enemy",
                    velocity_x=vx,
                    velocity_y=vy,
                    damage=1,
                    lifetime=130,
                    variant="orb",
                )
            )
        if self.phase >= 3:
            for index in range(ring_count):
                angle = -self.orbit_angle + index * (math.tau / ring_count) + 0.22
                vx = math.cos(angle) * 4.2
                vy = math.sin(angle) * 4.2
                enemy_projectiles.add(
                    Projectile(
                        self.rect.centerx,
                        self.rect.centery - 10,
                        16,
                        16,
                        1 if vx >= 0 else -1,
                        color=CYAN,
                        owner="enemy",
                        velocity_x=vx,
                        velocity_y=vy,
                        damage=1,
                        lifetime=138,
                        variant="orb",
                    )
                )
        self.orbit_angle += 0.42

    def _fire_side_barrage(self, enemy_projectiles, player):
        if not player:
            return
        incoming_from_left = player.rect.centerx >= self.rect.centerx
        spawn_x = self.arena_left + 34 if incoming_from_left else self.arena_right - 34
        direction = 1 if incoming_from_left else -1
        base_y = clamp(player.rect.centery - 20, 180, 820)
        for offset in (-96, -24, 48):
            start_y = clamp(base_y + offset, 150, 860)
            correction = clamp((player.rect.centery - start_y) * 0.035, -1.6, 1.6)
            enemy_projectiles.add(
                Projectile(
                    spawn_x,
                    start_y,
                    20,
                    20,
                    direction,
                    color=ORANGE if self.phase >= 3 else YELLOW,
                    owner="enemy",
                    velocity_x=7.8 * direction,
                    velocity_y=correction,
                    damage=1,
                    lifetime=136,
                    variant="orb",
                )
            )

    def _select_boss_attack(self, enemy_projectiles, player):
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
            return

        if self.vulnerable_timer > 0:
            self._fire_spread(enemy_projectiles, player, count=3, speed=6.6)
            self.attack_cooldown = 34
            return

        patterns = ["spread", "dash", "spread"]
        if self.phase >= 2:
            patterns.extend(["wide", "meteor", "orbit", "barrage"])
        if self.phase >= 3:
            patterns.extend(["summon", "orbit", "barrage"])

        choice = patterns[self.attack_pattern_index % len(patterns)]
        self.attack_pattern_index += 1
        if choice == "spread":
            self._fire_spread(enemy_projectiles, player, count=5 if self.phase >= 2 else 3, speed=6.4 + self.phase * 0.22)
            self.attack_cooldown = 58 if self.phase >= 2 else 72
        elif choice == "wide":
            self._fire_spread(enemy_projectiles, player, count=7, speed=7.0)
            self.attack_cooldown = 68
        elif choice == "dash":
            self.attack_state = "dash_windup"
            self.attack_timer = 30 if self.phase >= 2 else 36
            self.attack_direction = 1 if player and player.rect.centerx >= self.rect.centerx else -1
            self.pending_announcements.append("Boss 蓄力冲锋，准备起跳")
        elif choice == "summon":
            self._queue_flyer_spawn(-1 if self.direction > 0 else 1, 58)
            if self.phase >= 3:
                self._queue_flyer_spawn(1 if self.direction > 0 else -1, 18)
            self.attack_cooldown = 104
            self.pending_announcements.append("审判者召出巡火眼")
        elif choice == "meteor":
            self._fire_meteor_pattern(enemy_projectiles, player)
            self.attack_cooldown = 82
            self.pending_announcements.append("顶部火雨正在落下")
        elif choice == "orbit":
            self._fire_orbit_ring(enemy_projectiles)
            self.attack_cooldown = 76
            self.pending_announcements.append("审判者展开环绕火球")
        elif choice == "barrage":
            self._fire_side_barrage(enemy_projectiles, player)
            self.attack_cooldown = 72
            self.pending_announcements.append("侧翼火线压进")

    def _update_boss_state_machine(self, enemy_projectiles, player):
        if self.attack_state == "dash_windup":
            self.attack_timer -= 1
            self.float_x += math.sin(self.frame_count * 0.9) * 0.8
            if self.attack_timer <= 0:
                self.attack_state = "dashing"
                self.attack_timer = 22 if self.phase >= 2 else 18
                self.x_vel = (9.2 + self.phase * 0.7) * self.attack_direction
        elif self.attack_state == "dashing":
            self.attack_timer -= 1
            self.float_x += self.x_vel
            self.direction = 1 if self.x_vel >= 0 else -1
            left_bound = self.arena_left
            right_bound = self.arena_right - self.width
            if self.float_x <= left_bound or self.float_x >= right_bound or self.attack_timer <= 0:
                self.float_x = clamp(self.float_x, left_bound, right_bound)
                self.attack_state = "recover"
                self.attack_timer = 20
                self.x_vel = 0
                self._spawn_shockwaves(enemy_projectiles)
                self.attack_cooldown = 72 if self.phase >= 2 else 86
        elif self.attack_state == "recover":
            self.attack_timer -= 1
            if self.attack_timer <= 0:
                self.attack_state = "idle"
        else:
            self._select_boss_attack(enemy_projectiles, player)

    def _update_boss(self, enemy_projectiles, player):
        self._maybe_shift_phase()
        self.hover_phase += 0.06
        hover_center = self.config.get("boss_hover_y", self.base_y)
        hover_amp = 18 if self.phase == 1 else 34 if self.phase == 2 else 52
        hover_wobble = 8 if self.phase < 3 else 14
        self.rect.x = int(round(self.float_x))
        self.rect.y = int(round(hover_center + math.sin(self.hover_phase * 0.8) * hover_amp + math.sin(self.hover_phase * 1.7) * hover_wobble))
        self.float_y = float(self.rect.y)

        if player:
            self.direction = 1 if player.rect.centerx >= self.rect.centerx else -1

        if self.attack_state in ("idle", "recover") and self.vulnerable_timer <= 0:
            self.float_x += self.speed * 0.75 * self.direction
            if self.rect.left <= self.arena_left or self.rect.right >= self.arena_right:
                self.direction *= -1
                self.float_x = clamp(self.float_x, self.arena_left, self.arena_right - self.width)

        if self.attack_state == "idle" and self.vulnerable_timer > 0:
            drift = self.speed * 0.45 * self.direction
            if player and abs(player.rect.centerx - self.rect.centerx) < 90:
                drift *= -1
            self.float_x += drift
            if self.rect.left <= self.arena_left or self.rect.right >= self.arena_right:
                self.direction *= -1
                self.float_x = clamp(self.float_x, self.arena_left, self.arena_right - self.width)

        self._update_boss_state_machine(enemy_projectiles, player)
        if self.phase >= 2:
            self.base_y = hover_center
        if self.phase >= 3 and player:
            self.wind_timer = (self.wind_timer + 1) % 240
            if 90 < self.wind_timer < 180:
                pull = -0.32 if player.rect.centerx < self.rect.centerx else 0.32
                player.x_vel += pull
        self.rect.x = int(round(clamp(self.float_x, self.arena_left, self.arena_right - self.width)))
        self.rect.y = int(round(hover_center + math.sin(self.hover_phase * 0.8) * hover_amp + math.sin(self.hover_phase * 1.7) * hover_wobble))

        if self.vulnerable_timer > 0:
            self.vulnerable_timer -= 1
            if self.vulnerable_timer <= 0 and self.health > 0:
                self._restore_shield()

        if self.core_flash_timer > 0:
            self.core_flash_timer -= 1
        if self.shield_flash_timer > 0:
            self.shield_flash_timer -= 1
        self._update_boss_nodes()

    def _handle_standard_projectiles(self, player_projectiles):
        hits = pygame.sprite.spritecollide(self, player_projectiles, False)
        for projectile in hits:
            if projectile.owner != "player":
                continue
            if self.take_hit(projectile.damage, projectile.direction, hit_type="projectile"):
                projectile.impact()

    def _handle_boss_projectiles(self, player_projectiles):
        hits = pygame.sprite.spritecollide(self, player_projectiles, False)
        for projectile in hits:
            if projectile.owner != "player":
                continue
            consumed = False
            if self.shielded:
                for node in self.shield_nodes:
                    if node["health"] <= 0:
                        continue
                    node_rect = pygame.Rect(0, 0, node["radius"] * 2, node["radius"] * 2)
                    node_rect.center = node["center"]
                    if projectile.rect.colliderect(node_rect):
                        node["health"] = max(0, node["health"] - projectile.damage)
                        self.hit_flash_timer = 6
                        self.shield_flash_timer = 8
                        projectile.impact()
                        consumed = True
                        break
                if not consumed:
                    projectile.impact()
                    self.shield_flash_timer = 6
                if all(node["health"] <= 0 for node in self.shield_nodes):
                    self._enter_vulnerable_state()
                continue

            if self.rect.colliderect(projectile.rect):
                self.take_hit(projectile.damage, projectile.direction, hit_type="projectile")
                projectile.impact()

    def _draw_walker(self, body_color):
        outline = tuple(max(0, channel - 70) for channel in body_color)
        belly = tuple(min(255, channel + 35) for channel in body_color)
        self.image.fill((0, 0, 0, 0))
        pygame.draw.rect(self.image, outline, (0, 0, self.width, self.height), border_radius=10)
        pygame.draw.rect(self.image, body_color, (4, 4, self.width - 8, self.height - 8), border_radius=10)
        pygame.draw.rect(self.image, belly, (8, self.height // 2, self.width - 16, self.height // 3), border_radius=8)
        eye_y = self.height // 3
        pygame.draw.circle(self.image, WHITE, (self.width // 3, eye_y), 4)
        pygame.draw.circle(self.image, WHITE, (self.width * 2 // 3, eye_y), 4)
        pupil_offset = -1 if self.direction < 0 else 1
        pygame.draw.circle(self.image, BLACK, (self.width // 3 + pupil_offset, eye_y), 2)
        pygame.draw.circle(self.image, BLACK, (self.width * 2 // 3 + pupil_offset, eye_y), 2)

    def _draw_flyer(self, body_color):
        self.image.fill((0, 0, 0, 0))
        outline = self._shade(-88)
        wing_color = self._shade(-22)
        wing_tip = self._shade(52)
        body = pygame.Rect(12, 12, self.width - 24, self.height - 18)
        flap = math.sin(self.hover_phase * 3.5) * 8
        wing_y = self.height // 2
        left_wing = [(body.left + 6, wing_y), (2, wing_y - 10 - flap), (10, wing_y + 14 + flap)]
        right_wing = [(body.right - 6, wing_y), (self.width - 2, wing_y - 10 - flap), (self.width - 10, wing_y + 14 + flap)]
        pygame.draw.polygon(self.image, outline, left_wing)
        pygame.draw.polygon(self.image, outline, right_wing)
        pygame.draw.polygon(self.image, wing_color, [(x + 2, y) for x, y in left_wing])
        pygame.draw.polygon(self.image, wing_color, [(x - 2, y) for x, y in right_wing])
        pygame.draw.ellipse(self.image, outline, body)
        pygame.draw.ellipse(self.image, body_color, body.inflate(-6, -6))
        pygame.draw.circle(self.image, wing_tip, (body.left + 9, wing_y - 1), 4)
        pygame.draw.circle(self.image, wing_tip, (body.right - 9, wing_y - 1), 4)
        eye_line_y = body.y + 10
        pygame.draw.line(self.image, WHITE, (body.left + 10, eye_line_y), (body.centerx - 2, eye_line_y + 2), 3)
        pygame.draw.line(self.image, WHITE, (body.centerx + 2, eye_line_y + 2), (body.right - 10, eye_line_y), 3)
        if self.fly_state == "windup":
            pygame.draw.circle(self.image, YELLOW, (body.centerx, body.centery + 4), 4)

    def _draw_boss(self, body_color):
        self.image.fill((0, 0, 0, 0))
        outline = self._shade(-90)
        plate = self._shade(-26)
        glow = CYAN if self.vulnerable_timer <= 0 else GREEN
        warning = ORANGE if self.phase >= 2 else YELLOW

        body = pygame.Rect(22, 36, self.width - 44, self.height - 54)
        head = pygame.Rect(self.width // 2 - 44, 10, 88, 42)
        left_leg = pygame.Rect(42, self.height - 48, 42, 34)
        right_leg = pygame.Rect(self.width - 84, self.height - 48, 42, 34)
        left_arm = pygame.Rect(10, 52, 26, 76)
        right_arm = pygame.Rect(self.width - 36, 52, 26, 76)

        for rect in (left_arm, right_arm, left_leg, right_leg, body, head):
            pygame.draw.rect(self.image, outline, rect, border_radius=14)
            pygame.draw.rect(self.image, plate if rect not in (head,) else body_color, rect.inflate(-6, -6), border_radius=12)

        visor = pygame.Rect(head.x + 14, head.y + 12, head.width - 28, 12)
        pygame.draw.rect(self.image, glow, visor, border_radius=6)
        pygame.draw.rect(self.image, WHITE, (visor.x + 10, visor.y + 3, visor.width - 20, 4), border_radius=2)

        shoulder_y = 52
        pygame.draw.rect(self.image, warning, (34, shoulder_y, 30, 12), border_radius=5)
        pygame.draw.rect(self.image, warning, (self.width - 64, shoulder_y, 30, 12), border_radius=5)

        core_rect = pygame.Rect(self.width // 2 - 24, self.height // 2 - 16, 48, 34)
        core_color = glow if self.core_flash_timer % 2 == 0 else WHITE
        pygame.draw.rect(self.image, self._with_alpha(glow, 70), core_rect.inflate(24, 18), border_radius=18)
        pygame.draw.rect(self.image, outline, core_rect, border_radius=12)
        pygame.draw.rect(self.image, core_color, core_rect.inflate(-6, -6), border_radius=10)
        pygame.draw.line(self.image, WHITE, (core_rect.x + 8, core_rect.centery), (core_rect.right - 8, core_rect.centery), 2)

        if self.shielded:
            shield_alpha = 92 if self.shield_flash_timer == 0 else 150
            shield_rect = pygame.Rect(8, 2, self.width - 16, self.height - 8)
            pygame.draw.ellipse(self.image, self._with_alpha(CYAN, shield_alpha), shield_rect, 4)
            pygame.draw.ellipse(self.image, self._with_alpha(WHITE, 30), shield_rect.inflate(-18, -22), 2)

        for node in self.shield_nodes:
            if node["health"] <= 0:
                continue
            cx = int(node["center"][0] - self.rect.x)
            cy = int(node["center"][1] - self.rect.y)
            radius = node["radius"]
            pulse = int((math.sin(node["pulse"]) + 1.0) * 3)
            node_color = YELLOW if node["name"] == "top" else CYAN
            pygame.draw.circle(self.image, self._with_alpha(node_color, 70), (cx, cy), radius + 5 + pulse)
            pygame.draw.circle(self.image, outline, (cx, cy), radius + 1)
            pygame.draw.circle(self.image, node_color, (cx, cy), radius)
            pygame.draw.circle(self.image, WHITE, (cx - 3, cy - 3), max(3, radius // 3))
            health_ratio = node["health"] / max(1, node["max_health"])
            bar_width = radius * 2
            bar_x = cx - radius
            bar_y = cy + radius + 6
            pygame.draw.rect(self.image, (36, 48, 66), (bar_x, bar_y, bar_width, 5), border_radius=3)
            pygame.draw.rect(self.image, warning, (bar_x, bar_y, int(bar_width * health_ratio), 5), border_radius=3)

    def _with_alpha(self, color, alpha):
        if isinstance(color, pygame.Color):
            return (color.r, color.g, color.b, alpha)
        return (*color, alpha)

    def _draw(self):
        body_color = self._shade(38) if self.hit_flash_timer <= 0 else WHITE
        if self.is_boss:
            self._draw_boss(body_color)
        elif self.enemy_type == "flyer":
            self._draw_flyer(body_color)
        else:
            self._draw_walker(body_color)

    def update(self, walls, tokens, hazards, player_projectiles, enemy_projectiles=None, player=None, frame_count=0):
        self.frame_count = frame_count
        if self.squished:
            token_value = self.score_value
            token_size = 30 if self.is_boss else 25
            tokens.add(Token(self.rect.centerx - token_size // 2, self.rect.centery - token_size // 2, token_size, token_size, value=token_value))
            if self.is_boss:
                for offset_x in (-70, -20, 30, 80):
                    tokens.add(Token(self.rect.centerx + offset_x, self.rect.centery - 40, 24, 24, color=CYAN, value=40))
            self.kill()
            return

        if self.is_boss:
            self._handle_boss_projectiles(player_projectiles)
        else:
            self._handle_standard_projectiles(player_projectiles)

        if self.squished:
            token_value = self.score_value
            token_size = 30 if self.is_boss else 25
            tokens.add(Token(self.rect.centerx - token_size // 2, self.rect.centery - token_size // 2, token_size, token_size, value=token_value))
            if self.is_boss:
                for offset_x in (-70, -20, 30, 80):
                    tokens.add(Token(self.rect.centerx + offset_x, self.rect.centery - 40, 24, 24, color=CYAN, value=40))
            self.kill()
            return

        if self.is_boss:
            self._update_boss(enemy_projectiles, player)
        elif self.enemy_type == "flyer":
            self._update_flyer(walls, hazards, player)
        else:
            self._update_walker(walls, hazards)

        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= 1
        self._draw()
