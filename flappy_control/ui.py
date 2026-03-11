from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import os
from pathlib import Path
from typing import Sequence

from .analytics import analytic_transfer_function, bode_points, closed_loop_bode
from .controllers import BaseController, TransferFunctionController, controller_factory
from .core import (
    ControlCommand,
    ExperimentResult,
    ExperimentSpec,
    FlappySimulation,
    Observation,
    PlantParams,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TransferFunctionModel,
)


MENU = "menu"
MANUAL = "manual"
PLANT_LAB = "plant_lab"
CONTROLLER_LAB = "controller_lab"
GAME_CHALLENGE = "game_challenge"

WINDOW_WIDTH = 1360
WINDOW_HEIGHT = 860
MIN_WIDTH = 1120
MIN_HEIGHT = 760

LAB_STAGES = [
    ("Observe open loop", "Watch gravity, drag, and one flap change the bird state."),
    ("Impulse response", "Run a one-flap experiment from a fixed initial condition."),
    ("Step response", "Inspect the integrated impulse response as an approximate step response."),
    ("Transfer function", "Compare the analytic plant model with the identified one."),
    ("Bode view", "Relate gain and phase to the bird's vertical dynamics."),
]

PALETTE = {
    "bg": (241, 236, 225),
    "ink": (31, 38, 46),
    "muted": (93, 99, 107),
    "sky": (190, 217, 236),
    "sand": (219, 208, 168),
    "grass": (72, 165, 97),
    "forest": (43, 108, 63),
    "panel": (250, 247, 241),
    "card": (255, 253, 249),
    "line": (207, 198, 184),
    "accent": (219, 120, 65),
    "accent_2": (36, 126, 104),
    "accent_3": (79, 98, 190),
    "shadow": (227, 219, 205),
}


@dataclass
class PlotData:
    title: str
    series: list[tuple[str, list[tuple[float, float]], tuple[int, int, int]]]


@dataclass
class AppLayout:
    world: tuple[int, int, int, int]
    sidebar: tuple[int, int, int, int]


class ControlTheoryApp:
    def __init__(self) -> None:
        import pygame

        pygame.init()
        self.pygame = pygame
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Flappy Bird Control Theory Lab")
        self.clock = pygame.time.Clock()
        self.world_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        self.title_font = pygame.font.SysFont("georgia", 34, bold=True)
        self.heading_font = pygame.font.SysFont("georgia", 24, bold=True)
        self.body_font = pygame.font.SysFont("dejavusansmono", 17)
        self.small_font = pygame.font.SysFont("dejavusansmono", 15)
        self.tiny_font = pygame.font.SysFont("dejavusansmono", 13)
        self.asset_root = Path(__file__).resolve().parent.parent / "flappy-bird-assets"
        self.assets = self._load_assets()
        if self.assets.get("icon") is not None:
            pygame.display.set_icon(self.assets["icon"])

        self.sim = FlappySimulation()
        self.mode = MENU
        self.controllers = controller_factory()
        self.selected_controller = 0
        self.selected_parameter = 0
        self.lab_stage = 0
        self.manual_cooldown = 0.0
        self.manual_pending_flap = False
        self.result: ExperimentResult | None = None
        self.plot: PlotData | None = None
        self.secondary_plot: PlotData | None = None
        self.status = "Choose a mode to start exploring the bird as a control object."
        self._start_mode(MENU)

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

            if event.key == pygame.K_ESCAPE:
                self._start_mode(MENU)
                continue
            if self.mode == MENU:
                self._handle_menu_key(event.key)
            elif self.mode == MANUAL:
                self._handle_manual_key(event.key)
            elif self.mode == PLANT_LAB:
                self._handle_plant_lab_key(event.key)
            else:
                self._handle_controller_key(event.key)
        return True

    def _handle_menu_key(self, key: int) -> None:
        pygame = self.pygame
        mapping = {
            pygame.K_1: MANUAL,
            pygame.K_2: PLANT_LAB,
            pygame.K_3: CONTROLLER_LAB,
            pygame.K_4: GAME_CHALLENGE,
        }
        mode = mapping.get(key)
        if mode:
            self._start_mode(mode)

    def _handle_manual_key(self, key: int) -> None:
        pygame = self.pygame
        if key == pygame.K_SPACE and self.manual_cooldown <= 0.0:
            self.manual_cooldown = 0.14
            self.manual_pending_flap = True
        elif key == pygame.K_r:
            self._start_mode(MANUAL)

    def _handle_plant_lab_key(self, key: int) -> None:
        pygame = self.pygame
        if key == pygame.K_i:
            self._run_impulse_experiment()
        elif key == pygame.K_s:
            self._start_stage(2)
            self._build_step_plot()
        elif key == pygame.K_m:
            self._start_stage(3)
            self._build_model_plot()
        elif key == pygame.K_b:
            self._start_stage(4)
            self._build_bode_plot()
        elif key == pygame.K_n:
            self._start_stage((self.lab_stage + 1) % len(LAB_STAGES))
        elif key == pygame.K_p:
            self._export_current_plot()
        elif key == pygame.K_e:
            self._export_current_result()

    def _handle_controller_key(self, key: int) -> None:
        pygame = self.pygame
        if key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.selected_controller = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2}[key]
            self.selected_parameter = 0
            if self.mode == CONTROLLER_LAB:
                self._start_mode(CONTROLLER_LAB)
            else:
                self._start_mode(GAME_CHALLENGE)
            return
        if key == pygame.K_TAB:
            editable = self.controller.editable_parameters()
            if editable:
                self.selected_parameter = (self.selected_parameter + 1) % len(editable)
        elif key in (pygame.K_EQUALS, pygame.K_PLUS):
            self._adjust_selected_parameter(+0.02)
        elif key == pygame.K_MINUS:
            self._adjust_selected_parameter(-0.02)
        elif key == pygame.K_r:
            self._start_mode(self.mode)
        elif key == pygame.K_p:
            self._export_current_plot()
        elif key == pygame.K_e:
            self._export_current_result()

    def _adjust_selected_parameter(self, delta: float) -> None:
        editable = self.controller.editable_parameters()
        if not editable:
            return
        parameter = editable[self.selected_parameter]
        self.controller.adjust(parameter, delta)
        self.status = f"Tuned {self.controller.name}: {parameter} {delta:+.2f}."
        self._start_mode(self.mode)

    def _update(self, dt: float) -> None:
        if self.mode == MENU:
            return
        if self.mode == MANUAL:
            self.manual_cooldown = max(0.0, self.manual_cooldown - dt)
            if not self.sim.state.alive:
                return
            flap = self.manual_pending_flap
            self.manual_pending_flap = False
            self.sim.step(ControlCommand(flap=flap, effort=1.0 if flap else 0.0, label="manual"))
            return

    def _start_mode(self, mode: str) -> None:
        self.mode = mode
        self.result = None
        self.plot = None
        self.secondary_plot = None
        self.manual_cooldown = 0.0
        self.manual_pending_flap = False
        self.controller.reset()

        if mode == MENU:
            self.status = "Main menu. Use 1-4 to move from gameplay into experiments and controllers."
            return
        if mode == MANUAL:
            self.sim.reset(pipes_enabled=True, target_y=SCREEN_HEIGHT / 2)
            self.status = "Manual mode. Space flaps, R restarts, Esc returns to the menu."
            return
        if mode == PLANT_LAB:
            self._run_impulse_experiment()
            return
        if mode == CONTROLLER_LAB:
            self._run_closed_loop_lab()
            return
        if mode == GAME_CHALLENGE:
            self._run_game_challenge()

    def _start_stage(self, index: int) -> None:
        self.lab_stage = index
        stage, goal = LAB_STAGES[index]
        self.status = f"{stage}. {goal}"

    def _run_impulse_experiment(self) -> None:
        self._start_stage(1)
        fired = {"value": False}

        def command_fn(_: Observation, __: float) -> ControlCommand:
            if not fired["value"]:
                fired["value"] = True
                return ControlCommand(flap=True, effort=1.0, label="impulse")
            return ControlCommand(label="impulse")

        spec = ExperimentSpec(
            name="Impulse experiment",
            duration=6.0,
            initial_y=SCREEN_HEIGHT / 2,
            target_y=SCREEN_HEIGHT / 2,
            pipes_enabled=False,
            input_profile="single_flap",
        )
        self.result = self.sim.run_experiment(spec, command_fn)
        self.plot = PlotData(
            title="Impulse experiment",
            series=[
                ("Position y", self._series(self.result.samples, "y"), PALETTE["ink"]),
                ("Velocity vy", self._series(self.result.samples, "vy"), PALETTE["accent_3"]),
                ("Input u", self._series(self.result.samples, "control_effort", scale=120.0, offset=120.0), PALETTE["accent"]),
            ],
        )
        self.secondary_plot = None

    def _build_step_plot(self) -> None:
        if not self.result:
            self._run_impulse_experiment()
        if not self.result:
            return
        self.plot = PlotData(
            title="Impulse and integrated step response",
            series=[
                (
                    "Integrated step",
                    [(index * self.sim.plant.dt, value) for index, value in enumerate(self.result.step_response)],
                    PALETTE["accent_2"],
                ),
                (
                    "Impulse x8",
                    [(index * self.sim.plant.dt, value * 8.0) for index, value in enumerate(self.result.impulse_response)],
                    PALETTE["accent"],
                ),
            ],
        )

    def _build_model_plot(self) -> None:
        if not self.result:
            self._run_impulse_experiment()
        if not self.result:
            return
        analytic = analytic_transfer_function(self.sim.plant)
        identified = self.result.model
        self.plot = PlotData(
            title="Measured vs model response",
            series=[
                ("Measured", self._series(self.result.samples, "y"), PALETTE["ink"]),
                ("Analytic", simulate_transfer_response(analytic, self.result.samples, self.sim.plant), PALETTE["accent_3"]),
                ("Identified", simulate_transfer_response(identified, self.result.samples, self.sim.plant), PALETTE["accent"]),
            ],
        )

    def _build_bode_plot(self) -> None:
        if not self.result:
            self._run_impulse_experiment()
        if not self.result:
            return
        analytic = analytic_transfer_function(self.sim.plant)
        identified = self.result.model
        self.plot = PlotData(
            title="Plant Bode magnitude",
            series=[
                ("Analytic", [(f, m) for f, m, _ in bode_points(analytic)], PALETTE["accent_3"]),
                ("Identified", [(f, m) for f, m, _ in bode_points(identified)], PALETTE["accent"]),
            ],
        )

    def _run_closed_loop_lab(self) -> None:
        controller = self.controller
        controller.reset()
        target = SCREEN_HEIGHT / 2 - 20

        def command_fn(observation: Observation, dt: float) -> ControlCommand:
            observation.target_y = target
            return controller.update(observation, dt)

        spec = ExperimentSpec(
            name=f"{controller.name} altitude hold",
            duration=10.0,
            initial_y=SCREEN_HEIGHT / 2 + 100,
            target_y=target,
            pipes_enabled=False,
            input_profile=controller.name.lower(),
        )
        self.result = self.sim.run_experiment(spec, command_fn)
        self.status = f"{controller.name} controller lab ready. Use Tab and +/- to tune, R to rerun."
        self.plot = PlotData(
            title=f"{controller.name} altitude response",
            series=[
                ("Bird altitude", self._series(self.result.samples, "y"), PALETTE["ink"]),
                ("Target", self._constant_series(self.result.samples, target), PALETTE["accent_2"]),
                ("Control effort", self._series(self.result.samples, "control_effort", scale=120.0, offset=120.0), PALETTE["accent"]),
            ],
        )
        self.secondary_plot = PlotData(
            title="Closed-loop Bode magnitude",
            series=[
                (
                    "Closed loop",
                    [(f, m) for f, m, _ in closed_loop_bode(self.result.model, controller_transfer_model(controller), count=60)],
                    PALETTE["accent_3"],
                )
            ],
        )

    def _run_game_challenge(self) -> None:
        controller = self.controller
        controller.reset()
        self.sim.reset(pipes_enabled=True, target_y=SCREEN_HEIGHT / 2)

        def command_fn(observation: Observation, dt: float) -> ControlCommand:
            observation.target_y = observation.next_pipe_gap_y if observation.next_pipe_gap_y is not None else SCREEN_HEIGHT / 2
            return controller.update(observation, dt)

        spec = ExperimentSpec(
            name=f"{controller.name} game challenge",
            duration=18.0,
            initial_y=SCREEN_HEIGHT / 2,
            target_y=SCREEN_HEIGHT / 2,
            pipes_enabled=True,
            input_profile=f"{controller.name.lower()}_pipes",
        )
        self.result = self.sim.run_experiment(spec, command_fn)
        self.status = f"{controller.name} game challenge complete. Compare survival, score, and control effort."
        self.plot = PlotData(
            title=f"{controller.name} gap tracking",
            series=[
                ("Bird altitude", self._series(self.result.samples, "y"), PALETTE["ink"]),
                (
                    "Gap center",
                    [(float(sample["time"]), float(sample.get("next_pipe_gap_y") or SCREEN_HEIGHT / 2)) for sample in self.result.samples],
                    PALETTE["accent_2"],
                ),
                ("Control effort", self._series(self.result.samples, "control_effort", scale=120.0, offset=120.0), PALETTE["accent"]),
            ],
        )
        self.secondary_plot = PlotData(
            title="Closed-loop Bode magnitude",
            series=[
                (
                    "Closed loop",
                    [(f, m) for f, m, _ in closed_loop_bode(self.result.model, controller_transfer_model(controller), count=60)],
                    PALETTE["accent_3"],
                )
            ],
        )

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
        world_width = int(width * 0.53)
        world_rect = (margin, margin, world_width - margin, height - margin * 2)
        sidebar_x = world_rect[0] + world_rect[2] + gutter
        sidebar_rect = (sidebar_x, margin, width - sidebar_x - margin, height - margin * 2)
        return AppLayout(world=world_rect, sidebar=sidebar_rect)

    def _draw_world(self, rect: tuple[int, int, int, int]) -> None:
        x, y, width, height = rect
        canvas = self.world_surface
        self._draw_canvas_background(canvas)

        if self.mode == MENU:
            self._draw_menu_canvas(canvas)
        else:
            self._draw_simulation_canvas(canvas)

        frame_rect = self.pygame.Rect(x, y, width, height)
        self._draw_panel(self.screen, frame_rect, PALETTE["panel"])
        inset = frame_rect.inflate(-16, -16)
        scaled = self.pygame.transform.smoothscale(canvas, inset.size)
        self.screen.blit(scaled, inset.topleft)

    def _draw_canvas_background(self, surface) -> None:
        background = self.assets["background_day"]
        if self.mode in (PLANT_LAB, CONTROLLER_LAB):
            background = self.assets["background_night"]
        surface.blit(background, (0, 0))

    def _draw_menu_canvas(self, surface) -> None:
        pygame = self.pygame
        surface.blit(self.assets["message"], (SCREEN_WIDTH // 2 - self.assets["message"].get_width() // 2, 52))
        self._draw_bird_sprite(surface, SCREEN_WIDTH // 2 - 20, 186 + self._menu_bird_offset(), flap_phase=0.0)

        title = self.title_font.render("Control Theory Lab", True, PALETTE["ink"])
        subtitle = self.body_font.render("Play, identify, model, and close the loop.", True, PALETTE["muted"])
        surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 264))
        surface.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, 306))

        cards = [
            ("1", "Manual Play", "Classic Flappy Bird with live plant motion."),
            ("2", "Plant Lab", "Impulse, step, transfer-function, and Bode views."),
            ("3", "Controller Lab", "Tune on-off, PID, and polynomial controllers."),
            ("4", "Game Challenge", "Track pipe gaps and compare control strategies."),
        ]
        top = 226
        for index, (badge, heading, body) in enumerate(cards):
            rect = self.pygame.Rect(24 + (index % 2) * 182, top + (index // 2) * 138, 170, 116)
            pygame.draw.rect(surface, PALETTE["card"], rect, border_radius=16)
            pygame.draw.rect(surface, PALETTE["line"], rect, 1, border_radius=16)
            pygame.draw.circle(surface, PALETTE["accent"], (rect.left + 26, rect.top + 28), 16)
            surface.blit(self.body_font.render(badge, True, (255, 255, 255)), (rect.left + 20, rect.top + 17))
            surface.blit(self.heading_font.render(heading, True, PALETTE["ink"]), (rect.left + 18, rect.top + 52))
            self._draw_text_block(surface, body, self.small_font, PALETTE["muted"], self.pygame.Rect(rect.left + 18, rect.top + 82, rect.width - 32, 26))

        footer = self.pygame.Rect(24, 522, SCREEN_WIDTH - 48, 54)
        pygame.draw.rect(surface, (246, 241, 230), footer, border_radius=16)
        self._draw_text_block(
            surface,
            "The app is organized around the SDP: observe the plant, identify a model, tune a controller, and test it in the game.",
            self.body_font,
            PALETTE["ink"],
            self.pygame.Rect(footer.left + 18, footer.top + 14, footer.width - 36, footer.height - 18),
        )
        self._draw_base(surface, self._world_time())

    def _draw_simulation_canvas(self, surface) -> None:
        pygame = self.pygame
        base_y = self._base_y()
        target_y = self._target_for_render()
        self._draw_target_line(surface, target_y)
        target_label = self.tiny_font.render("target", True, (192, 107, 64))
        surface.blit(target_label, (12, max(8, int(target_y) - 18)))

        for pipe in self.sim.pipes:
            self._draw_pipe(surface, pipe.x, pipe.gap_y, pipe.gap_height, base_y)

        if self.result and self.mode in (PLANT_LAB, CONTROLLER_LAB, GAME_CHALLENGE):
            trace = []
            max_time = float(self.result.samples[-1]["time"]) if self.result.samples else 1.0
            for sample in self.result.samples:
                trace_x = 16 + (float(sample["time"]) / max(max_time, 1e-9)) * (SCREEN_WIDTH - 32)
                trace_y = float(sample["y"])
                trace.append((trace_x, trace_y))
            if len(trace) > 1:
                pygame.draw.lines(surface, PALETTE["ink"], False, trace, 2)

        bird_y = self.sim.state.y if self.mode == MANUAL else self._render_bird_y()
        self._draw_bird_sprite(surface, self.sim.plant.bird_x, bird_y, flap_phase=self._world_time())

        self._draw_base(surface, self._world_time())
        self._draw_score(surface)

        badge_rect = self.pygame.Rect(18, 18, 220, 52)
        pygame.draw.rect(surface, (252, 248, 240), badge_rect, border_radius=14)
        pygame.draw.rect(surface, PALETTE["line"], badge_rect, 1, border_radius=14)
        surface.blit(self.heading_font.render(self._mode_title(), True, PALETTE["ink"]), (30, 28))

        if self.mode == PLANT_LAB:
            stage, goal = LAB_STAGES[self.lab_stage]
            self._draw_world_note(surface, stage, goal)
        elif self.mode == CONTROLLER_LAB:
            self._draw_world_note(surface, self.controller.name, "Closed-loop altitude hold in the simplified plant environment.")
        elif self.mode == GAME_CHALLENGE:
            self._draw_world_note(surface, self.controller.name, "Closed-loop gap tracking through moving pipe constraints.")
        if self.mode == MANUAL and not self.sim.state.alive:
            gameover = self.assets["gameover"]
            surface.blit(gameover, (SCREEN_WIDTH // 2 - gameover.get_width() // 2, 132))

    def _draw_world_note(self, surface, title: str, body: str) -> None:
        pygame = self.pygame
        card = pygame.Rect(18, SCREEN_HEIGHT - 146, SCREEN_WIDTH - 36, 84)
        note_surface = pygame.Surface(card.size, pygame.SRCALPHA)
        pygame.draw.rect(note_surface, (252, 248, 240, 230), note_surface.get_rect(), border_radius=18)
        surface.blit(note_surface, card.topleft)
        pygame.draw.rect(surface, PALETTE["line"], card, 1, border_radius=18)
        surface.blit(self.heading_font.render(title, True, PALETTE["ink"]), (card.left + 18, card.top + 12))
        self._draw_text_block(surface, body, self.small_font, PALETTE["muted"], self.pygame.Rect(card.left + 18, card.top + 42, card.width - 36, 30))

    def _draw_sidebar(self, rect: tuple[int, int, int, int]) -> None:
        x, y, width, height = rect
        sidebar_rect = self.pygame.Rect(x, y, width, height)
        self._draw_panel(self.screen, sidebar_rect, PALETTE["panel"])

        inner = sidebar_rect.inflate(-18, -18)
        cursor = inner.top
        header_height = 124
        guide_height = 122
        summary_height = 184 if self.mode == PLANT_LAB else 206
        plot_gap = 12

        header_rect = self.pygame.Rect(inner.left, cursor, inner.width, header_height)
        self._draw_header_card(header_rect)
        cursor = header_rect.bottom + 12

        guide_rect = self.pygame.Rect(inner.left, cursor, inner.width, guide_height)
        self._draw_text_card(guide_rect, "Mode guide", self._guide_lines())
        cursor = guide_rect.bottom + 12

        summary_rect = self.pygame.Rect(inner.left, cursor, inner.width, summary_height)
        if self.mode == PLANT_LAB:
            self._draw_text_card(summary_rect, "Plant summary", self._plant_summary_lines())
        elif self.mode in (CONTROLLER_LAB, GAME_CHALLENGE):
            self._draw_text_card(summary_rect, "Controller summary", self._controller_summary_lines())
        else:
            self._draw_text_card(summary_rect, "Project purpose", self._menu_summary_lines())
        cursor = summary_rect.bottom + 12

        remaining = inner.bottom - cursor
        if self.plot and self.secondary_plot:
            plot_height = max(146, (remaining - plot_gap) // 2)
            top_plot = self.pygame.Rect(inner.left, cursor, inner.width, plot_height)
            bottom_plot = self.pygame.Rect(inner.left, top_plot.bottom + plot_gap, inner.width, inner.bottom - (top_plot.bottom + plot_gap))
            self._draw_plot_card(top_plot, self.plot)
            self._draw_plot_card(bottom_plot, self.secondary_plot)
        elif self.plot:
            plot_rect = self.pygame.Rect(inner.left, cursor, inner.width, max(180, remaining))
            self._draw_plot_card(plot_rect, self.plot)

    def _draw_header_card(self, rect) -> None:
        self._draw_card(rect)
        title = self.title_font.render(self._mode_title(), True, PALETTE["ink"])
        self.screen.blit(title, (rect.left + 20, rect.top + 16))
        self._draw_text_block(
            self.screen,
            self.status,
            self.body_font,
            PALETTE["muted"],
            self.pygame.Rect(rect.left + 20, rect.top + 62, rect.width - 40, rect.height - 76),
        )

    def _draw_text_card(self, rect, title: str, lines: list[str]) -> None:
        self._draw_card(rect)
        self.screen.blit(self.heading_font.render(title, True, PALETTE["ink"]), (rect.left + 18, rect.top + 14))
        text_rect = self.pygame.Rect(rect.left + 18, rect.top + 48, rect.width - 36, rect.height - 60)
        self._draw_lines_in_rect(self.screen, lines, self.small_font, PALETTE["muted"], text_rect)

    def _draw_plot_card(self, rect, plot: PlotData) -> None:
        self._draw_card(rect)
        title_surf = self.heading_font.render(plot.title, True, PALETTE["ink"])
        self.screen.blit(title_surf, (rect.left + 18, rect.top + 14))
        plot_area = self.pygame.Rect(rect.left + 18, rect.top + 52, rect.width - 36, rect.height - 88)
        self._draw_plot(self.screen, plot, plot_area)

        legend_x = rect.left + 18
        legend_y = rect.bottom - 28
        for label, _, color in plot.series[:4]:
            self.pygame.draw.circle(self.screen, color, (legend_x + 7, legend_y + 7), 5)
            label_surface = self.tiny_font.render(label, True, PALETTE["muted"])
            self.screen.blit(label_surface, (legend_x + 18, legend_y))
            legend_x += label_surface.get_width() + 42

    def _draw_panel(self, surface, rect, color: tuple[int, int, int]) -> None:
        shadow_rect = rect.move(0, 8)
        self.pygame.draw.rect(surface, PALETTE["shadow"], shadow_rect, border_radius=22)
        self.pygame.draw.rect(surface, color, rect, border_radius=22)
        self.pygame.draw.rect(surface, PALETTE["line"], rect, 1, border_radius=22)

    def _draw_card(self, rect) -> None:
        self.pygame.draw.rect(self.screen, PALETTE["card"], rect, border_radius=18)
        self.pygame.draw.rect(self.screen, PALETTE["line"], rect, 1, border_radius=18)

    def _draw_plot(self, surface, plot: PlotData, rect) -> None:
        self.pygame.draw.rect(surface, (253, 252, 248), rect, border_radius=14)
        self.pygame.draw.rect(surface, PALETTE["line"], rect, 1, border_radius=14)
        if not plot.series:
            return

        plot_rect = rect.inflate(-20, -22)
        all_points = [point for _, series, _ in plot.series for point in series]
        if not all_points:
            return

        xs = [point[0] for point in all_points]
        ys = [point[1] for point in all_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if abs(max_x - min_x) < 1e-9:
            max_x = min_x + 1.0
        if abs(max_y - min_y) < 1e-9:
            max_y = min_y + 1.0

        for fraction in (0.25, 0.5, 0.75):
            y_line = plot_rect.bottom - fraction * plot_rect.height
            self.pygame.draw.line(surface, (231, 226, 214), (plot_rect.left, y_line), (plot_rect.right, y_line), 1)
        self.pygame.draw.line(surface, PALETTE["line"], (plot_rect.left, plot_rect.bottom), (plot_rect.right, plot_rect.bottom), 1)
        self.pygame.draw.line(surface, PALETTE["line"], (plot_rect.left, plot_rect.top), (plot_rect.left, plot_rect.bottom), 1)

        for _, series, color in plot.series[:4]:
            converted = []
            for point_x, point_y in series:
                sx = plot_rect.left + (point_x - min_x) / (max_x - min_x) * plot_rect.width
                sy = plot_rect.bottom - (point_y - min_y) / (max_y - min_y) * plot_rect.height
                converted.append((sx, sy))
            if len(converted) > 1:
                self.pygame.draw.lines(surface, color, False, converted, 2)

        x_label = self.tiny_font.render(f"{min_x:.1f}s to {max_x:.1f}s", True, PALETTE["muted"])
        y_label = self.tiny_font.render(f"{min_y:.1f} to {max_y:.1f}", True, PALETTE["muted"])
        surface.blit(x_label, (plot_rect.left, rect.bottom - 24))
        surface.blit(y_label, (plot_rect.right - y_label.get_width(), plot_rect.top - 2))

    def _load_assets(self) -> dict[str, object]:
        pygame = self.pygame
        sprite_dir = self.asset_root / "sprites"

        def load_sprite(name: str):
            return pygame.image.load(str(sprite_dir / name)).convert_alpha()

        background_day = pygame.transform.smoothscale(load_sprite("background-day.png"), (SCREEN_WIDTH, SCREEN_HEIGHT))
        background_night = pygame.transform.smoothscale(load_sprite("background-night.png"), (SCREEN_WIDTH, SCREEN_HEIGHT))

        base_raw = load_sprite("base.png")
        base_height = 84
        base_width = int(base_raw.get_width() * (base_height / base_raw.get_height()))
        base = pygame.transform.smoothscale(base_raw, (base_width, base_height))

        pipe_raw = load_sprite("pipe-green.png")
        pipe_red_raw = load_sprite("pipe-red.png")
        pipe_width = 78

        bird_size = (54, 38)
        bird_frames = [
            pygame.transform.smoothscale(load_sprite("yellowbird-upflap.png"), bird_size),
            pygame.transform.smoothscale(load_sprite("yellowbird-midflap.png"), bird_size),
            pygame.transform.smoothscale(load_sprite("yellowbird-downflap.png"), bird_size),
        ]

        icon = pygame.transform.smoothscale(load_sprite("yellowbird-midflap.png"), (32, 32))
        message = pygame.transform.smoothscale(load_sprite("message.png"), (236, 342))
        gameover = pygame.transform.smoothscale(load_sprite("gameover.png"), (204, 56))

        digits: dict[str, object] = {}
        for digit in range(10):
            surface = load_sprite(f"{digit}.png")
            scaled = pygame.transform.smoothscale(surface, (int(surface.get_width() * 1.35), int(surface.get_height() * 1.35)))
            digits[str(digit)] = scaled

        return {
            "background_day": background_day,
            "background_night": background_night,
            "base": base,
            "pipe_green": pipe_raw,
            "pipe_red": pipe_red_raw,
            "pipe_width": pipe_width,
            "bird_frames": bird_frames,
            "message": message,
            "gameover": gameover,
            "digits": digits,
            "icon": icon,
        }

    def _draw_target_line(self, surface, y: float) -> None:
        dash = 10
        gap = 6
        x = 0
        while x < SCREEN_WIDTH:
            self.pygame.draw.line(surface, (192, 107, 64), (x, y), (min(SCREEN_WIDTH, x + dash), y), 2)
            x += dash + gap

    def _draw_pipe(self, surface, x: float, gap_y: float, gap_height: float, base_y: int) -> None:
        pygame = self.pygame
        pipe_sprite = self.assets["pipe_green"]
        pipe_width = self.assets["pipe_width"]
        gap_top = gap_y - gap_height / 2.0
        gap_bottom = gap_y + gap_height / 2.0
        top_height = max(12, int(gap_top))
        bottom_height = max(12, int(base_y - gap_bottom))

        top_pipe = pygame.transform.smoothscale(pipe_sprite, (pipe_width, top_height))
        top_pipe = pygame.transform.flip(top_pipe, False, True)
        bottom_pipe = pygame.transform.smoothscale(pipe_sprite, (pipe_width, bottom_height))

        surface.blit(top_pipe, (int(x), 0))
        surface.blit(bottom_pipe, (int(x), int(gap_bottom)))

    def _draw_base(self, surface, time_value: float) -> None:
        base = self.assets["base"]
        base_y = self._base_y()
        scroll_speed = 90.0
        width = base.get_width()
        offset = int((time_value * scroll_speed) % width)
        for tile_x in range(-offset, SCREEN_WIDTH + width, width):
            surface.blit(base, (tile_x, base_y))

    def _draw_bird_sprite(self, surface, x: float, y: float, flap_phase: float) -> None:
        pygame = self.pygame
        frame_index = int((flap_phase * 8.0) % len(self.assets["bird_frames"]))
        sprite = self.assets["bird_frames"][frame_index]
        rotation_source = self.sim.state.vy if self.mode == MANUAL else self._bird_velocity_hint()
        angle = max(-28.0, min(35.0, -rotation_source * 2.6))
        rotated = pygame.transform.rotozoom(sprite, angle, 1.0)
        rect = rotated.get_rect(center=(x + self.sim.plant.bird_width / 2, y + self.sim.plant.bird_height / 2))
        surface.blit(rotated, rect.topleft)

    def _draw_score(self, surface) -> None:
        if self.mode not in (MANUAL, GAME_CHALLENGE):
            return
        score = self._score_value()
        text = str(score)
        digits = [self.assets["digits"][digit] for digit in text]
        total_width = sum(digit.get_width() for digit in digits) + max(0, len(digits) - 1) * 2
        x = SCREEN_WIDTH // 2 - total_width // 2
        for digit in digits:
            surface.blit(digit, (x, 24))
            x += digit.get_width() + 2

    def _world_time(self) -> float:
        if self.mode == MANUAL:
            return self.sim.state.time
        if self.result and self.result.samples:
            return float(self.result.samples[-1]["time"])
        return self.pygame.time.get_ticks() / 1000.0

    def _menu_bird_offset(self) -> int:
        return int(8.0 * math.sin(self.pygame.time.get_ticks() / 250.0))

    def _bird_velocity_hint(self) -> float:
        if self.result and self.result.samples:
            return float(self.result.samples[-1].get("vy", 0.0))
        return self.sim.state.vy

    def _base_y(self) -> int:
        return SCREEN_HEIGHT - self.assets["base"].get_height()

    def _score_value(self) -> int:
        if self.mode == MANUAL:
            return int(self.sim.score)
        if self.result and self.result.samples:
            return int(self.result.samples[-1].get("score", 0))
        return 0

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

    def _guide_lines(self) -> list[str]:
        if self.mode == MENU:
            return [
                "1 Manual Play: classic interaction with the bird plant.",
                "2 Plant Lab: impulse, step, model fit, and Bode analysis.",
                "3 Controller Lab: altitude control with on-off, PID, and polynomial controllers.",
                "4 Game Challenge: close the loop against moving pipe-gap targets.",
            ]
        if self.mode == MANUAL:
            return ["Space flap", "R restart", "Esc menu"]
        if self.mode == PLANT_LAB:
            stage, goal = LAB_STAGES[self.lab_stage]
            return [
                f"Stage: {stage}",
                f"Goal: {goal}",
                "I impulse | S step | M model | B Bode | E export | P plot export",
            ]
        return [
            "1/2/3 choose controller",
            "Tab select parameter",
            "+/- tune current parameter",
            "R rerun | E export | P plot export",
        ]

    def _menu_summary_lines(self) -> list[str]:
        return [
            "Purpose: turn a Flappy Bird prototype into a control-theory learning tool.",
            "Workflow: observe the plant, derive a model, tune a controller, test it in the game.",
            "Plan: the SDP in SDP.md drives the module structure and educational progression.",
            "Repo docs: README.md explains usage and goals; CHANGELOG.md tracks milestones.",
        ]

    def _plant_summary_lines(self) -> list[str]:
        params = self.sim.plant
        analytic = analytic_transfer_function(params)
        fit = self.result.model.fit_quality if self.result else 0.0
        lines = [
            f"Plant: gravity={params.gravity:.2f}, flap={params.flap_impulse:.2f}, drag={params.drag:.2f}, dt={params.dt:.4f}",
            f"Analytic model: {analytic.pretty()}",
            f"Identified fit quality: {fit:.3f}",
        ]
        if self.result:
            lines.extend(self.result.notes[:3])
        return lines

    def _controller_summary_lines(self) -> list[str]:
        controller = self.controller
        lines = [f"Controller family: {controller.name}"]
        for index, key in enumerate(controller.editable_parameters()):
            marker = ">" if index == self.selected_parameter else "-"
            value = getattr(controller, key, None)
            if value is None and isinstance(controller, TransferFunctionController):
                if key == "num0":
                    value = controller.numerator[0]
                elif key == "num1":
                    value = controller.numerator[1] if len(controller.numerator) > 1 else 0.0
                elif key == "den1":
                    value = controller.denominator[1] if len(controller.denominator) > 1 else 0.0
                elif key == "den2":
                    value = controller.denominator[2] if len(controller.denominator) > 2 else 0.0
            lines.append(f"{marker} {key}={float(value):.3f}")

        if isinstance(controller, TransferFunctionController):
            lines.append(f"Polynomial form: {controller.summary()}")
        if self.result:
            metrics = self.result.metrics
            lines.extend(
                [
                    f"rise={_fmt_metric(metrics.get('rise_time'))}  settle={_fmt_metric(metrics.get('settling_time'))}",
                    f"overshoot={_fmt_metric(metrics.get('overshoot'))}  sse={_fmt_metric(metrics.get('steady_state_error'))}",
                    f"effort={_fmt_metric(metrics.get('control_effort'))}  flaps={_fmt_metric(metrics.get('flap_count'))}",
                    f"survival={_fmt_metric(metrics.get('survival_time'))}  crash={metrics.get('crash_reason')}",
                ]
            )
        return lines

    def _mode_title(self) -> str:
        return {
            MENU: "Main Menu",
            MANUAL: "Manual Play",
            PLANT_LAB: "Plant Lab",
            CONTROLLER_LAB: "Controller Lab",
            GAME_CHALLENGE: "Game Challenge",
        }[self.mode]

    def _render_bird_y(self) -> float:
        if self.result and self.result.samples:
            return float(self.result.samples[-1]["y"])
        return self.sim.state.y

    def _target_for_render(self) -> float:
        if self.mode == PLANT_LAB and self.result:
            return float(self.result.spec.target_y or SCREEN_HEIGHT / 2)
        if self.result and self.result.samples:
            sample = self.result.samples[-1]
            return float(sample.get("next_pipe_gap_y") or sample.get("target_y") or SCREEN_HEIGHT / 2)
        return SCREEN_HEIGHT / 2

    def _series(
        self,
        samples: Sequence[dict[str, float | bool | str | None]],
        key: str,
        *,
        scale: float = 1.0,
        offset: float = 0.0,
    ) -> list[tuple[float, float]]:
        return [(float(sample["time"]), float(sample.get(key, 0.0)) * scale + offset) for sample in samples]

    def _constant_series(self, samples: Sequence[dict[str, float | bool | str | None]], value: float) -> list[tuple[float, float]]:
        return [(float(sample["time"]), value) for sample in samples]

    def _export_current_result(self) -> None:
        if not self.result:
            self.status = "No experiment result to export."
            return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = os.path.join("exports", f"{self.mode}-{timestamp}")
        self.result.export_csv(base + ".csv")
        self.result.export_json(base + ".json")
        self.status = f"Exported data to {base}.csv and {base}.json."

    def _export_current_plot(self) -> None:
        if not self.plot:
            self.status = "No plot to export."
            return
        try:
            import matplotlib.pyplot as plt
        except Exception:
            self.status = "matplotlib is not installed; CSV and JSON export still work."
            return

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join("exports", f"{self.mode}-{timestamp}.png")
        figure, axis = plt.subplots(figsize=(8, 4))
        for label, series, _ in self.plot.series:
            axis.plot([x for x, _ in series], [y for _, y in series], label=label)
        axis.set_title(self.plot.title)
        axis.legend()
        axis.grid(True, alpha=0.25)
        figure.tight_layout()
        figure.savefig(path)
        plt.close(figure)
        self.status = f"Exported plot to {path}."


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


def controller_transfer_model(controller: BaseController) -> TransferFunctionModel:
    if hasattr(controller, "kp") and hasattr(controller, "ki") and hasattr(controller, "kd"):
        kp = float(getattr(controller, "kp"))
        ki = float(getattr(controller, "ki"))
        kd = float(getattr(controller, "kd"))
        return TransferFunctionModel(
            numerator=[kd, kp, ki],
            denominator=[1.0, 0.0],
            delay=0.0,
            fit_quality=1.0,
            source_method="controller",
            description="PID controller model",
        )
    if isinstance(controller, TransferFunctionController):
        return TransferFunctionModel(
            numerator=controller.numerator[:],
            denominator=controller.denominator[:],
            delay=0.0,
            fit_quality=1.0,
            source_method="controller",
            description="Polynomial controller model",
        )
    return TransferFunctionModel(
        numerator=[1.0],
        denominator=[1.0],
        delay=0.0,
        fit_quality=1.0,
        source_method="controller",
        description="On-off controller approximated as unit gain",
    )


def simulate_transfer_response(
    model: TransferFunctionModel,
    samples: Sequence[dict[str, float | bool | str | None]],
    plant: PlantParams,
) -> list[tuple[float, float]]:
    if not samples:
        return []
    y = float(samples[0]["y"])
    v = 0.0
    gain = -model.numerator[-1] if model.numerator else 0.0
    drag = model.denominator[1] if len(model.denominator) > 1 else plant.drag
    response: list[tuple[float, float]] = []
    for sample in samples:
        u = 1.0 if sample.get("flap") else 0.0
        acceleration = plant.gravity - drag * v - gain * u
        v += acceleration * plant.dt
        y += v * plant.dt
        response.append((float(sample["time"]), y))
    return response


def _fmt_metric(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    if value is None:
        return "-"
    return str(value)


def run_app() -> None:
    try:
        app = ControlTheoryApp()
    except Exception as error:
        raise SystemExit(
            "Unable to start the PyGame UI. Install dependencies from requirements.txt first. "
            f"Original error: {error}"
        ) from error
    app.run()
