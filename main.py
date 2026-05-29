import argparse
import math
import os
from pathlib import Path
import pygame
from settings import *
from Camera import Camera
from level_loader import load_single_level, load_all_levels
from Enemy import Enemy
from Projectile import Projectile
from classes import BuffPickup, DynamicPlatform, FallingPlatform, FakeWall, ToggleWall


HUD_HEIGHT = 210
GAME_VIEWPORT_WIDTH = SCREEN_WIDTH
GAME_VIEWPORT_HEIGHT = SCREEN_HEIGHT - HUD_HEIGHT

LEVEL_THEMES = [
    {"sky_top": (29, 38, 66), "sky_bottom": (10, 16, 28), "far": (42, 56, 84), "near": (58, 78, 112)},
    {"sky_top": (31, 48, 68), "sky_bottom": (10, 21, 31), "far": (44, 74, 92), "near": (74, 114, 126)},
    {"sky_top": (52, 35, 58), "sky_bottom": (20, 14, 28), "far": (82, 52, 84), "near": (124, 70, 108)},
]

PANEL_BG = (16, 22, 34, 218)
PANEL_BORDER = (98, 136, 194)
TEXT_MAIN = (241, 245, 255)
TEXT_MUTED = (178, 191, 214)
TEXT_ACCENT = (255, 221, 114)
TEXT_DANGER = (255, 126, 126)
HEALTH_BG = (49, 58, 74)
HEALTH_FILL = (90, 214, 146)
HEALTH_WARN = (255, 113, 113)
HUD_BG = (8, 13, 22)
HUD_EDGE = (27, 40, 61)
CHINESE_FONT_FILES = ["msyh.ttc", "msyhl.ttc", "simhei.ttf", "simsun.ttc"]
CHINESE_BOLD_FONT_FILES = ["msyhbd.ttc", "simhei.ttf", "simsunb.ttf", "msyh.ttc"]
PET_LEGACY_FRAME_RECTS = [(0, 147, 34, 67), (34, 147, 34, 67), (68, 147, 34, 67), (102, 147, 34, 67), (136, 147, 34, 67), (170, 147, 34, 67)]


def clamp(value, low, high):
    return max(low, min(high, value))


def parse_args():
    parser = argparse.ArgumentParser(description="平台闯关挑战")
    parser.add_argument("--smoke-test", type=int, default=0, help="运行短时自动循环，用于验证程序是否正常启动。")
    return parser.parse_args()


def format_time(milliseconds):
    total_seconds = max(0, milliseconds // 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    tenths = (milliseconds % 1000) // 100
    return f"{minutes:02}:{seconds:02}.{tenths}"


def load_font(size, bold=False):
    font_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = CHINESE_BOLD_FONT_FILES if bold else CHINESE_FONT_FILES
    for font_name in candidates:
        font_path = font_dir / font_name
        if font_path.exists():
            return pygame.font.Font(str(font_path), size)
    return pygame.font.Font(None, size)


def load_pet_frames():
    asset_dir = Path(__file__).with_name("assets")
    ghost_path = asset_dir / "pet_ghost_sheet.png"
    if ghost_path.exists():
        sheet = pygame.image.load(str(ghost_path)).convert_alpha()
        frame_width = max(1, sheet.get_width() // 6)
        frame_height = sheet.get_height()
        frames = []
        for index in range(6):
            frame = pygame.Surface((frame_width, frame_height), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), pygame.Rect(index * frame_width, 0, frame_width, frame_height))
            frames.append(pygame.transform.smoothscale(frame, (58, 58)))
        return frames

    legacy_path = asset_dir / "fire_familiar_sheet.png"
    if not legacy_path.exists():
        return []
    sheet = pygame.image.load(str(legacy_path)).convert_alpha()
    frames = []
    for x, y, w, h in PET_LEGACY_FRAME_RECTS:
        frame = pygame.Surface((w, h), pygame.SRCALPHA)
        frame.blit(sheet, (0, 0), pygame.Rect(x, y, w, h))
        frame.set_colorkey((255, 255, 255))
        frames.append(pygame.transform.smoothscale(frame, (44, 86)))
    return frames


class ChallengeGame:
    def __init__(self, smoke_test_frames=0):
        if smoke_test_frames:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("平台闯关挑战")
        self.clock = pygame.time.Clock()
        self.world_surface = pygame.Surface((GAME_VIEWPORT_WIDTH, GAME_VIEWPORT_HEIGHT))
        self.title_font = load_font(72, bold=True)
        self.heading_font = load_font(34, bold=True)
        self.hud_font = load_font(26, bold=True)
        self.small_font = load_font(21)
        self.tiny_font = load_font(16)
        self.pet_frames = load_pet_frames()
        self.levels = load_all_levels("levels.json")
        self.total_levels = len(self.levels)
        self.smoke_test_frames = smoke_test_frames
        self.reset_runtime_state()
        if not self.smoke_test_frames:
            self.start_new_run()

    def reset_runtime_state(self):
        self.game_state = "menu"
        self.running = True
        self.frame_count = 0
        self.current_level_index = 0
        self.current_level_meta = {}
        self.level_failures = 0
        self.total_deaths = 0
        self.level_start_score = 0
        self.level_start_has_skill = True
        self.level_start_fire_upgrades = {"burst": False, "rapid": False}
        self.checkpoint_score = 0
        self.checkpoint_has_skill = False
        self.checkpoint_fire_upgrades = {"burst": False, "rapid": False}
        self.active_checkpoint_index = None
        self.active_checkpoint_label = "起点"
        self.level_complete_timer = 0
        self.level_complete_title = ""
        self.toast_text = ""
        self.toast_timer = 0
        self.banner_timer = 0
        self.show_help_panel = False
        self.final_time_ms = 0
        self.run_start_ticks = 0
        self.camera = None
        self.projectiles = pygame.sprite.Group()
        self.enemy_projectiles = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.tokens = pygame.sprite.Group()
        self.pickups = pygame.sprite.Group()
        self.hazards = pygame.sprite.Group()
        self.visible_walls = pygame.sprite.Group()
        self.all_walls = []
        self.dynamic_walls = []
        self.checkpoints = []
        self.trigger_zones = []
        self.events = []
        self.pending_events = []
        self.active_encounters = []
        self.trigger_history = set()
        self.exit_zone = None
        self.player = None
        self.active_boss = None
        self.total_level_width = GAME_VIEWPORT_WIDTH
        self.total_level_height = GAME_VIEWPORT_HEIGHT
        self.max_health = 1
        self.encounter_count = 0
        self.level_start_has_skill = True
        self.checkpoint_has_skill = True
        self.phase_label = ""
        self.phase_timer = 0
        self.controls_hint_timer = FPS * 8
        self.help_chip_rect = pygame.Rect(0, 0, 0, 0)
        self.pet_x = 0.0
        self.pet_y = 0.0
        self.pet_frame = 0

    def start_new_run(self):
        self.current_level_index = 0
        self.level_failures = 0
        self.total_deaths = 0
        self.level_start_score = 0
        self.level_start_has_skill = True
        self.level_start_fire_upgrades = {"burst": False, "rapid": False}
        self.checkpoint_score = 0
        self.checkpoint_has_skill = True
        self.checkpoint_fire_upgrades = {"burst": False, "rapid": False}
        self.active_checkpoint_index = None
        self.active_checkpoint_label = "起点"
        self.final_time_ms = 0
        self.encounter_count = 0
        self.show_help_panel = False
        self.controls_hint_timer = FPS * 7
        self.run_start_ticks = pygame.time.get_ticks()
        self.load_level(
            0,
            carry_score=0,
            checkpoint_index=None,
            keep_failures=False,
            show_banner=True,
            has_skill=True,
            fire_upgrades=self.level_start_fire_upgrades,
        )
        self.game_state = "playing"

    def spawn_enemy(self, enemy_data, encounter=None):
        enemy_config = dict(enemy_data)
        enemy = Enemy(
            enemy_config["x"],
            enemy_config["y"],
            enemy_config["width"],
            enemy_config["height"],
            enemy_config.get("speed", 0),
            enemy_config.get("dir", 1),
            enemy_config.get("color", RED),
            enemy_config.get("enemy_type", enemy_config.get("variant", "walker")),
            enemy_config.get("patrol_distance", 140),
            enemy_config.get("hover_amplitude", 36),
            enemy_config.get("hover_speed", 0.1),
            enemy_config.get("health", 2),
            config=enemy_config,
        )
        self.enemies.add(enemy)
        if encounter is not None:
            enemy.encounter_ref = encounter
            encounter["enemies"].append(enemy)
        if getattr(enemy, "is_boss", False):
            self.active_boss = enemy
        return enemy

    def rebuild_visible_walls(self):
        self.visible_walls.empty()
        for wall in self.all_walls:
            if getattr(wall, "visible", True):
                self.visible_walls.add(wall)

    def get_wall_by_tag(self, tag):
        for wall in self.all_walls:
            if getattr(wall, "tag", None) == tag:
                return wall
        return None

    def process_enemy_signals(self):
        for enemy in list(self.enemies):
            if not enemy.alive():
                continue
            if hasattr(enemy, "pop_announcements"):
                for message in enemy.pop_announcements():
                    self.start_phase(message, duration=FPS * 2)
            if hasattr(enemy, "pop_spawn_requests"):
                for spawn_request in enemy.pop_spawn_requests():
                    encounter = getattr(enemy, "encounter_ref", None)
                    self.spawn_enemy(spawn_request, encounter=encounter)
                    self.encounter_count += 1

    def spawn_buff_drop(self, x, y, buff_type="burst", message=None):
        buff_messages = {
            "burst": "三连火种到手",
            "rapid": "急速咏唱已激活",
            "shield": "护体余烬已点亮",
        }
        pickup = BuffPickup(x, y, buff_type=buff_type, message=message or buff_messages.get(buff_type, "力量涌入"), spawn_y=y - 220)
        self.pickups.add(pickup)
        return pickup

    def update_pet_support(self):
        if not self.player or not getattr(self.player, "pet_active", False):
            return
        if self.boss_is_active():
            boss = self.active_boss
            boss_side = 1 if boss.rect.centerx >= self.player.rect.centerx else -1
            target_x = self.player.rect.centerx * 0.72 + boss.rect.centerx * 0.28 + boss_side * 30
            target_y = clamp(self.player.rect.centery - 172, 190, self.player.rect.centery - 116)
            support_interval = 86
        else:
            target_x = self.player.rect.centerx + (156 if self.player.facing_direction == "right" else -156)
            target_y = self.player.rect.centery - 132
            support_interval = 116
        target_x += math.cos(self.frame_count * 0.05) * 6.0
        target_y += math.sin(self.frame_count * 0.09) * 12.0
        if self.pet_x == 0.0 and self.pet_y == 0.0:
            self.pet_x = float(target_x)
            self.pet_y = float(target_y)
        self.pet_x += (target_x - self.pet_x) * 0.14
        self.pet_y += (target_y - self.pet_y) * 0.14
        if self.pet_frames:
            self.pet_frame = (self.frame_count // 8) % len(self.pet_frames)
        if self.player.pet_timer % support_interval == 0:
            living_enemies = [enemy for enemy in self.enemies if enemy.alive()]
            if living_enemies:
                target = min(living_enemies, key=lambda enemy: abs(enemy.rect.centerx - self.pet_x) + abs(enemy.rect.centery - self.pet_y))
                dx = target.rect.centerx - self.pet_x
                dy = target.rect.centery - self.pet_y
                length = max(1.0, math.hypot(dx, dy))
                vx = dx / length * 8.8
                vy = dy / length * 8.8
                self.projectiles.add(
                    Projectile(
                        self.pet_x,
                        self.pet_y,
                        18,
                        18,
                        1 if vx >= 0 else -1,
                        owner="player",
                        color=CYAN,
                        velocity_x=vx,
                        velocity_y=vy,
                        damage=1,
                        lifetime=84,
                        variant="orb",
                    )
                )

    def boss_is_active(self):
        return bool(self.active_boss and self.active_boss.alive())

    def defeat_active_boss(self):
        if not self.boss_is_active():
            return False
        boss = self.active_boss
        boss.shielded = False
        boss.vulnerable_timer = 0
        boss.health = 0
        boss.squished = True
        boss.update(
            self.visible_walls,
            self.tokens,
            self.hazards,
            self.projectiles,
            self.enemy_projectiles,
            self.player,
            self.frame_count,
        )
        self.active_boss = None
        return True

    def cancel_encounter_waves(self, encounter):
        remaining_events = []
        for item in self.pending_events:
            queued_encounter = item.get("event", {}).get("payload", {}).get("encounter")
            if queued_encounter is encounter:
                continue
            remaining_events.append(item)
        self.pending_events = remaining_events

    def load_level(self, level_index, carry_score, checkpoint_index=None, keep_failures=False, show_banner=True, has_skill=False, has_pistol=None, fire_upgrades=None):
        if has_pistol is not None:
            has_skill = has_pistol
        if fire_upgrades is None:
            fire_upgrades = {"burst": False, "rapid": False}
        level = load_single_level(level_index)
        self.current_level_index = level_index
        self.current_level_meta = level
        self.all_walls = level["walls"]
        self.dynamic_walls = [wall for wall in self.all_walls if isinstance(wall, (DynamicPlatform, FallingPlatform, FakeWall, ToggleWall))]
        self.tokens = pygame.sprite.Group(level["tokens"])
        self.pickups = pygame.sprite.Group(level.get("pickups", []))
        self.hazards = pygame.sprite.Group(level["hazards"])
        self.checkpoints = level["checkpoints"]
        self.trigger_zones = level["triggers"]
        self.events = level["events"]
        self.pending_events = []
        self.active_encounters = []
        self.exit_zone = level["exit_zone"]
        self.player = level["player"]
        self.total_level_width = level["level_width"]
        self.total_level_height = level["level_height"]
        self.camera = Camera(self.total_level_width, self.total_level_height, GAME_VIEWPORT_WIDTH, GAME_VIEWPORT_HEIGHT)
        self.projectiles = pygame.sprite.Group()
        self.enemy_projectiles = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.active_boss = None
        for enemy_entry in level["enemy_spawns"]:
            self.spawn_enemy(enemy_entry)
        self.player.score = carry_score
        if has_skill:
            self.player.equip_fire_skill()
        self.player.set_upgrade_state(fire_upgrades)
        self.max_health = max(1, getattr(self.player, "max_health", self.player.health))
        self.trigger_history = set()
        self.phase_label = ""
        self.phase_timer = 0
        self.level_start_has_skill = has_skill
        self.checkpoint_has_skill = has_skill
        self.level_start_fire_upgrades = dict(fire_upgrades)
        self.checkpoint_fire_upgrades = dict(fire_upgrades)
        self.pet_x = 0.0
        self.pet_y = 0.0
        self.pet_frame = 0

        for wall in self.all_walls:
            if isinstance(wall, ToggleWall):
                wall.visible = wall.initial_visible
            if isinstance(wall, FakeWall):
                wall.visible = True
                wall.triggered = False
                wall.timer = 0
            if isinstance(wall, FallingPlatform):
                wall.visible = True
                wall.triggered = False
                wall.falling = False
                wall.timer = 0
                wall.velocity_y = 0.0
                wall.rect.topleft = wall.origin

        if checkpoint_index is not None and self.checkpoints:
            self.active_checkpoint_index = checkpoint_index
            active_checkpoint = self.checkpoints[checkpoint_index]
            for index, checkpoint in enumerate(self.checkpoints):
                checkpoint.set_active(index == checkpoint_index)
            self.player.set_position(*active_checkpoint.spawn_point)
            self.checkpoint_score = carry_score
            self.checkpoint_has_skill = has_skill
            self.checkpoint_fire_upgrades = dict(fire_upgrades)
            self.active_checkpoint_label = active_checkpoint.label
        else:
            self.active_checkpoint_index = None
            self.player.set_position(*level["spawn_point"])
            self.checkpoint_score = carry_score
            self.checkpoint_fire_upgrades = dict(fire_upgrades)
            self.active_checkpoint_label = "起点"

        if not keep_failures:
            self.level_failures = 0
        self.player.grant_respawn_protection()
        self.rebuild_visible_walls()
        self.banner_timer = FPS * 2 if show_banner else 0
        self.controls_hint_timer = FPS * (6 if show_banner else 3)
        self.toast_timer = 0
        self.toast_text = ""

    def restart_level(self):
        checkpoint_index = self.active_checkpoint_index
        carry_score = self.checkpoint_score if checkpoint_index is not None else self.level_start_score
        carry_skill = self.checkpoint_has_skill if checkpoint_index is not None else self.level_start_has_skill
        carry_upgrades = self.checkpoint_fire_upgrades if checkpoint_index is not None else self.level_start_fire_upgrades
        self.load_level(
            self.current_level_index,
            carry_score=carry_score,
            checkpoint_index=checkpoint_index,
            keep_failures=True,
            show_banner=False,
            has_skill=carry_skill,
            fire_upgrades=carry_upgrades,
        )
        self.game_state = "playing"
        if checkpoint_index is not None:
            self.show_toast(f"已在 {self.active_checkpoint_label} 处重生")
        else:
            self.show_toast("已重开当前关卡")

    def show_toast(self, text, duration=FPS * 2):
        self.toast_text = text
        self.toast_timer = duration

    def toggle_help_panel(self):
        self.show_help_panel = not self.show_help_panel
        self.controls_hint_timer = 0
        if self.game_state == "playing":
            self.show_toast("帮助面板已打开" if self.show_help_panel else "帮助面板已隐藏", duration=int(FPS * 0.7))

    def start_phase(self, text, duration=FPS * 2):
        self.phase_label = text
        self.phase_timer = duration
        self.show_toast(text, duration=min(duration, FPS * 2))

    def get_elapsed_time(self):
        if not self.run_start_ticks:
            return 0
        if self.game_state == "victory":
            return self.final_time_ms - self.run_start_ticks
        return pygame.time.get_ticks() - self.run_start_ticks

    def current_theme(self):
        return LEVEL_THEMES[self.current_level_index % len(LEVEL_THEMES)]

    def activate_checkpoint(self, checkpoint_index):
        if checkpoint_index == self.active_checkpoint_index:
            return
        self.active_checkpoint_index = checkpoint_index
        for index, checkpoint in enumerate(self.checkpoints):
            checkpoint.set_active(index == checkpoint_index)
        active_checkpoint = self.checkpoints[checkpoint_index]
        self.checkpoint_score = self.player.score
        self.checkpoint_has_skill = self.player.has_fire_skill
        self.checkpoint_fire_upgrades = self.player.get_upgrade_state()
        self.active_checkpoint_label = active_checkpoint.label
        self.show_toast(f"已激活检查点：{active_checkpoint.label}")

    def advance_level(self):
        self.level_start_score = self.player.score
        carry_skill = self.player.has_fire_skill
        carry_upgrades = self.player.get_upgrade_state()
        next_level_index = self.current_level_index + 1
        if next_level_index >= self.total_levels:
            self.final_time_ms = pygame.time.get_ticks()
            self.game_state = "victory"
            return
        self.load_level(
            next_level_index,
            carry_score=self.level_start_score,
            checkpoint_index=None,
            keep_failures=False,
            show_banner=True,
            has_skill=carry_skill,
            fire_upgrades=carry_upgrades,
        )
        self.game_state = "playing"

    def handle_trigger(self, trigger):
        if trigger.once and trigger.trigger_id in self.trigger_history:
            return
        self.trigger_history.add(trigger.trigger_id)
        trigger.triggered = True
        for event in self.events:
            if event["done"] and event["once"]:
                continue
            if event["trigger"] == trigger.trigger_id:
                if event.get("delay", 0) > 0:
                    self.pending_events.append({"timer": event["delay"], "event": event})
                else:
                    self.run_event(event)

    def start_encounter_from_payload(self, payload, source_event, teleport=None):
        encounter = {
            "enemies": [],
            "unlock_tags": payload.get("unlock_tags", []),
            "reveal_tags": payload.get("reveal_tags", []),
            "clear_message": payload.get("clear_message", "道路已打开"),
            "waves_pending": len(payload.get("waves", [])),
        }
        for tag in payload.get("lock_tags", []):
            wall = self.get_wall_by_tag(tag)
            if wall and isinstance(wall, ToggleWall):
                wall.show()
        if teleport:
            self.player.set_position(teleport["x"], teleport["y"])
            self.projectiles.empty()
            self.enemy_projectiles.empty()
            self.camera.x = clamp(-self.player.rect.centerx + GAME_VIEWPORT_WIDTH // 2, -(self.total_level_width - GAME_VIEWPORT_WIDTH), 0)
            self.camera.y = clamp(-self.player.rect.centery + GAME_VIEWPORT_HEIGHT // 2, -(self.total_level_height - GAME_VIEWPORT_HEIGHT), 0)
            self.camera.camera = pygame.Rect(int(self.camera.x), int(self.camera.y), self.total_level_width, self.total_level_height)
            self.camera.update(self.player)
        for enemy_data in payload.get("enemies", []):
            self.spawn_enemy(enemy_data, encounter=encounter)
        self.rebuild_visible_walls()
        self.encounter_count += len(payload.get("enemies", []))
        self.active_encounters.append(encounter)
        for wave in payload.get("waves", []):
            self.pending_events.append(
                {
                    "timer": wave.get("delay", 0),
                    "event": {
                        "trigger": source_event.get("trigger", ""),
                        "type": "encounter_wave",
                        "once": True,
                        "done": False,
                        "payload": {
                            "encounter": encounter,
                            "enemies": wave.get("enemies", []),
                            "message": wave.get("message", "敌人增援到场"),
                        },
                    },
                }
            )
        self.start_phase(payload.get("message", "遭遇战开始"))

    def run_event(self, event):
        payload = event["payload"]
        event_type = event["type"]
        if event_type == "spawn_enemy":
            self.spawn_enemy(payload["enemy"])
            self.encounter_count += 1
            self.start_phase(payload.get("message", "埋伏怪出现"))
        elif event_type == "spawn_wave":
            for enemy_data in payload.get("enemies", []):
                self.spawn_enemy(enemy_data)
            self.encounter_count += len(payload.get("enemies", []))
            self.start_phase(payload.get("message", "遭遇战开始"))
        elif event_type == "encounter_wave":
            encounter = payload.get("encounter")
            for enemy_data in payload.get("enemies", []):
                self.spawn_enemy(enemy_data, encounter=encounter)
            if encounter is not None:
                encounter["waves_pending"] = max(0, encounter.get("waves_pending", 0) - 1)
            self.encounter_count += len(payload.get("enemies", []))
            self.start_phase(payload.get("message", "敌人增援到场"))
        elif event_type == "toggle_wall":
            wall = self.get_wall_by_tag(payload["tag"])
            if wall:
                if payload.get("visible", True):
                    wall.show()
                else:
                    wall.hide()
                self.rebuild_visible_walls()
                self.start_phase(payload.get("message", "地形已变化"), duration=FPS * 2)
        elif event_type == "drop_platform":
            wall = self.get_wall_by_tag(payload["tag"])
            if wall and isinstance(wall, FallingPlatform):
                wall.trigger()
                self.start_phase(payload.get("message", "脚下平台开始崩塌"), duration=FPS * 2)
        elif event_type == "break_fake_wall":
            wall = self.get_wall_by_tag(payload["tag"])
            if wall and isinstance(wall, FakeWall):
                wall.trigger()
                self.start_phase(payload.get("message", "假墙消失了"), duration=FPS * 2)
        elif event_type == "set_hint":
            self.start_phase(payload.get("message", "阶段变化"), duration=payload.get("duration", FPS * 2))
        elif event_type == "drop_buff":
            self.spawn_buff_drop(payload["x"], payload["y"], buff_type=payload.get("buff_type", "burst"), message=payload.get("message"))
            self.start_phase(payload.get("message", "强化掉落已落地"), duration=FPS * 2)
        elif event_type == "start_encounter":
            self.start_encounter_from_payload(payload, event)
        elif event_type == "start_boss_room":
            self.start_encounter_from_payload(payload, event, teleport=payload.get("teleport"))
        event["done"] = True

    def update_dynamic_objects(self):
        changed = False
        for wall in self.dynamic_walls:
            if isinstance(wall, DynamicPlatform):
                wall.update()
            elif isinstance(wall, FallingPlatform):
                visible_before = wall.visible
                wall.update()
                if visible_before != wall.visible:
                    changed = True
            elif isinstance(wall, FakeWall):
                visible_before = wall.visible
                wall.update()
                if visible_before != wall.visible:
                    changed = True
        if changed:
            self.rebuild_visible_walls()

    def update_triggers(self):
        for trigger in self.trigger_zones:
            if trigger.once and trigger.triggered:
                continue
            if self.player.rect.colliderect(trigger.rect):
                self.handle_trigger(trigger)

    def update_playing(self):
        self.update_dynamic_objects()
        if self.pending_events:
            remaining = []
            for item in self.pending_events:
                item["timer"] -= 1
                if item["timer"] <= 0:
                    self.run_event(item["event"])
                else:
                    remaining.append(item)
            self.pending_events = remaining
        if self.active_encounters:
            remaining_encounters = []
            for encounter in self.active_encounters:
                if any(getattr(enemy, "is_boss", False) and not enemy.alive() for enemy in encounter["enemies"]):
                    encounter["waves_pending"] = 0
                    self.cancel_encounter_waves(encounter)
                    for tag in encounter["unlock_tags"]:
                        wall = self.get_wall_by_tag(tag)
                        if wall and isinstance(wall, ToggleWall):
                            wall.hide()
                    for tag in encounter["reveal_tags"]:
                        wall = self.get_wall_by_tag(tag)
                        if wall and isinstance(wall, ToggleWall):
                            wall.show()
                    self.rebuild_visible_walls()
                    self.start_phase(encounter["clear_message"])
                    continue
                if encounter.get("waves_pending", 0) > 0 or any(enemy.alive() for enemy in encounter["enemies"]):
                    remaining_encounters.append(encounter)
                    continue
                for tag in encounter["unlock_tags"]:
                    wall = self.get_wall_by_tag(tag)
                    if wall and isinstance(wall, ToggleWall):
                        wall.hide()
                for tag in encounter["reveal_tags"]:
                    wall = self.get_wall_by_tag(tag)
                    if wall and isinstance(wall, ToggleWall):
                        wall.show()
                self.rebuild_visible_walls()
                self.start_phase(encounter["clear_message"])
            self.active_encounters = remaining_encounters
        pickup_messages = self.player.update(
            self.visible_walls,
            self.enemies,
            self.tokens,
            self.pickups,
            self.hazards,
            self.projectiles,
            self.total_level_width,
            self.total_level_height,
        )
        if pickup_messages:
            self.level_start_has_skill = self.player.has_fire_skill or self.level_start_has_skill
            self.level_start_fire_upgrades = self.player.get_upgrade_state()
            self.checkpoint_fire_upgrades = self.player.get_upgrade_state()
            for message in pickup_messages:
                self.show_toast(message)
            self.start_phase("火球术已觉醒", duration=FPS * 2)
        self.enemies.update(
            self.visible_walls,
            self.tokens,
            self.hazards,
            self.projectiles,
            self.enemy_projectiles,
            self.player,
            self.frame_count,
        )
        self.process_enemy_signals()
        self.update_pet_support()
        if self.active_boss and not self.active_boss.alive():
            self.active_boss = None
        self.projectiles.update(self.visible_walls, self.enemies, self.projectiles, None)
        self.enemy_projectiles.update(self.visible_walls, self.enemies, self.enemy_projectiles, self.player)
        self.update_triggers()
        if self.boss_is_active():
            focus_rect = self.player.rect.copy()
            focus_rect.centerx = int(self.player.rect.centerx * 0.56 + self.active_boss.rect.centerx * 0.44)
            focus_rect.centery = int(self.player.rect.centery * 0.68 + self.active_boss.rect.centery * 0.32)
            focus_target = type("FocusTarget", (), {"rect": focus_rect})()
            self.camera.update(focus_target)
        else:
            self.camera.update(self.player)

        for wall in self.dynamic_walls:
            if isinstance(wall, FallingPlatform) and wall.visible and self.player.rect.colliderect(wall.rect) and self.player.rect.bottom <= wall.rect.top + 16:
                wall.trigger()

        for index, checkpoint in enumerate(self.checkpoints):
            if self.player.rect.colliderect(checkpoint.rect):
                self.activate_checkpoint(index)

        if self.exit_zone and self.player.rect.colliderect(self.exit_zone.rect):
            self.level_complete_title = f"{self.current_level_meta['name']}通关"
            self.level_complete_timer = int(FPS * 0.8)
            self.game_state = "transition"
            return

        if self.player.dead and getattr(self.player, "god_mode", False):
            self.player.dead = False
            self.player.health = self.player.max_health
        if self.player.dead:
            self.total_deaths += 1
            self.level_failures += 1
            self.game_state = "dead"

        if self.phase_timer > 0:
            self.phase_timer -= 1
            if self.phase_timer <= 0:
                self.phase_label = ""

    def update_transition(self):
        self.level_complete_timer -= 1
        if self.level_complete_timer <= 0:
            self.advance_level()

    def update_animated_objects(self):
        if self.exit_zone:
            self.exit_zone.animate(self.frame_count)
        for checkpoint in self.checkpoints:
            checkpoint.animate(self.frame_count)

    def draw_vertical_gradient(self, surface, top_color, bottom_color):
        width, height = surface.get_size()
        for y in range(height):
            ratio = y / max(1, height - 1)
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
            pygame.draw.line(surface, (r, g, b), (0, y), (width, y))

    def draw_background(self, surface):
        theme = self.current_theme()
        self.draw_vertical_gradient(surface, theme["sky_top"], theme["sky_bottom"])
        for layer_index, (color, speed, base_height, amplitude) in enumerate(
            ((theme["far"], 0.18, GAME_VIEWPORT_HEIGHT * 0.7, 34), (theme["near"], 0.34, GAME_VIEWPORT_HEIGHT * 0.82, 48))
        ):
            points = [(0, GAME_VIEWPORT_HEIGHT)]
            step = 120
            offset = (self.camera.x * speed) if self.camera else 0
            for x in range(-step, GAME_VIEWPORT_WIDTH + step * 2, step):
                wave = math.sin((x - offset) * 0.01 + layer_index * 1.2) * amplitude
                ridge_y = int(base_height + wave + ((x // step) % 2) * 18)
                points.append((x, ridge_y))
            points.append((GAME_VIEWPORT_WIDTH, GAME_VIEWPORT_HEIGHT))
            pygame.draw.polygon(surface, color, points)

    def draw_panel(self, surface, rect, radius=16):
        panel_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(panel_surface, PANEL_BG, panel_surface.get_rect(), border_radius=radius)
        pygame.draw.rect(panel_surface, PANEL_BORDER, panel_surface.get_rect(), width=2, border_radius=radius)
        surface.blit(panel_surface, rect.topleft)

    def wrap_text(self, text, font, max_width, max_lines=2):
        if not text:
            return [""]
        lines = []
        current = ""
        for char in text:
            test_line = current + char
            if current and font.size(test_line)[0] > max_width:
                lines.append(current)
                current = char
                if len(lines) >= max_lines - 1:
                    break
            else:
                current = test_line
        if len(lines) < max_lines and current:
            lines.append(current)

        remainder = text[len("".join(lines)) :]
        if remainder and lines:
            trimmed = lines[-1]
            while trimmed and font.size(trimmed + "...")[0] > max_width:
                trimmed = trimmed[:-1]
            lines[-1] = trimmed + "..."
        return lines or [text[:max_width]]

    def draw_center_overlay(self, title, subtitle_lines, accent=TEXT_ACCENT):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((5, 10, 18, 160))
        self.screen.blit(overlay, (0, 0))
        panel_rect = pygame.Rect(0, 0, 860, 340)
        panel_rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.draw_panel(self.screen, panel_rect, radius=22)
        title_surface = self.title_font.render(title, True, accent)
        self.screen.blit(title_surface, (panel_rect.centerx - title_surface.get_width() // 2, panel_rect.y + 36))
        y = panel_rect.y + 130
        for line in subtitle_lines:
            line_surface = self.heading_font.render(line, True, TEXT_MAIN if line == subtitle_lines[0] else TEXT_MUTED)
            self.screen.blit(line_surface, (panel_rect.centerx - line_surface.get_width() // 2, y))
            y += 46

    def draw_banner(self):
        if self.banner_timer <= 0:
            return
        banner_rect = pygame.Rect(0, 0, 560, 70)
        banner_rect.center = (SCREEN_WIDTH // 2, HUD_HEIGHT + 42)
        self.draw_panel(self.screen, banner_rect, radius=16)
        title = self.hud_font.render(self.current_level_meta["name"], True, TEXT_MAIN)
        subtitle = self.small_font.render(self.current_level_meta["subtitle"], True, TEXT_MUTED)
        self.screen.blit(title, (banner_rect.centerx - title.get_width() // 2, banner_rect.y + 10))
        self.screen.blit(subtitle, (banner_rect.centerx - subtitle.get_width() // 2, banner_rect.y + 42))
        self.banner_timer -= 1

    def draw_toast(self):
        if self.toast_timer <= 0 or not self.toast_text:
            return
        toast_rect = pygame.Rect(0, 0, 420, 48)
        toast_rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 42)
        self.draw_panel(self.screen, toast_rect, radius=14)
        toast_surface = self.small_font.render(self.toast_text, True, TEXT_MAIN)
        self.screen.blit(toast_surface, (toast_rect.centerx - toast_surface.get_width() // 2, toast_rect.y + 12))
        self.toast_timer -= 1

    def draw_focus_hint(self):
        if self.game_state != "playing":
            return
        if pygame.key.get_focused() and self.controls_hint_timer <= 0:
            return

        if pygame.key.get_focused():
            message = "A/D 移动  空格跳跃  W 上瞄  H 帮助"
        else:
            message = "点击游戏窗口后，再用键盘操作"

        hint_rect = pygame.Rect(0, 0, 384, 42)
        hint_rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 38)
        self.draw_panel(self.screen, hint_rect, radius=12)
        hint_surface = self.tiny_font.render(message, True, TEXT_ACCENT)
        self.screen.blit(hint_surface, (hint_rect.centerx - hint_surface.get_width() // 2, hint_rect.y + 12))
        if pygame.key.get_focused() and self.controls_hint_timer > 0:
            self.controls_hint_timer -= 1

    def draw_hud(self):
        if not self.player:
            return
        pygame.draw.rect(self.screen, HUD_BG, (0, 0, SCREEN_WIDTH, HUD_HEIGHT))
        pygame.draw.rect(self.screen, HUD_EDGE, (0, HUD_HEIGHT - 2, SCREEN_WIDTH, 2))
        stage_rect = pygame.Rect(24, 18, 318, 96)
        status_rect = pygame.Rect(360, 18, 240, 96)
        score_rect = pygame.Rect(618, 18, 438, 96)
        hint_rect = pygame.Rect(24, 128, 1032, 42)
        progress_rect = pygame.Rect(24, 184, 1032, 16)
        chip_rect = pygame.Rect(score_rect.right - 102, score_rect.y + 16, 78, 30)
        self.help_chip_rect = chip_rect.copy()
        for rect in (stage_rect, status_rect, score_rect, hint_rect):
            self.draw_panel(self.screen, rect, radius=12)

        stage_label = self.small_font.render(f"第 {self.current_level_index + 1} / {self.total_levels} 关", True, TEXT_MUTED)
        stage_title = self.hud_font.render(self.current_level_meta["name"], True, TEXT_MAIN)
        stage_subtitle = self.small_font.render(self.current_level_meta["subtitle"], True, TEXT_MUTED)
        self.screen.blit(stage_label, (stage_rect.x + 22, stage_rect.y + 14))
        self.screen.blit(stage_title, (stage_rect.x + 22, stage_rect.y + 42))
        self.screen.blit(stage_subtitle, (stage_rect.x + 22, stage_rect.y + 72))

        timer_label = self.small_font.render("用时", True, TEXT_MUTED)
        timer_value = self.heading_font.render(format_time(self.get_elapsed_time()), True, TEXT_MAIN)
        death_value = self.small_font.render(f"死亡 {self.total_deaths}", True, TEXT_MUTED)
        target_time = self.tiny_font.render(f"目标 {self.current_level_meta.get('time_par', '--:--')}", True, TEXT_MUTED)
        self.screen.blit(timer_label, (status_rect.x + 22, status_rect.y + 14))
        self.screen.blit(timer_value, (status_rect.x + 22, status_rect.y + 42))
        self.screen.blit(death_value, (status_rect.x + 22, status_rect.y + 74))
        self.screen.blit(target_time, (status_rect.right - target_time.get_width() - 22, status_rect.y + 76))

        score_label = self.small_font.render(f"得分 {self.player.score}", True, TEXT_MAIN)
        checkpoint_label = self.tiny_font.render(f"检查点：{self.active_checkpoint_label}", True, TEXT_MUTED)
        phase_text = self.phase_label if self.phase_label else "当前阶段稳定"
        phase_surface = self.tiny_font.render(phase_text, True, TEXT_ACCENT if self.phase_label else TEXT_MUTED)
        weapon_text = "技能 火球术" if self.player.has_fire_skill else "技能 未觉醒"
        weapon_surface = self.tiny_font.render(weapon_text, True, TEXT_ACCENT if self.player.has_fire_skill else TEXT_MUTED)
        reload_text = "火球就绪" if self.player.weapon_ready_ratio() >= 1.0 else "凝聚中"
        reload_surface = self.tiny_font.render(reload_text, True, TEXT_ACCENT if self.player.weapon_ready_ratio() >= 1.0 else TEXT_MUTED)
        event_surface = self.tiny_font.render(f"事件 {self.encounter_count}", True, TEXT_MUTED)
        god_surface = self.tiny_font.render("无敌 ON" if getattr(self.player, "god_mode", False) else "无敌 OFF", True, TEXT_ACCENT if getattr(self.player, "god_mode", False) else TEXT_MUTED)
        self.screen.blit(score_label, (score_rect.x + 22, score_rect.y + 14))
        self.screen.blit(checkpoint_label, (score_rect.x + 22, score_rect.y + 44))
        self.screen.blit(phase_surface, (score_rect.x + 22, score_rect.y + 72))
        self.screen.blit(event_surface, (score_rect.x + 166, score_rect.y + 18))
        self.screen.blit(weapon_surface, (score_rect.x + 244, score_rect.y + 18))
        self.screen.blit(reload_surface, (score_rect.x + 244, score_rect.y + 46))
        self.screen.blit(god_surface, (score_rect.x + 338, score_rect.y + 46))
        self.draw_panel(self.screen, chip_rect, radius=8)
        chip_text = self.tiny_font.render("H 帮助" if not self.show_help_panel else "H 收起", True, TEXT_ACCENT if not self.show_help_panel else TEXT_MAIN)
        self.screen.blit(chip_text, (chip_rect.centerx - chip_text.get_width() // 2, chip_rect.y + 7))

        bar_x = score_rect.x + 244
        bar_y = score_rect.y + 76
        bar_w = score_rect.right - bar_x - 18
        bar_h = 8
        pygame.draw.rect(self.screen, HEALTH_BG, (bar_x, bar_y, bar_w, bar_h), border_radius=6)
        health_ratio = max(0.0, min(1.0, self.player.health / self.max_health))
        fill_color = HEALTH_FILL if health_ratio > 0.35 else HEALTH_WARN
        pygame.draw.rect(self.screen, fill_color, (bar_x, bar_y, int(bar_w * health_ratio), bar_h), border_radius=6)
        pygame.draw.rect(self.screen, WHITE, (bar_x, bar_y, bar_w, bar_h), width=2, border_radius=6)
        reload_bar_w = 164
        reload_bar_x = score_rect.x + 244
        reload_bar_y = score_rect.y + 64
        pygame.draw.rect(self.screen, HEALTH_BG, (reload_bar_x, reload_bar_y, reload_bar_w, 6), border_radius=4)
        pygame.draw.rect(
            self.screen,
            TEXT_ACCENT,
            (reload_bar_x, reload_bar_y, int(reload_bar_w * self.player.weapon_ready_ratio()), 6),
            border_radius=4,
        )

        if self.level_failures >= 3:
            hint_text = self.current_level_meta["failure_hint"]
        else:
            hint_text = self.phase_label if self.phase_label else self.current_level_meta["tip"]
        hint_label = self.tiny_font.render("提示", True, TEXT_ACCENT if self.phase_label else TEXT_MUTED)
        hint_lines = self.wrap_text(hint_text, self.small_font, hint_rect.width - 120, max_lines=1)
        hint_surface = self.small_font.render(hint_lines[0], True, TEXT_MAIN if self.phase_label else TEXT_MUTED)
        self.screen.blit(hint_label, (hint_rect.x + 22, hint_rect.y + 11))
        self.screen.blit(hint_surface, (hint_rect.x + 82, hint_rect.y + 8))

        self.draw_panel(self.screen, progress_rect, radius=10)
        inner_rect = progress_rect.inflate(-10, -8)
        pygame.draw.rect(self.screen, HEALTH_BG, inner_rect, border_radius=8)
        progress_ratio = 0.0
        if self.total_level_width > self.player.width:
            progress_ratio = self.player.rect.centerx / (self.total_level_width - self.player.width)
        progress_ratio = max(0.0, min(1.0, progress_ratio))
        fill_width = max(12, int(inner_rect.width * progress_ratio))
        pygame.draw.rect(self.screen, TEXT_ACCENT, (inner_rect.x, inner_rect.y, fill_width, inner_rect.height), border_radius=8)
        pygame.draw.circle(self.screen, WHITE, (inner_rect.x + fill_width, inner_rect.centery), 6)
        progress_text = self.tiny_font.render("起点", True, TEXT_MUTED)
        finish_text = self.tiny_font.render("终点", True, TEXT_MUTED)
        self.screen.blit(progress_text, (progress_rect.x + 4, progress_rect.y - 22))
        self.screen.blit(finish_text, (progress_rect.right - finish_text.get_width() - 4, progress_rect.y - 22))

        if self.show_help_panel:
            self.draw_help_panel()

    def draw_boss_bar(self):
        if not self.boss_is_active():
            return

        boss = self.active_boss
        panel_rect = pygame.Rect(168, HUD_HEIGHT + 12, SCREEN_WIDTH - 336, 80)
        self.draw_panel(self.screen, panel_rect, radius=14)

        title_surface = self.small_font.render(boss.boss_name, True, TEXT_MAIN)
        phase_surface = self.tiny_font.render(boss.get_phase_name(), True, TEXT_DANGER if boss.shielded else HEALTH_FILL)
        state_text = "护盾在线，先点掉外侧节点" if boss.shielded else f"核心暴露 {max(0, boss.vulnerable_timer // FPS)}s"
        state_surface = self.tiny_font.render(state_text, True, TEXT_MUTED if boss.shielded else HEALTH_FILL)
        self.screen.blit(title_surface, (panel_rect.x + 16, panel_rect.y + 10))
        self.screen.blit(phase_surface, (panel_rect.right - phase_surface.get_width() - 16, panel_rect.y + 12))
        self.screen.blit(state_surface, (panel_rect.x + 16, panel_rect.y + 34))

        bar_rect = pygame.Rect(panel_rect.x + 16, panel_rect.y + 56, panel_rect.width - 32, 12)
        pygame.draw.rect(self.screen, HEALTH_BG, bar_rect, border_radius=6)
        fill_width = int(bar_rect.width * max(0.0, min(1.0, boss.health_ratio())))
        pygame.draw.rect(self.screen, TEXT_DANGER, (bar_rect.x, bar_rect.y, fill_width, bar_rect.height), border_radius=6)
        pygame.draw.rect(self.screen, WHITE, bar_rect, width=2, border_radius=6)

        node_x = panel_rect.right - 106
        node_y = panel_rect.y + 38
        for index, node in enumerate(getattr(boss, "shield_nodes", [])):
            center = (node_x + index * 28, node_y)
            if node["health"] > 0:
                node_color = TEXT_ACCENT if node["name"] == "top" else CYAN
                pygame.draw.circle(self.screen, node_color, center, 8)
                pygame.draw.circle(self.screen, WHITE, center, 8, 2)
            else:
                pygame.draw.circle(self.screen, HEALTH_BG, center, 8)
                pygame.draw.circle(self.screen, TEXT_MUTED, center, 8, 2)

    def draw_help_panel(self):
        if self.game_state in ("paused", "dead"):
            panel_rect = pygame.Rect(84, 448, 360, 206)
        else:
            panel_rect = pygame.Rect(40, HUD_HEIGHT + 84, 388, 206)
        self.draw_panel(self.screen, panel_rect, radius=14)
        title = self.small_font.render("操作说明", True, TEXT_MAIN)
        lines = [
            "移动：A / D / 左右方向键",
            "跳跃：空格",
            "上瞄：W / 上方向键",
            "二段跳：空中再按一次空格",
            "滑翔：长按空格缓降",
            "火球：F / J",
            "无敌开关：U",
            "秒杀 Boss：T",
            "重试：Enter / R",
            "暂停 / 帮助：P / Esc / H",
        ]
        self.screen.blit(title, (panel_rect.x + 14, panel_rect.y + 12))
        y = panel_rect.y + 42
        for line in lines:
            line_surface = self.tiny_font.render(line, True, TEXT_MUTED)
            self.screen.blit(line_surface, (panel_rect.x + 14, y))
            y += 19

    def draw_pet(self):
        if not self.player or not getattr(self.player, "pet_active", False):
            return
        if self.pet_frames:
            frame = self.pet_frames[self.pet_frame % len(self.pet_frames)]
            center_x = int(self.pet_x + self.camera.camera.x)
            center_y = int(self.pet_y + self.camera.camera.y)
            glow_radius = max(frame.get_width(), frame.get_height()) // 2 + 10
            glow_surface = pygame.Surface((glow_radius * 2 + 12, glow_radius * 2 + 12), pygame.SRCALPHA)
            pygame.draw.circle(
                glow_surface,
                (94, 226, 255, 54),
                (glow_surface.get_width() // 2, glow_surface.get_height() // 2),
                glow_radius,
            )
            self.world_surface.blit(glow_surface, (center_x - glow_surface.get_width() // 2, center_y - glow_surface.get_height() // 2))
            draw_x = center_x - frame.get_width() // 2
            draw_y = center_y - frame.get_height() // 2
            self.world_surface.blit(frame, (draw_x, draw_y))
        else:
            pet_rect = pygame.Rect(0, 0, 22, 22)
            pet_rect.center = (int(self.pet_x), int(self.pet_y))
            draw_rect = pet_rect.move(self.camera.camera.topleft)
            pygame.draw.circle(self.world_surface, (255, 156, 72), draw_rect.center, 9)
            pygame.draw.circle(self.world_surface, (255, 226, 124), draw_rect.center, 5)
            pygame.draw.circle(self.world_surface, WHITE, (draw_rect.centerx - 2, draw_rect.centery - 2), 2)

    def draw_world(self):
        self.update_animated_objects()
        self.draw_background(self.world_surface)
        if self.exit_zone:
            self.world_surface.blit(self.exit_zone.image, self.camera.apply(self.exit_zone))
        for wall in self.visible_walls:
            self.world_surface.blit(wall.image, self.camera.apply(wall))
        for checkpoint in self.checkpoints:
            self.world_surface.blit(checkpoint.image, self.camera.apply(checkpoint))
        for hazard in self.hazards:
            self.world_surface.blit(hazard.image, self.camera.apply(hazard))
        for enemy in self.enemies:
            self.world_surface.blit(enemy.image, self.camera.apply(enemy))
        for projectile in self.enemy_projectiles:
            self.world_surface.blit(projectile.image, self.camera.apply(projectile))
        for pickup in self.pickups:
            self.world_surface.blit(pickup.image, self.camera.apply(pickup))
        for token in self.tokens:
            self.world_surface.blit(token.image, self.camera.apply(token))
        for projectile in self.projectiles:
            self.world_surface.blit(projectile.image, self.camera.apply(projectile))
        self.draw_pet()
        self.world_surface.blit(self.player.image, self.camera.apply(self.player))
        self.screen.blit(self.world_surface, (0, HUD_HEIGHT))
        self.draw_hud()
        self.draw_boss_bar()
        self.draw_banner()
        self.draw_toast()
        self.draw_focus_hint()

    def draw_world_base(self):
        help_was_visible = self.show_help_panel
        banner_timer = self.banner_timer
        self.show_help_panel = False
        self.banner_timer = 0
        self.draw_world()
        self.show_help_panel = help_was_visible
        self.banner_timer = banner_timer

    def draw_menu(self):
        self.draw_background(self.world_surface)
        self.screen.blit(self.world_surface, (0, HUD_HEIGHT))
        pygame.draw.rect(self.screen, HUD_BG, (0, 0, SCREEN_WIDTH, HUD_HEIGHT))
        pygame.draw.rect(self.screen, HUD_EDGE, (0, HUD_HEIGHT - 2, SCREEN_WIDTH, 2))
        if self.show_help_panel:
            self.draw_center_overlay(
                "操作说明",
                [
                    "A/D 移动，空格跳跃，空中再跳一次可二段跳",
                    "按 F/J 投掷火球，按住 W 可朝上轰击",
                    "Enter 或鼠标点击开始挑战",
                ],
            )
        else:
            self.draw_center_overlay(
                "平台闯关挑战",
                [
                    "三关重制：热身、压迫路线、最终 Boss 战",
                    "按 Enter 或点击画面开始",
                    "按 H 查看操作说明",
                ],
            )

    def draw_dead(self):
        self.draw_world_base()
        lines = [
            f"将从 {self.active_checkpoint_label} 重新出发",
            "按 Enter 或 R 再试一次",
            self.current_level_meta["failure_hint"] if self.level_failures >= 3 else "按 Esc 退出本轮挑战",
        ]
        self.draw_center_overlay("挑战失败", lines, accent=TEXT_DANGER)
        if self.show_help_panel:
            self.draw_help_panel()

    def draw_paused(self):
        self.draw_world_base()
        self.draw_center_overlay("已暂停", ["按 P 或 Esc 继续", "按 R 重开本关   按 H 查看操作"])
        if self.show_help_panel:
            self.draw_help_panel()

    def draw_transition(self):
        self.draw_world()
        self.draw_center_overlay(self.level_complete_title, ["准备进入下一关"], accent=HEALTH_FILL)

    def draw_victory(self):
        self.draw_world()
        clear_time = format_time(self.final_time_ms - self.run_start_ticks)
        self.draw_center_overlay(
            "挑战完成",
            [
                f"得分 {self.player.score}   用时 {clear_time}",
                f"死亡 {self.total_deaths} 次   触发事件 {self.encounter_count}",
                "按 Enter 开始新一轮挑战",
            ],
            accent=TEXT_ACCENT,
        )

    def draw(self):
        self.screen.fill(BLACK)
        if self.game_state == "menu":
            self.draw_menu()
        elif self.game_state == "playing":
            self.draw_world()
        elif self.game_state == "paused":
            self.draw_paused()
        elif self.game_state == "dead":
            self.draw_dead()
        elif self.game_state == "transition":
            self.draw_transition()
        elif self.game_state == "victory":
            self.draw_victory()

    def update(self):
        if self.game_state == "playing":
            self.update_playing()
        elif self.game_state == "transition":
            self.update_transition()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.game_state == "menu":
                    self.start_new_run()
                elif self.help_chip_rect.collidepoint(event.pos) and self.game_state in ("playing", "paused", "dead"):
                    self.toggle_help_panel()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.game_state == "playing":
                        self.game_state = "paused"
                    elif self.game_state == "paused":
                        self.game_state = "playing"
                    else:
                        self.running = False
                elif event.key == pygame.K_p and self.game_state in ("playing", "paused"):
                    self.game_state = "paused" if self.game_state == "playing" else "playing"
                elif event.key == pygame.K_h and self.game_state in ("menu", "playing", "paused", "dead"):
                    self.toggle_help_panel()
                elif event.key == pygame.K_u and self.game_state == "playing":
                    self.player.god_mode = not getattr(self.player, "god_mode", False)
                    if self.player.god_mode:
                        self.player.health = self.player.max_health
                        self.player.dead = False
                        self.show_toast("无敌已开启", duration=FPS)
                    else:
                        self.show_toast("无敌已关闭", duration=FPS)
                elif event.key == pygame.K_t and self.game_state == "playing":
                    if self.defeat_active_boss():
                        self.show_toast("Boss 已被秒杀", duration=FPS)
                elif event.key == pygame.K_RETURN:
                    if self.game_state == "menu":
                        self.start_new_run()
                    elif self.game_state == "dead":
                        self.restart_level()
                    elif self.game_state == "victory":
                        self.start_new_run()
                elif event.key in (pygame.K_f, pygame.K_j) and self.game_state == "playing":
                    self.player.queue_fire()
                elif event.key == pygame.K_SPACE and self.game_state == "playing":
                    self.player.queue_jump()
                elif event.key == pygame.K_r and self.game_state in ("playing", "paused", "dead"):
                    self.restart_level()

    def run(self):
        if self.smoke_test_frames:
            self.start_new_run()
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)
            self.frame_count += 1
            if self.smoke_test_frames and self.frame_count >= self.smoke_test_frames:
                break
        pygame.quit()


def main():
    args = parse_args()
    game = ChallengeGame(smoke_test_frames=args.smoke_test)
    game.run()
    if args.smoke_test:
        print("冒烟测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
