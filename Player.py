import pygame
from settings import *
from Projectile import Projectile


class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height):
        super().__init__()
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.width = width
        self.height = height
        self.previous_rect = self.rect.copy()
        self.gravity = 0.9
        self.max_fall_speed = 18
        self.ground_acceleration = 0.9
        self.air_acceleration = 0.58
        self.ground_friction = 0.76
        self.air_friction = 0.08
        self.max_speed = 8.0
        self.jump_height = 15
        self.wall_jump_x = 7.0
        self.wall_slide_speed = 2.8
        self.facing_direction = "right"
        self.score = 0

        self.pos_x = float(x)
        self.pos_y = float(y)
        self.x_vel = 0.0
        self.y_vel = 0.0
        self.is_jumping = False
        self.has_double_jumped = False

        self.is_wall_sliding = False
        self.wall_direction = None
        self.on_platform = False
        self.supporting_platform = None

        self.health = 5
        self.max_health = 5
        self.dead = False
        self.is_damaged = False
        self.invincibility_timeframe = 72
        self.invincibility_timer = self.invincibility_timeframe
        self.has_fire_skill = False

        self.projectile_max = 4
        self.fire_timer = 18
        self.fire_threshold = 18
        self.fire_buffer_frames = 8
        self.fire_buffer_timer = 0
        self.weapon_flash_timer = 0
        self.weapon_recoil = 0.0

        self.jump_buffer_frames = 10
        self.jump_buffer_timer = 0
        self.coyote_frames = 8
        self.coyote_timer = 0

        self.glide_fall_speed = 2.3
        self.glide_gravity = 0.18
        self.damage_flash_color = (255, 244, 214)
        self.buff_timers = {"burst": 0, "rapid": 0, "shield": 0}
        self.permanent_buffs = {"burst": False, "rapid": False}
        self.god_mode = False
        self.pet_active = False
        self.pet_angle = 0.0
        self.pet_timer = 0
        self._draw()

    def queue_jump(self):
        self.jump_buffer_timer = self.jump_buffer_frames

    def queue_fire(self):
        self.fire_buffer_timer = self.fire_buffer_frames

    def set_position(self, x, y):
        self.rect.x = x
        self.rect.y = y
        self.pos_x = float(x)
        self.pos_y = float(y)
        self.previous_rect = self.rect.copy()
        self.x_vel = 0.0
        self.y_vel = 0.0
        self.is_jumping = False
        self.has_double_jumped = False
        self.is_wall_sliding = False
        self.wall_direction = None
        self.on_platform = False
        self.supporting_platform = None
        self.fire_buffer_timer = 0
        self.weapon_flash_timer = 0
        self.weapon_recoil = 0.0

    @property
    def has_pistol(self):
        return self.has_fire_skill

    @has_pistol.setter
    def has_pistol(self, value):
        self.has_fire_skill = value

    def equip_fire_skill(self):
        self.has_fire_skill = True
        self.pet_active = True

    def equip_pistol(self):
        self.equip_fire_skill()

    def apply_buff(self, buff_type, duration=FPS * 8):
        if buff_type in self.permanent_buffs:
            self.permanent_buffs[buff_type] = True
            self.buff_timers[buff_type] = 0
        elif buff_type in self.buff_timers:
            self.buff_timers[buff_type] = max(self.buff_timers[buff_type], duration)

    def has_buff(self, buff_type):
        return self.permanent_buffs.get(buff_type, False) or self.buff_timers.get(buff_type, 0) > 0

    def get_upgrade_state(self):
        return dict(self.permanent_buffs)

    def set_upgrade_state(self, upgrade_state):
        for buff_type in self.permanent_buffs:
            self.permanent_buffs[buff_type] = bool(upgrade_state.get(buff_type, False))
            if self.permanent_buffs[buff_type]:
                self.buff_timers[buff_type] = 0

    def grant_respawn_protection(self):
        self.invincibility_timer = 0
        self.is_damaged = True

    def weapon_ready_ratio(self):
        return min(1.0, self.fire_timer / max(1, self.fire_threshold))

    def has_shield_buff(self):
        return self.buff_timers["shield"] > 0

    def apply_platform_motion(self):
        platform = self.supporting_platform
        if not platform:
            return
        if not getattr(platform, "visible", True):
            self.supporting_platform = None
            self.on_platform = False
            return
        delta_x = getattr(platform, "delta_x", 0)
        delta_y = getattr(platform, "delta_y", 0)
        if delta_x or delta_y:
            self.rect.x += delta_x
            self.rect.y += delta_y
            self.pos_x = float(self.rect.x)
            self.pos_y = float(self.rect.y)

    def _horizontal_input(self, keys):
        move_left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        move_right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        if move_left and not move_right:
            return -1
        if move_right and not move_left:
            return 1
        return 0

    def move_and_collide_x(self, walls):
        self.pos_x += self.x_vel
        self.rect.x = int(round(self.pos_x))
        collisions = pygame.sprite.spritecollide(self, walls, False)
        for wall in collisions:
            if self.x_vel > 0:
                self.rect.right = wall.rect.left
                self.wall_direction = "right"
            elif self.x_vel < 0:
                self.rect.left = wall.rect.right
                self.wall_direction = "left"
            self.pos_x = float(self.rect.x)
            self.x_vel = 0

    def move_and_collide_y(self, walls):
        self.on_platform = False
        self.supporting_platform = None
        self.pos_y += self.y_vel
        self.rect.y = int(round(self.pos_y))
        collisions = pygame.sprite.spritecollide(self, walls, False)
        for wall in collisions:
            if self.y_vel > 0:
                self.rect.bottom = wall.rect.top
                self.on_platform = True
                self.supporting_platform = wall
                self.is_jumping = False
                self.has_double_jumped = False
                self.coyote_timer = self.coyote_frames
            elif self.y_vel < 0:
                self.rect.top = wall.rect.bottom
                self.is_jumping = True
            self.pos_y = float(self.rect.y)
            self.y_vel = 0

        if not self.on_platform and self.coyote_timer > 0:
            self.coyote_timer -= 1

    def update_wall_slide(self, walls, horizontal_input):
        if self.on_platform:
            self.is_wall_sliding = False
            return
        touching_left = any(self.rect.move(-1, 0).colliderect(wall.rect) for wall in walls)
        touching_right = any(self.rect.move(1, 0).colliderect(wall.rect) for wall in walls)
        moving_down = self.y_vel > 0
        self.is_wall_sliding = False
        if touching_left and horizontal_input < 0 and moving_down:
            self.is_wall_sliding = True
            self.wall_direction = "left"
        elif touching_right and horizontal_input > 0 and moving_down:
            self.is_wall_sliding = True
            self.wall_direction = "right"

        if self.is_wall_sliding and self.y_vel > self.wall_slide_speed:
            self.y_vel = self.wall_slide_speed

    def try_consume_jump(self, horizontal_input):
        if self.jump_buffer_timer <= 0:
            return
        did_jump = False
        if self.on_platform or self.coyote_timer > 0:
            self.y_vel = -self.jump_height
            self.is_jumping = True
            self.on_platform = False
            self.coyote_timer = 0
            did_jump = True
        elif self.is_wall_sliding:
            self.y_vel = -self.jump_height
            if horizontal_input > 0:
                self.x_vel = self.wall_jump_x
            elif horizontal_input < 0:
                self.x_vel = -self.wall_jump_x
            elif self.wall_direction == "left":
                self.x_vel = self.wall_jump_x
            elif self.wall_direction == "right":
                self.x_vel = -self.wall_jump_x
            self.is_jumping = True
            self.has_double_jumped = False
            self.on_platform = False
            did_jump = True
        elif self.is_jumping and not self.has_double_jumped:
            self.y_vel = -self.jump_height
            self.has_double_jumped = True
            self.on_platform = False
            did_jump = True

        if did_jump:
            self.jump_buffer_timer = 0

    def handle_enemy_collisions(self, enemies):
        enemy_collisions = pygame.sprite.spritecollide(self, enemies, False)
        for enemy in enemy_collisions:
            stomped = (
                (enemy.is_stompable() if hasattr(enemy, "is_stompable") else getattr(enemy, "can_stomp", True))
                and self.previous_rect.bottom <= enemy.rect.top + 10
                and self.rect.bottom >= enemy.rect.top
                and self.y_vel >= 0
            )
            if stomped:
                self.y_vel = -self.jump_height
                self.is_jumping = True
                self.has_double_jumped = False
                self.on_platform = False
                self.supporting_platform = None
                if hasattr(enemy, "take_hit"):
                    enemy.take_hit(amount=1, source_direction=0, hit_type="stomp")
                else:
                    enemy.squished = True
                self.score += getattr(enemy, "stomp_score", 10)
            else:
                push = -7 if self.rect.centerx < enemy.rect.centerx else 7
                self.handle_damage(push, -10, damage=getattr(enemy, "contact_damage", 1))

    def handle_hazard_collisions(self, hazards):
        hazard_collisions = pygame.sprite.spritecollide(self, hazards, False)
        for hazard in hazard_collisions:
            overlap = self.rect.clip(hazard.rect)
            if not overlap.width or not overlap.height:
                continue
            if overlap.width < overlap.height:
                if self.rect.centerx < hazard.rect.centerx:
                    self.rect.x -= overlap.width + 2
                    knock_x = -8
                else:
                    self.rect.x += overlap.width + 2
                    knock_x = 8
                self.pos_x = float(self.rect.x)
                knock_y = -8 if self.rect.centery < hazard.rect.centery else 5
                self.handle_damage(knock_x, knock_y)
            else:
                if self.rect.centery < hazard.rect.centery:
                    self.rect.y -= overlap.height + 2
                    knock_y = -13
                else:
                    self.rect.y += overlap.height + 2
                    knock_y = 8
                self.pos_y = float(self.rect.y)
                push = -6 if self.rect.centerx < hazard.rect.centerx else 6
                self.handle_damage(push, knock_y)
                self.is_jumping = True
                self.has_double_jumped = False
                self.on_platform = False
                self.supporting_platform = None

    def collect_pickups(self, pickups):
        messages = []
        pickup_collisions = pygame.sprite.spritecollide(self, pickups, False)
        for pickup in pickup_collisions:
            if hasattr(pickup, "collect"):
                message = pickup.collect(self)
                if message:
                    messages.append(message)
        return messages

    def handle_damage(self, knockback_x=0, knockback_y=-8, damage=1):
        if self.god_mode:
            return
        if self.invincibility_timer >= self.invincibility_timeframe:
            if self.has_shield_buff():
                self.buff_timers["shield"] = 0
                self.invincibility_timer = 0
                self.is_damaged = True
                return
            self.health -= damage
            self.x_vel = knockback_x
            self.y_vel = knockback_y
            self.is_jumping = True
            self.on_platform = False
            self.supporting_platform = None
            self.has_double_jumped = False
            if self.health <= 0:
                self.dead = True

            self.invincibility_timer = 0
            self.is_damaged = True

    def invincibility(self):
        if self.invincibility_timer < self.invincibility_timeframe:
            self.invincibility_timer += 1
            self.is_damaged = True
        else:
            self.is_damaged = False
        if self.weapon_flash_timer > 0:
            self.weapon_flash_timer -= 1
        self.weapon_recoil *= 0.68
        for buff_type in self.buff_timers:
            if self.buff_timers[buff_type] > 0:
                self.buff_timers[buff_type] -= 1
        if self.pet_active:
            self.pet_angle += 0.08
            self.pet_timer += 1

    def draw(self):
        self._draw()

    def _draw(self):
        if self.god_mode:
            base_color = (255, 216, 86) if self.invincibility_timer % 10 < 5 else (255, 244, 214)
        else:
            base_color = GREEN if not self.is_damaged or self.invincibility_timer % 6 else self.damage_flash_color
        outline = tuple(max(0, channel - 70) for channel in base_color)
        belly = tuple(min(255, channel + 35) for channel in base_color)
        self.image.fill((0, 0, 0, 0))
        pygame.draw.rect(self.image, outline, (0, 0, self.width, self.height), border_radius=12)
        pygame.draw.rect(self.image, base_color, (4, 4, self.width - 8, self.height - 8), border_radius=12)
        pygame.draw.rect(self.image, belly, (8, self.height // 2 - 2, self.width - 16, self.height // 3), border_radius=10)
        eye_y = self.height // 3
        left_eye_x = self.width // 3
        right_eye_x = self.width * 2 // 3
        pupil_offset = -2 if self.facing_direction == "left" else 2
        pygame.draw.circle(self.image, WHITE, (left_eye_x, eye_y), 4)
        pygame.draw.circle(self.image, WHITE, (right_eye_x, eye_y), 4)
        pygame.draw.circle(self.image, BLACK, (left_eye_x + pupil_offset, eye_y), 2)
        pygame.draw.circle(self.image, BLACK, (right_eye_x + pupil_offset, eye_y), 2)
        if self.has_shield_buff():
            pygame.draw.circle(self.image, (120, 255, 188), (self.width // 2, self.height // 2), self.width // 2 - 2, 2)
        if self.has_fire_skill:
            palm_x = self.width - 8 if self.facing_direction == "right" else 8
            palm_y = self.height // 2 + 4
            pygame.draw.circle(self.image, (255, 142, 62), (palm_x, palm_y), 6)
            pygame.draw.circle(self.image, (255, 224, 94), (palm_x - (2 if self.facing_direction == "right" else -2), palm_y - 2), 3)
            if self.weapon_flash_timer > 0:
                pygame.draw.circle(self.image, (255, 238, 152), (palm_x, palm_y), 10, 2)
                pygame.draw.circle(self.image, (255, 106, 64), (palm_x, palm_y), 8, 1)

    def update(self, walls, enemies, tokens, pickups, hazards, projectiles, level_width, level_height):
        self.previous_rect = self.rect.copy()
        self.apply_platform_motion()
        self.invincibility()
        keys = pygame.key.get_pressed()
        horizontal_input = self._horizontal_input(keys)

        if self.jump_buffer_timer > 0:
            self.jump_buffer_timer -= 1
        if self.fire_buffer_timer > 0:
            self.fire_buffer_timer -= 1

        move_accel = self.ground_acceleration if self.on_platform else self.air_acceleration
        move_friction = self.ground_friction if self.on_platform else self.air_friction
        if horizontal_input < 0:
            self.x_vel = max(-self.max_speed, self.x_vel - move_accel)
            self.facing_direction = "left"
        elif horizontal_input > 0:
            self.x_vel = min(self.max_speed, self.x_vel + move_accel)
            self.facing_direction = "right"
        else:
            if self.x_vel > 0:
                self.x_vel -= move_friction
                if self.x_vel < 0:
                    self.x_vel = 0
            elif self.x_vel < 0:
                self.x_vel += move_friction
                if self.x_vel > 0:
                    self.x_vel = 0

        aim_up = keys[pygame.K_UP] or keys[pygame.K_w]
        shoot_pressed = self.fire_buffer_timer > 0 or keys[pygame.K_f] or keys[pygame.K_j]
        fire_threshold = 9 if self.has_buff("rapid") else self.fire_threshold
        if self.has_fire_skill and shoot_pressed and len(projectiles) < self.projectile_max and self.fire_timer >= fire_threshold:
            self.fire_timer = 0
            self.fire_buffer_timer = 0
            direction = 1 if self.facing_direction == "right" else -1
            projectile_speed = 11 if self.on_platform else 10
            if aim_up and horizontal_input == 0:
                muzzle_x = self.rect.centerx
                muzzle_y = self.rect.top + 10
                base_vx = 0.0
                base_vy = -12.4
            elif aim_up:
                muzzle_x = self.rect.centerx + direction * (self.width // 2 + 4)
                muzzle_y = self.rect.top + 14
                base_vx = direction * 8.5
                base_vy = -6.8
            else:
                muzzle_x = self.rect.centerx + direction * (self.width // 2 + 8)
                muzzle_y = self.rect.centery + (1 if self.is_jumping else 0)
                base_vx = direction * projectile_speed
                base_vy = 0.0
            burst_offsets = (-0.22, 0.0, 0.22) if self.has_buff("burst") else (0.0,)
            for spread in burst_offsets:
                projectiles.add(
                    Projectile(
                        muzzle_x,
                        muzzle_y,
                        30,
                        22,
                        direction,
                        speed=projectile_speed,
                        color=ORANGE,
                        owner="player",
                        velocity_x=base_vx + spread * 2.4,
                        velocity_y=base_vy + spread * projectile_speed,
                        damage=2,
                        lifetime=128,
                        gravity=0.04,
                        variant="fireball",
                    )
                )
            self.weapon_flash_timer = 8
            self.weapon_recoil = -2.0 * direction
            self.x_vel += self.weapon_recoil * 0.08

        if self.fire_timer < fire_threshold:
            self.fire_timer += 1

        self.try_consume_jump(horizontal_input)
        self.move_and_collide_x(walls)

        jump_held = keys[pygame.K_SPACE]
        can_glide = self.has_double_jumped and not self.on_platform and jump_held and self.y_vel > 0
        if can_glide:
            self.y_vel += self.glide_gravity
            if self.y_vel > self.glide_fall_speed:
                self.y_vel = self.glide_fall_speed
        else:
            self.y_vel += self.gravity
            if self.y_vel > self.max_fall_speed:
                self.y_vel = self.max_fall_speed

        self.move_and_collide_y(walls)
        self.update_wall_slide(walls, horizontal_input)

        token_collisions = pygame.sprite.spritecollide(self, tokens, False)
        for token in token_collisions:
            self.score += token.value
            token.kill()
        pickup_messages = self.collect_pickups(pickups)

        self.handle_enemy_collisions(enemies)
        self.handle_hazard_collisions(hazards)

        if self.rect.y >= level_height + self.height:
            self.dead = True

        if self.rect.x < 0:
            self.rect.x = 0
            self.pos_x = float(self.rect.x)
        elif self.rect.x > level_width - self.width:
            self.rect.x = level_width - self.width
            self.pos_x = float(self.rect.x)
        self.draw()
        return pickup_messages
