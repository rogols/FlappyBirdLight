from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

from .controllers import BaseController, TransferFunctionController, controller_factory
from .core import ControlCommand, FlappySimulation, SCREEN_HEIGHT, SCREEN_WIDTH


MANUAL = "manual"
AUTOMATIC = "automatic"

READY = "ready"
RUNNING = "running"
GAME_OVER = "game_over"

WINDOW_WIDTH = 1360
WINDOW_HEIGHT = 860
MIN_WIDTH = 1120
MIN_HEIGHT = 760
MANUAL_FLAP_COOLDOWN = 0.10
HIGH_SCORE_LIMIT = 5

PALETTE = {
    "bg": (241, 236, 225),
    "ink": (31, 38, 46),
    "muted": (93, 99, 107),
    "panel": (250, 247, 241),
    "card": (255, 253, 249),
    "line": (207, 198, 184),
    "shadow": (227, 219, 205),
    "accent": (219, 120, 65),
    "accent_2": (36, 126, 104),
    "accent_3": (79, 98, 190),
    "target": (192, 107, 64),
}


@dataclass
class AppLayout:
    world: tuple[int, int, int, int]
    sidebar: tuple[int, int, int, int]


@dataclass
class ScoreEntry:
    name: str
    score: int


class ControlTheoryApp:
    def __init__(self) -> None:
        import pygame

        pygame.init()
        self.pygame = pygame
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Flappy Bird Reglerteorilabb")
        self.clock = pygame.time.Clock()
        self.world_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        self.title_font = pygame.font.SysFont("georgia", 34, bold=True)
        self.heading_font = pygame.font.SysFont("georgia", 24, bold=True)
        self.body_font = pygame.font.SysFont("dejavusansmono", 17)
        self.small_font = pygame.font.SysFont("dejavusansmono", 15)
        self.tiny_font = pygame.font.SysFont("dejavusansmono", 13)

        self.asset_root = Path(__file__).resolve().parent.parent / "flappy-bird-assets"
        self.high_score_path = Path(__file__).resolve().parent.parent / "high_scores.json"
        self.assets = self._load_assets()
        if self.assets.get("icon") is not None:
            pygame.display.set_icon(self.assets["icon"])

        self.sim = FlappySimulation()
        self.controllers = controller_factory()
        self.selected_controller = 0
        self.selected_parameter = 0
        self.parameter_input: str | None = None
        self.mode = MANUAL
        self.phase = READY
        self.manual_cooldown = 0.0
        self.manual_pending_flap = False
        self.status = ""
        self.high_scores = self._load_high_scores()
        self._reset_round()

    @property
    def controller(self) -> BaseController:
        return self.controllers[self.selected_controller]

    def run(self) -> None:
        while True:
            dt = self.sim.plant.dt
            if not self._handle_events():
                break
            self._update(dt)
            self._render()
            self.clock.tick(int(round(1.0 / dt)))
        self.pygame.quit()

    def _handle_events(self) -> bool:
        pygame = self.pygame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.VIDEORESIZE:
                width = max(MIN_WIDTH, event.w)
                height = max(MIN_HEIGHT, event.h)
                self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                continue
            if event.type != pygame.KEYDOWN:
                continue
            self._handle_key(event)
        return True

    def _handle_key(self, event) -> None:
        pygame = self.pygame
        key = event.key

        if key == pygame.K_ESCAPE:
            self._reset_round()
            return
        if key == pygame.K_m:
            self._switch_mode(MANUAL)
            return
        if key == pygame.K_a:
            self._switch_mode(AUTOMATIC)
            return
        if self._handle_parameter_input_key(event):
            return

        if self.mode == MANUAL:
            if key == pygame.K_SPACE:
                if self.phase == GAME_OVER:
                    self._prepare_round_state()
                if self.phase != RUNNING:
                    self._start_round()
                if self.manual_cooldown <= 0.0:
                    self.manual_cooldown = MANUAL_FLAP_COOLDOWN
                    self.manual_pending_flap = True
            elif key == pygame.K_TAB:
                editable = self._editable_parameters()
                if editable:
                    self.selected_parameter = (self.selected_parameter + 1) % len(editable)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.phase == RUNNING:
                    self.status = "Återställ rundan innan du ändrar spelparametrar."
                    return
                self._begin_parameter_input()
            elif key == pygame.K_r:
                self._reset_round()
        else:
            if key in (pygame.K_1, pygame.K_2, pygame.K_3):
                if self.phase == RUNNING:
                    self.status = "Återställ rundan innan du byter regulatorfamilj."
                    return
                self.selected_controller = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2}[key]
                self.selected_parameter = 0
                self._reset_round()
            elif key == pygame.K_TAB:
                if self.phase == RUNNING:
                    self.status = "Återställ rundan innan du ändrar regulatorparametrar."
                    return
                editable = self.controller.editable_parameters()
                if editable:
                    self.selected_parameter = (self.selected_parameter + 1) % len(editable)
            elif key == pygame.K_SPACE:
                if self.phase == GAME_OVER:
                    self._prepare_round_state()
                if self.phase != RUNNING:
                    self._start_round()
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.phase == RUNNING:
                    self.status = "Återställ rundan innan du ändrar regulatorparametrar."
                    return
                self._begin_parameter_input()
            elif key == pygame.K_r:
                self._reset_round()

    def _switch_mode(self, mode: str) -> None:
        if self.mode == mode:
            return
        self.mode = mode
        self.selected_parameter = 0
        self._reset_round()

    def _reset_round(self, status: str | None = None) -> None:
        self.phase = READY
        self._prepare_round_state()
        if status is not None:
            self.status = status
        elif self.mode == MANUAL:
            self.status = "Manuellt läge klart. Blanksteg startar och flaxar. M/A byter läge."
        else:
            self.status = "Automatiskt läge klart. Ställ in regulatorn och tryck Blanksteg för att starta."

    def _prepare_round_state(self) -> None:
        self.manual_cooldown = 0.0
        self.manual_pending_flap = False
        self.parameter_input = None
        self.controller.reset()
        self.sim.reset(pipes_enabled=True, target_y=self.sim.center_y)

    def _start_round(self) -> None:
        if self.phase == RUNNING:
            return
        self.phase = RUNNING
        self.controller.reset()
        if self.mode == MANUAL:
            self.status = "Manuellt spel påbörjat."
        else:
            self.status = f"Automatiskt spel påbörjat med {self._controller_display_name()}."

    def _manual_control_command(self) -> ControlCommand:
        command = ControlCommand(
            flap=self.manual_pending_flap,
            effort=1.0 if self.manual_pending_flap else 0.0,
            label="spelare",
        )
        self.manual_pending_flap = False
        return command

    def _automatic_control_command(self, dt: float) -> ControlCommand:
        observation = self.sim.observe()
        observation.target_y = observation.next_pipe_gap_y if observation.next_pipe_gap_y is not None else self.sim.center_y
        return self.controller.update(observation, dt)

    def _update(self, dt: float) -> None:
        if self.phase != RUNNING:
            return

        if self.mode == MANUAL:
            self.manual_cooldown = max(0.0, self.manual_cooldown - dt)
            command = self._manual_control_command()
        else:
            command = self._automatic_control_command(dt)

        sample = self.sim.step(command)
        if not sample["alive"]:
            self.phase = GAME_OVER
            self._record_score()
            self.status = f"Spelet är slut. Kollision med {self._crash_reason_text(sample['crash_reason'])} efter poäng {self.sim.score}."

    def _record_score(self) -> None:
        if self.mode == MANUAL:
            bucket = "player"
            name = "Spelare"
        else:
            bucket = "controller"
            name = self._controller_display_name()
        entries = self.high_scores[bucket]
        entries.append(ScoreEntry(name=name, score=int(self.sim.score)))
        entries.sort(key=lambda entry: entry.score, reverse=True)
        del entries[HIGH_SCORE_LIMIT:]
        self._save_high_scores()

    def _render(self) -> None:
        layout = self._layout()
        self.screen.fill(PALETTE["bg"])
        self._draw_world(layout.world)
        self._draw_sidebar(layout.sidebar)
        self.pygame.display.flip()

    def _layout(self) -> AppLayout:
        width, height = self.screen.get_size()
        margin = 18
        gutter = 18
        world_width = int(width * 0.56)
        world_rect = (margin, margin, world_width - margin, height - margin * 2)
        sidebar_x = world_rect[0] + world_rect[2] + gutter
        sidebar_rect = (sidebar_x, margin, width - sidebar_x - margin, height - margin * 2)
        return AppLayout(world=world_rect, sidebar=sidebar_rect)

    def _draw_world(self, rect: tuple[int, int, int, int]) -> None:
        x, y, width, height = rect
        canvas = self.world_surface
        self._draw_canvas_background(canvas)
        self._draw_simulation_canvas(canvas)

        frame_rect = self.pygame.Rect(x, y, width, height)
        self._draw_panel(self.screen, frame_rect, PALETTE["panel"])
        inset = frame_rect.inflate(-16, -16)
        scaled = self.pygame.transform.smoothscale(canvas, inset.size)
        self.screen.blit(scaled, inset.topleft)

    def _draw_canvas_background(self, surface) -> None:
        surface.blit(self.assets["background_day"], (0, 0))

    def _draw_simulation_canvas(self, surface) -> None:
        base_y = self._base_y()
        if self.mode == AUTOMATIC:
            target_y_px = self._py(self._target_for_render())
            self._draw_target_line(surface, target_y_px)
            target_label = self.tiny_font.render("Börvärde", True, PALETTE["target"])
            surface.blit(target_label, (12, max(8, int(target_y_px) - 18)))

        for pipe in self.sim.pipes:
            self._draw_pipe(surface, pipe.x, pipe.gap_y, pipe.gap_height, base_y)

        bird_y = self.sim.state.y
        self._draw_bird_sprite(surface, self.sim.plant.bird_x, bird_y, flap_phase=self._world_time())

        self._draw_base(surface, self._world_time())
        self._draw_score(surface)
        self._draw_world_banner(surface)

        if self.phase == GAME_OVER:
            gameover = self.assets["gameover"]
            surface.blit(gameover, (SCREEN_WIDTH // 2 - gameover.get_width() // 2, 132))

    def _draw_world_banner(self, surface) -> None:
        pygame = self.pygame
        badge_rect = pygame.Rect(18, 18, 126, 50)
        pygame.draw.rect(surface, (252, 248, 240), badge_rect, border_radius=14)
        pygame.draw.rect(surface, PALETTE["line"], badge_rect, 1, border_radius=14)
        phase_surf = self.heading_font.render(self._phase_label().capitalize(), True, PALETTE["ink"])
        surface.blit(phase_surf, (badge_rect.left + 16, badge_rect.top + 10))

    def _draw_high_score_overlay(self, surface) -> None:
        pygame = self.pygame
        overlay = pygame.Surface((SCREEN_WIDTH - 42, 170), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (250, 247, 241, 238), overlay.get_rect(), border_radius=18)
        target = pygame.Rect(21, SCREEN_HEIGHT - 200, SCREEN_WIDTH - 42, 170)
        surface.blit(overlay, target.topleft)
        pygame.draw.rect(surface, PALETTE["line"], target, 1, border_radius=18)
        surface.blit(self.heading_font.render("Topplista", True, PALETTE["ink"]), (target.left + 18, target.top + 14))

        left = pygame.Rect(target.left + 18, target.top + 52, target.width // 2 - 30, target.height - 66)
        right = pygame.Rect(target.centerx + 6, target.top + 52, target.width // 2 - 24, target.height - 66)
        self._draw_score_column(surface, left, "Spelare", self.high_scores["player"])
        self._draw_score_column(surface, right, "Regulator", self.high_scores["controller"])

    def _draw_score_column(self, surface, rect, title: str, entries: list[ScoreEntry]) -> None:
        surface.blit(self.small_font.render(title, True, PALETTE["ink"]), (rect.left, rect.top))
        y = rect.top + 22
        if not entries:
            surface.blit(self.tiny_font.render("Inga poäng än", True, PALETTE["muted"]), (rect.left, y))
            return
        for index, entry in enumerate(entries[:HIGH_SCORE_LIMIT], start=1):
            label = f"{index}. {entry.name[:26]}"
            score = str(entry.score)
            surface.blit(self.tiny_font.render(label, True, PALETTE["muted"]), (rect.left, y))
            score_surf = self.tiny_font.render(score, True, PALETTE["ink"])
            surface.blit(score_surf, (rect.right - score_surf.get_width(), y))
            y += 18

    def _draw_sidebar(self, rect: tuple[int, int, int, int]) -> None:
        x, y, width, height = rect
        sidebar_rect = self.pygame.Rect(x, y, width, height)
        self._draw_panel(self.screen, sidebar_rect, PALETTE["panel"])

        inner = sidebar_rect.inflate(-18, -18)
        cursor = inner.top

        header_rect = self.pygame.Rect(inner.left, cursor, inner.width, 96)
        self._draw_card(header_rect)
        self.screen.blit(self.title_font.render(self._mode_title(), True, PALETTE["ink"]), (header_rect.left + 18, header_rect.top + 14))
        self._draw_text_block(self.screen, self.status, self.body_font, PALETTE["muted"], self.pygame.Rect(header_rect.left + 18, header_rect.top + 58, header_rect.width - 36, 42))
        cursor = header_rect.bottom + 12

        controls_rect = self.pygame.Rect(inner.left, cursor, inner.width, 104 if self.mode == MANUAL else 132)
        self._draw_text_card(controls_rect, "Kontroller", self._control_lines())
        cursor = controls_rect.bottom + 12

        live_rect = self.pygame.Rect(inner.left, cursor, inner.width, 100)
        self._draw_text_card(live_rect, "Live-data", self._live_lines())
        cursor = live_rect.bottom + 12

        config_rect = self.pygame.Rect(inner.left, cursor, inner.width, 120 if self.mode == MANUAL else 150)
        if self.mode == AUTOMATIC:
            self._draw_text_card(config_rect, "Regulatorinställning", self._controller_lines())
        else:
            self._draw_text_card(config_rect, "Spelarsession", self._player_lines())
        cursor = config_rect.bottom + 12

        scores_rect = self.pygame.Rect(inner.left, cursor, inner.width, inner.bottom - cursor)
        self._draw_card(scores_rect)
        self.screen.blit(self.heading_font.render("Poängtavla", True, PALETTE["ink"]), (scores_rect.left + 18, scores_rect.top + 14))
        left = self.pygame.Rect(scores_rect.left + 18, scores_rect.top + 52, scores_rect.width // 2 - 26, scores_rect.height - 68)
        right = self.pygame.Rect(scores_rect.centerx + 8, scores_rect.top + 52, scores_rect.width // 2 - 26, scores_rect.height - 68)
        self._draw_score_column(self.screen, left, "Spelare", self.high_scores["player"])
        self._draw_score_column(self.screen, right, "Regulator", self.high_scores["controller"])

    def _draw_text_card(self, rect, title: str, lines: list[str]) -> None:
        self._draw_card(rect)
        self.screen.blit(self.heading_font.render(title, True, PALETTE["ink"]), (rect.left + 18, rect.top + 14))
        text_rect = self.pygame.Rect(rect.left + 18, rect.top + 48, rect.width - 36, rect.height - 60)
        self._draw_lines_in_rect(self.screen, lines, self.small_font, PALETTE["muted"], text_rect)

    def _load_assets(self) -> dict[str, object]:
        pygame = self.pygame
        sprite_dir = self.asset_root / "sprites"

        def load_sprite(name: str):
            return pygame.image.load(str(sprite_dir / name)).convert_alpha()

        background_day = pygame.transform.smoothscale(load_sprite("background-day.png"), (SCREEN_WIDTH, SCREEN_HEIGHT))
        base_raw = load_sprite("base.png")
        base_height = 84
        base_width = int(base_raw.get_width() * (base_height / base_raw.get_height()))
        base = pygame.transform.smoothscale(base_raw, (base_width, base_height))
        pipe_raw = load_sprite("pipe-green.png")
        pipe_width = 78
        bird_size = (54, 38)
        bird_frames = [
            pygame.transform.smoothscale(load_sprite("yellowbird-upflap.png"), bird_size),
            pygame.transform.smoothscale(load_sprite("yellowbird-midflap.png"), bird_size),
            pygame.transform.smoothscale(load_sprite("yellowbird-downflap.png"), bird_size),
        ]
        icon = pygame.transform.smoothscale(load_sprite("yellowbird-midflap.png"), (32, 32))
        gameover = pygame.transform.smoothscale(load_sprite("gameover.png"), (204, 56))
        digits: dict[str, object] = {}
        for digit in range(10):
            surface = load_sprite(f"{digit}.png")
            scaled = pygame.transform.smoothscale(surface, (int(surface.get_width() * 1.35), int(surface.get_height() * 1.35)))
            digits[str(digit)] = scaled
        return {
            "background_day": background_day,
            "base": base,
            "pipe_green": pipe_raw,
            "pipe_width": pipe_width,
            "bird_frames": bird_frames,
            "gameover": gameover,
            "digits": digits,
            "icon": icon,
        }

    def _draw_target_line(self, surface, y: float) -> None:
        dash = 10
        gap = 6
        x = 0
        while x < SCREEN_WIDTH:
            self.pygame.draw.line(surface, PALETTE["target"], (x, y), (min(SCREEN_WIDTH, x + dash), y), 2)
            x += dash + gap

    def _draw_pipe(self, surface, x: float, gap_y: float, gap_height: float, base_y: int) -> None:
        pygame = self.pygame
        pipe_sprite = self.assets["pipe_green"]
        pipe_width = self.assets["pipe_width"]
        gap_top = self._py(gap_y - gap_height / 2.0)
        gap_bottom = self._py(gap_y + gap_height / 2.0)
        top_height = max(12, int(gap_top))
        bottom_height = max(12, int(base_y - gap_bottom))
        x_px = self._px(x)

        top_pipe = pygame.transform.smoothscale(pipe_sprite, (pipe_width, top_height))
        top_pipe = pygame.transform.flip(top_pipe, False, True)
        bottom_pipe = pygame.transform.smoothscale(pipe_sprite, (pipe_width, bottom_height))
        surface.blit(top_pipe, (x_px, 0))
        surface.blit(bottom_pipe, (x_px, int(gap_bottom)))

    def _draw_base(self, surface, time_value: float) -> None:
        base = self.assets["base"]
        base_y = self._base_y()
        scroll_speed = self.sim.world_to_pixels_x(self.sim.config.pipe_speed)
        width = base.get_width()
        offset = int((time_value * scroll_speed) % width)
        for tile_x in range(-offset, SCREEN_WIDTH + width, width):
            surface.blit(base, (tile_x, base_y))

    def _draw_bird_sprite(self, surface, x: float, y: float, flap_phase: float) -> None:
        pygame = self.pygame
        frame_index = int((flap_phase * 8.0) % len(self.assets["bird_frames"]))
        sprite = self.assets["bird_frames"][frame_index]
        angle = max(-28.0, min(35.0, -self.sim.state.vy * 12.0))
        rotated = pygame.transform.rotozoom(sprite, angle, 1.0)
        rect = rotated.get_rect(center=(self._px(x + self.sim.plant.bird_width / 2), self._py(y + self.sim.plant.bird_height / 2)))
        surface.blit(rotated, rect.topleft)

    def _draw_score(self, surface) -> None:
        pygame = self.pygame
        box = pygame.Rect(12, self._base_y() - 54, 132, 40)
        pygame.draw.rect(surface, (252, 248, 240), box, border_radius=12)
        pygame.draw.rect(surface, PALETTE["line"], box, 1, border_radius=12)
        label = self.tiny_font.render("Poäng", True, PALETTE["muted"])
        value = self.heading_font.render(str(self.sim.score), True, PALETTE["ink"])
        surface.blit(label, (box.left + 10, box.top + 6))
        surface.blit(value, (box.left + 10, box.top + 14))

    def _draw_panel(self, surface, rect, color: tuple[int, int, int]) -> None:
        shadow_rect = rect.move(0, 8)
        self.pygame.draw.rect(surface, PALETTE["shadow"], shadow_rect, border_radius=22)
        self.pygame.draw.rect(surface, color, rect, border_radius=22)
        self.pygame.draw.rect(surface, PALETTE["line"], rect, 1, border_radius=22)

    def _draw_card(self, rect) -> None:
        self.pygame.draw.rect(self.screen, PALETTE["card"], rect, border_radius=18)
        self.pygame.draw.rect(self.screen, PALETTE["line"], rect, 1, border_radius=18)

    def _draw_text_block(self, surface, text: str, font, color, rect) -> None:
        lines = wrap_text(font, text, rect.width)
        y = rect.top
        for line in lines:
            if y + font.get_linesize() > rect.bottom:
                break
            surface.blit(font.render(line, True, color), (rect.left, y))
            y += font.get_linesize()

    def _draw_lines_in_rect(self, surface, lines: list[str], font, color, rect) -> None:
        y = rect.top
        for line in lines:
            wrapped = wrap_text(font, line, rect.width)
            for part in wrapped:
                if y + font.get_linesize() > rect.bottom:
                    return
                surface.blit(font.render(part, True, color), (rect.left, y))
                y += font.get_linesize()
            y += 2

    def _control_lines(self) -> list[str]:
        if self.mode == MANUAL:
            return [
                "M manuellt läge | A automatiskt läge",
                "Blanksteg startar rundan och flaxar",
                "Tab väljer hastighetsökning",
                "Enter ändrar valt värde, R/Esc återgår till Redo",
                "Poäng = passerade rör före kollision",
            ]
        return [
            "M manuellt läge | A automatiskt läge",
            "1/2/3 väljer regulatorfamilj",
            "Tab väljer parameter",
            "Enter ändrar valt värde, Blanksteg startar",
            "R/Esc återgår till Redo",
        ]

    def _live_lines(self) -> list[str]:
        lines = [
            f"fas={self._phase_label()}  poäng={self.sim.score}",
            f"ärvärde={self.sim.state.y:.2f} m  vy={self.sim.state.vy:.2f} m/s",
            f"acceleration={self.sim.state.ay:.2f} m/s²",
            f"rörhastighet={self.sim.current_pipe_speed():.2f} m/s",
            f"hastighetsökning={self.sim.config.pipe_speed_gain:.3f} m/s²",
        ]
        if self.mode == AUTOMATIC:
            lines.insert(2, f"börvärde={self._target_for_render():.2f} m")
        return lines

    def _player_lines(self) -> list[str]:
        return [
            "Spelarstyrd fågel med samma processmodell som regulatorn.",
            f"flaximpuls={self.sim.plant.flap_impulse:.3f} N·s",
            f"massa={self.sim.plant.bird_mass:.3f} kg  gravitation={self.sim.plant.gravity:.2f} m/s²",
            f"hastighetsökning={self.sim.config.pipe_speed_gain:.3f} m/s²",
            "Topplistor sparas separat för spelare och regulatorer.",
        ]

    def _controller_lines(self) -> list[str]:
        lines = [f"regulator={self._controller_display_name()}"]
        for index, key in enumerate(self._editable_parameters()):
            marker = ">" if index == self.selected_parameter else "-"
            value = self._parameter_value(key)
            suffix = ""
            if index == self.selected_parameter and self.parameter_input is not None:
                suffix = f"  edit[{self.parameter_input or '...'}]"
            lines.append(f"{marker} {self._parameter_label(key)}={value:.3f}{suffix}")
        lines.append("Tab väljer parameter. Enter redigerar valt värde.")
        lines.append("Tryck Blanksteg efter justering för att se regulatorn spela live.")
        return lines

    def _parameter_value(self, key: str) -> float:
        if key == "pipe_speed_gain":
            return float(self.sim.config.pipe_speed_gain)
        value = getattr(self.controller, key, None)
        if value is not None:
            return float(value)
        if isinstance(self.controller, TransferFunctionController):
            if key == "num0":
                return float(self.controller.numerator[0])
            if key == "num1":
                return float(self.controller.numerator[1] if len(self.controller.numerator) > 1 else 0.0)
            if key == "den1":
                return float(self.controller.denominator[1] if len(self.controller.denominator) > 1 else 0.0)
            if key == "den2":
                return float(self.controller.denominator[2] if len(self.controller.denominator) > 2 else 0.0)
        return 0.0

    def _editable_parameters(self) -> list[str]:
        if self.mode == MANUAL:
            return ["pipe_speed_gain"]
        return ["pipe_speed_gain", *self.controller.editable_parameters()]

    def _controller_display_name(self) -> str:
        controller = self.controller
        if controller.name == "On-Off":
            return f"På-av dödzon={controller.deadband:.2f} hysteres={controller.hysteresis:.2f}"
        if controller.name == "PID":
            return f"PID K={controller.k:.2f} Ti={controller.ti:.2f} Td={controller.td:.2f}"
        if isinstance(controller, TransferFunctionController):
            num1 = controller.numerator[1] if len(controller.numerator) > 1 else 0.0
            den1 = controller.denominator[1] if len(controller.denominator) > 1 else 0.0
            den2 = controller.denominator[2] if len(controller.denominator) > 2 else 0.0
            return f"Polynom N={controller.numerator[0]:.2f},{num1:.2f} D={den1:.2f},{den2:.2f}"
        return self._controller_family_name()

    def _load_high_scores(self) -> dict[str, list[ScoreEntry]]:
        empty = {"player": [], "controller": []}
        if not self.high_score_path.exists():
            return empty
        try:
            payload = json.loads(self.high_score_path.read_text(encoding="utf-8"))
        except Exception:
            return empty
        loaded: dict[str, list[ScoreEntry]] = {"player": [], "controller": []}
        for bucket in loaded:
            for item in payload.get(bucket, []):
                try:
                    loaded[bucket].append(ScoreEntry(name=str(item["name"]), score=int(item["score"])))
                except Exception:
                    continue
            loaded[bucket].sort(key=lambda entry: entry.score, reverse=True)
            del loaded[bucket][HIGH_SCORE_LIMIT:]
        return loaded

    def _save_high_scores(self) -> None:
        payload = {
            bucket: [asdict(entry) for entry in entries]
            for bucket, entries in self.high_scores.items()
        }
        self.high_score_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _world_time(self) -> float:
        return self.sim.state.time if self.phase != READY else self.pygame.time.get_ticks() / 1000.0

    def _base_y(self) -> int:
        return SCREEN_HEIGHT - self.assets["base"].get_height()

    def _px(self, meters: float) -> int:
        return int(round(self.sim.world_to_pixels_x(meters)))

    def _py(self, meters: float) -> int:
        return int(round(self.sim.world_to_pixels_y(meters)))

    def _target_for_render(self) -> float:
        observation = self.sim.observe()
        return observation.next_pipe_gap_y if observation.next_pipe_gap_y is not None else self.sim.center_y

    def _mode_title(self) -> str:
        return "Manuellt spel" if self.mode == MANUAL else "Automatiskt spel"

    def _begin_parameter_input(self) -> None:
        editable = self._editable_parameters()
        if not editable:
            self.status = "Det finns inga redigerbara parametrar."
            return
        parameter = editable[self.selected_parameter]
        self.parameter_input = f"{self._parameter_value(parameter):.3f}"
        self.status = f"Redigerar {self._parameter_label(parameter)}. Skriv ett värde, Enter bekräftar, Esc avbryter."

    def _handle_parameter_input_key(self, event) -> bool:
        if self.parameter_input is None:
            return False

        pygame = self.pygame
        key = event.key
        if key == pygame.K_ESCAPE:
            self.parameter_input = None
            self.status = "Parameterredigering avbruten."
            return True
        if key == pygame.K_BACKSPACE:
            self.parameter_input = self.parameter_input[:-1]
            return True
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self._commit_parameter_input()

        character = event.unicode or ""
        if character and character in "0123456789.-":
            if character == "-" and self.parameter_input:
                return True
            if character == "." and "." in self.parameter_input:
                return True
            self.parameter_input += character
            return True
        return True

    def _commit_parameter_input(self) -> bool:
        editable = self._editable_parameters()
        if not editable:
            self.parameter_input = None
            return True
        parameter = editable[self.selected_parameter]
        text = (self.parameter_input or "").strip()
        if text in {"", "-", ".", "-."}:
            self.status = f"Ogiltigt värde för {self._parameter_label(parameter)}."
            return True
        try:
            target_value = float(text)
        except ValueError:
            self.status = f"Ogiltigt värde för {self._parameter_label(parameter)}: {text}"
            return True

        current_value = self._parameter_value(parameter)
        self.parameter_input = None
        self._set_parameter_value(parameter, target_value, current_value)
        self._reset_round(status=f"Satte {self._controller_family_name()} {self._parameter_label(parameter)} till {target_value:.3f}.")
        return True

    def _set_parameter_value(self, parameter: str, target_value: float, current_value: float) -> None:
        if parameter == "pipe_speed_gain":
            self.sim.config.pipe_speed_gain = max(0.0, target_value)
            return
        self.controller.adjust(parameter, target_value - current_value)

    def _parameter_label(self, key: str) -> str:
        return {
            "deadband": "dödzon",
            "hysteresis": "hysteres",
            "min_interval": "minintervall",
            "derivative_filter": "derivatafilter",
            "anti_windup": "anti-windup",
            "num0": "talar0",
            "num1": "talar1",
            "den1": "nämnare1",
            "den2": "nämnare2",
            "k": "K",
            "ti": "Ti",
            "td": "Td",
            "pipe_speed_gain": "hastighetsökning",
        }.get(key, key)

    def _phase_label(self) -> str:
        return {
            READY: "redo",
            RUNNING: "pågår",
            GAME_OVER: "redo",
        }[self.phase]

    def _controller_family_name(self) -> str:
        controller = self.controller
        if controller.name == "On-Off":
            return "På-av"
        if controller.name == "PID":
            return "PID"
        if isinstance(controller, TransferFunctionController):
            return "Polynom"
        return controller.name

    def _crash_reason_text(self, reason: object) -> str:
        reason_text = str(reason)
        return {
            "pipe": "rör",
            "ground": "marken",
            "ceiling": "taket",
            "": "okänd orsak",
        }.get(reason_text, reason_text)


def wrap_text(font, text: str, width: int) -> list[str]:
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if current and font.size(candidate)[0] > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def run_app() -> None:
    try:
        app = ControlTheoryApp()
    except Exception as error:
        raise SystemExit(
            "Kunde inte starta PyGame-gränssnittet. Installera beroenden från requirements.txt först. "
            f"Ursprungligt fel: {error}"
        ) from error
    app.run()
