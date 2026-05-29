import json
from pathlib import Path

from settings import *
from Player import Player
from classes import (
    Wall,
    Token,
    Hazard,
    ExitZone,
    Checkpoint,
    DynamicPlatform,
    FallingPlatform,
    FakeWall,
    ToggleWall,
    TriggerZone,
    FireSkillPickup,
    BuffPickup,
)

LEVEL_FILE = Path(__file__).with_name("levels.json")
levels = []
level_data = None


def read_level_data(filename=None):
    if filename:
        path = Path(filename)
        if not path.is_absolute():
            path = LEVEL_FILE.parent / path
    else:
        path = LEVEL_FILE
    with path.open("r", encoding="utf-8") as level_file:
        return json.load(level_file)


level_data = read_level_data()


def build_wall(entry):
    wall_type = entry.get("type", "wall")
    if wall_type == "dynamic_platform":
        return DynamicPlatform(
            entry["x"],
            entry["y"],
            entry["width"],
            entry["height"],
            color=entry.get("color", CYAN),
            movement=entry.get("movement", "horizontal"),
            distance=entry.get("distance", 120),
            speed=entry.get("speed", 2.0),
            start_offset=entry.get("start_offset", 0),
            phase=entry.get("phase", 0.0),
            tag=entry.get("tag"),
        )
    if wall_type == "falling_platform":
        return FallingPlatform(
            entry["x"],
            entry["y"],
            entry["width"],
            entry["height"],
            color=entry.get("color", ORANGE),
            delay=entry.get("delay", 35),
            respawn_time=entry.get("respawn_time", 150),
            tag=entry.get("tag"),
        )
    if wall_type == "fake_wall":
        return FakeWall(
            entry["x"],
            entry["y"],
            entry["width"],
            entry["height"],
            color=entry.get("color", PURPLE),
            tag=entry.get("tag"),
        )
    if wall_type == "toggle_wall":
        return ToggleWall(
            entry["x"],
            entry["y"],
            entry["width"],
            entry["height"],
            color=entry.get("color", BLUE),
            tag=entry.get("tag"),
            initial_visible=entry.get("visible", False),
        )
    return Wall(
        entry["x"],
        entry["y"],
        entry["width"],
        entry["height"],
        entry.get("color", BLUE),
        tag=entry.get("tag"),
    )


def build_event(entry):
    event_type = entry.get("type", "spawn_enemy")
    return {
        "trigger": entry["trigger"],
        "type": event_type,
        "once": entry.get("once", True),
        "done": False,
        "delay": entry.get("delay", 0),
        "timer": 0,
        "payload": entry,
    }


def build_pickup(entry):
    pickup_type = entry.get("type", "fire_skill")
    if pickup_type in ("fire_skill", "pistol"):
        return FireSkillPickup(
            entry["x"],
            entry["y"],
            width=entry.get("width", 52),
            height=entry.get("height", 42),
            message=entry.get("message", "获得火球术，按 F / J 向前投掷"),
        )
    if pickup_type == "buff":
        return BuffPickup(
            entry["x"],
            entry["y"],
            buff_type=entry.get("buff_type", "burst"),
            width=entry.get("width", 44),
            height=entry.get("height", 44),
            message=entry.get("message", "力量涌入"),
            spawn_y=entry.get("spawn_y"),
        )
    return None


def load_level(level):
    walls = []
    enemies = []
    tokens = []
    pickups = []
    hazards = []
    checkpoints = []
    trigger_zones = []
    events = []

    player_config = level["player"][0]
    player = Player(player_config["x"], player_config["y"], player_config["width"], player_config["height"])

    for wall_entry in level.get("walls", []):
        walls.append(build_wall(wall_entry))
    for enemy_entry in level.get("enemies", []):
        enemies.append(enemy_entry)
    for token_entry in level.get("tokens", []):
        tokens.append(
            Token(
                token_entry["x"],
                token_entry["y"],
                token_entry["width"],
                token_entry["height"],
                token_entry.get("color", PURPLE),
                token_entry.get("value", 10),
            )
        )
    for pickup_entry in level.get("pickups", []):
        pickup = build_pickup(pickup_entry)
        if pickup:
            pickups.append(pickup)
    for hazard_entry in level.get("hazards", []):
        hazards.append(
            Hazard(
                hazard_entry["x"],
                hazard_entry["y"],
                hazard_entry["width"],
                hazard_entry["height"],
                hazard_entry.get("color", GREY),
                hazard_entry.get("direction", "up"),
            )
        )
    for checkpoint_entry in level.get("checkpoints", []):
        checkpoints.append(
            Checkpoint(
                checkpoint_entry["x"],
                checkpoint_entry["y"],
                checkpoint_entry["width"],
                checkpoint_entry["height"],
                checkpoint_entry["spawn_x"],
                checkpoint_entry["spawn_y"],
                checkpoint_entry.get("label", "检查点"),
            )
        )
    for trigger_entry in level.get("triggers", []):
        trigger_zones.append(
            TriggerZone(
                trigger_entry["x"],
                trigger_entry["y"],
                trigger_entry["width"],
                trigger_entry["height"],
                trigger_entry["id"],
                once=trigger_entry.get("once", True),
                label=trigger_entry.get("label", ""),
            )
        )
    for event_entry in level.get("events", []):
        events.append(build_event(event_entry))

    exit_data = level["exit_zone"]
    exit_zone = ExitZone(exit_data["x"], exit_data["y"], exit_data["width"], exit_data["height"])

    return {
        "name": level["name"],
        "subtitle": level.get("subtitle", ""),
        "index": level["index"],
        "tip": level.get("tip", ""),
        "failure_hint": level.get("failure_hint", ""),
        "time_par": level.get("time_par", ""),
        "level_width": level["level_width"],
        "level_height": level["level_height"],
        "walls": walls,
        "enemy_spawns": enemies,
        "tokens": tokens,
        "pickups": pickups,
        "hazards": hazards,
        "checkpoints": checkpoints,
        "triggers": trigger_zones,
        "events": events,
        "exit_zone": exit_zone,
        "player": player,
        "spawn_point": (player.rect.x, player.rect.y),
    }


def load_all_levels(filename):
    global levels
    global level_data

    level_data = read_level_data(filename)
    levels = []
    for position, level in enumerate(level_data["levels"]):
        levels.append(
            {
                "name": level["name"],
                "subtitle": level.get("subtitle", ""),
                "index": position,
                "time_par": level.get("time_par", ""),
                "tip": level.get("tip", ""),
                "failure_hint": level.get("failure_hint", ""),
            }
        )
    return levels


def load_single_level(index):
    level = level_data["levels"][index]
    return load_level(level)
