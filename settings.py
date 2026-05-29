import pygame

SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 720
FPS = 60

BLACK = (12, 16, 24)
WHITE = (245, 247, 255)
GREY = (128, 132, 146)
RED = (235, 92, 92)
GREEN = (90, 214, 146)
BLUE = (72, 116, 214)
PURPLE = (163, 105, 255)
YELLOW = (255, 214, 74)
CYAN = (94, 226, 255)
ORANGE = (255, 156, 72)

NAMED_COLORS = {
    "BLACK": BLACK,
    "WHITE": WHITE,
    "GREY": GREY,
    "GRAY": GREY,
    "RED": RED,
    "GREEN": GREEN,
    "BLUE": BLUE,
    "PURPLE": PURPLE,
    "YELLOW": YELLOW,
    "CYAN": CYAN,
    "ORANGE": ORANGE,
}


def resolve_color(value, fallback):
    if isinstance(value, pygame.Color):
        return value
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        return tuple(value[:3])
    if isinstance(value, str):
        key = value.upper()
        if key in NAMED_COLORS:
            return NAMED_COLORS[key]
        try:
            return pygame.Color(value)
        except ValueError:
            return fallback
    return fallback
