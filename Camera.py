import pygame


class Camera:
    def __init__(self, width, height, viewport_width, viewport_height):
        self.camera = pygame.Rect(0, 0, width, height)
        self.width = width
        self.height = height
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.padding = 100
        self.x = 0.0
        self.y = 0.0
        self.smooth_factor = 0.18

    def apply(self, entity):
        return entity.rect.move(self.camera.topleft)

    def update(self, target):
        desired_x = -target.rect.x + int(self.viewport_width / 2)
        desired_y = -target.rect.y + int(self.viewport_height / 2)

        desired_x += min(self.padding, abs(desired_x)) * (-1 if desired_x < 0 else 1)
        desired_y += min(self.padding, abs(desired_y)) * (-1 if desired_y < 0 else 1)

        desired_x = min(0, desired_x)
        desired_y = min(0, desired_y)
        desired_x = max(-(self.width - self.viewport_width), desired_x)
        desired_y = max(-(self.height - self.viewport_height), desired_y)

        self.x += (desired_x - self.x) * self.smooth_factor
        self.y += (desired_y - self.y) * self.smooth_factor
        self.camera = pygame.Rect(int(self.x), int(self.y), self.width, self.height)
