from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import random
from typing import Callable


SCREEN_WIDTH = 400
SCREEN_HEIGHT = 600


@dataclass
class PlantParams:
    gravity: float = 18.0
    flap_impulse: float = 9.5
    dt: float = 1.0 / 30.0
    drag: float = 1.2
    y_min: float = 0.0
    y_max: float = SCREEN_HEIGHT
    v_min: float = -16.0
    v_max: float = 18.0
    bird_x: float = 70.0
    bird_width: int = 40
    bird_height: int = 30


@dataclass
class BirdState:
    time: float
    y: float
    vy: float
    ay: float
    alive: bool = True


@dataclass
class PipeState:
    x: float
    gap_y: float
    gap_height: float
    width: float
    scored: bool = False


@dataclass
class Observation:
    state: BirdState
    target_y: float
    next_pipe_gap_y: float | None
    next_pipe_distance: float | None
    score: int
    pipes_enabled: bool


@dataclass
class ControlCommand:
    flap: bool = False
    effort: float = 0.0
    label: str = ""


@dataclass
class ExperimentSpec:
    name: str
    duration: float
    initial_y: float
    initial_vy: float = 0.0
    target_y: float | None = None
    pipes_enabled: bool = False
    input_profile: str = "manual"
    sample_rate: float | None = None


@dataclass
class TransferFunctionModel:
    numerator: list[float]
    denominator: list[float]
    delay: float
    fit_quality: float
    source_method: str
    description: str

    def pretty(self) -> str:
        num = " + ".join(_poly_term(c, len(self.numerator) - i - 1) for i, c in enumerate(self.numerator) if abs(c) > 1e-9) or "0"
        den = " + ".join(_poly_term(c, len(self.denominator) - i - 1) for i, c in enumerate(self.denominator) if abs(c) > 1e-9) or "1"
        return f"G(s)=({num})/({den})"


@dataclass
class ExperimentResult:
    spec: ExperimentSpec
    samples: list[dict[str, float | bool | str | None]]
    impulse_response: list[float]
    step_response: list[float]
    metrics: dict[str, float | str | None]
    model: TransferFunctionModel
    notes: list[str] = field(default_factory=list)

    def export_csv(self, path: str) -> None:
        if not self.samples:
            return
        headers = list(self.samples[0].keys())
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(",".join(headers) + "\n")
            for row in self.samples:
                handle.write(",".join(_csv_value(row.get(header)) for header in headers) + "\n")

    def export_json(self, path: str) -> None:
        payload = {
            "spec": self.spec.__dict__,
            "samples": self.samples,
            "impulse_response": self.impulse_response,
            "step_response": self.step_response,
            "metrics": self.metrics,
            "model": self.model.__dict__,
            "notes": self.notes,
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)


@dataclass
class SimulationConfig:
    screen_width: int = SCREEN_WIDTH
    screen_height: int = SCREEN_HEIGHT
    pipe_gap: float = 190.0
    pipe_width: float = 70.0
    pipe_spacing: float = 240.0
    pipe_speed: float = 120.0
    score_zone_x: float = 70.0
    pipe_min_y: float = 110.0
    pipe_max_y: float = 490.0


class FlappySimulation:
    """Deterministic simulation core shared by gameplay and lab tooling."""

    def __init__(
        self,
        plant: PlantParams | None = None,
        config: SimulationConfig | None = None,
        seed: int = 7,
    ) -> None:
        self.plant = plant or PlantParams()
        self.config = config or SimulationConfig()
        self.random = random.Random(seed)
        self.seed = seed
        self.reset()

    def reset(
        self,
        *,
        initial_y: float | None = None,
        initial_vy: float = 0.0,
        pipes_enabled: bool = True,
        target_y: float | None = None,
    ) -> None:
        y = initial_y if initial_y is not None else self.config.screen_height / 2.0
        self.state = BirdState(time=0.0, y=y, vy=initial_vy, ay=0.0, alive=True)
        self.target_y = target_y if target_y is not None else self.config.screen_height / 2.0
        self.pipes_enabled = pipes_enabled
        self.score = 0
        self.last_crash_reason = ""
        self.last_flap = False
        self.pipes: list[PipeState] = []
        self.random.seed(self.seed)
        if pipes_enabled:
            self._spawn_pipe(self.config.screen_width + 100)

    def observe(self) -> Observation:
        next_pipe = self.next_pipe()
        return Observation(
            state=BirdState(
                time=self.state.time,
                y=self.state.y,
                vy=self.state.vy,
                ay=self.state.ay,
                alive=self.state.alive,
            ),
            target_y=self.target_y,
            next_pipe_gap_y=next_pipe.gap_y if next_pipe else None,
            next_pipe_distance=(next_pipe.x - self.plant.bird_x) if next_pipe else None,
            score=self.score,
            pipes_enabled=self.pipes_enabled,
        )

    def next_pipe(self) -> PipeState | None:
        upcoming = [pipe for pipe in self.pipes if pipe.x + pipe.width >= self.plant.bird_x]
        return min(upcoming, key=lambda pipe: pipe.x, default=None)

    def step(self, command: ControlCommand | None = None) -> dict[str, float | bool | str | None]:
        command = command or ControlCommand()
        flap = bool(command.flap)
        self.last_flap = flap

        acceleration = self.plant.gravity - self.plant.drag * self.state.vy
        if flap:
            acceleration -= self.plant.flap_impulse / max(self.plant.dt, 1e-9)

        self.state.ay = acceleration
        self.state.vy += acceleration * self.plant.dt
        self.state.vy = max(self.plant.v_min, min(self.state.vy, self.plant.v_max))
        self.state.y += self.state.vy * self.plant.dt
        self.state.time += self.plant.dt

        if self.pipes_enabled:
            self._update_pipes()
            self._check_pipe_collisions()
        self._check_bounds()

        next_pipe = self.next_pipe()
        return {
            "time": self.state.time,
            "y": self.state.y,
            "vy": self.state.vy,
            "ay": self.state.ay,
            "target_y": self.target_y,
            "control_effort": float(command.effort),
            "flap": flap,
            "score": self.score,
            "alive": self.state.alive,
            "next_pipe_gap_y": next_pipe.gap_y if next_pipe else None,
            "next_pipe_distance": (next_pipe.x - self.plant.bird_x) if next_pipe else None,
            "crash_reason": self.last_crash_reason,
            "controller_label": command.label,
        }

    def _spawn_pipe(self, x: float | None = None) -> None:
        gap_y = self.random.uniform(self.config.pipe_min_y, self.config.pipe_max_y)
        self.pipes.append(
            PipeState(
                x=x if x is not None else self.config.screen_width + 40,
                gap_y=gap_y,
                gap_height=self.config.pipe_gap,
                width=self.config.pipe_width,
            )
        )

    def _update_pipes(self) -> None:
        for pipe in self.pipes:
            pipe.x -= self.config.pipe_speed * self.plant.dt
            if not pipe.scored and pipe.x + pipe.width < self.config.score_zone_x:
                pipe.scored = True
                self.score += 1
        self.pipes = [pipe for pipe in self.pipes if pipe.x + pipe.width > 0]
        if not self.pipes or self.pipes[-1].x < self.config.screen_width - self.config.pipe_spacing:
            self._spawn_pipe()

    def _check_pipe_collisions(self) -> None:
        top = self.state.y
        bottom = self.state.y + self.plant.bird_height
        left = self.plant.bird_x
        right = self.plant.bird_x + self.plant.bird_width

        for pipe in self.pipes:
            pipe_left = pipe.x
            pipe_right = pipe.x + pipe.width
            gap_top = pipe.gap_y - pipe.gap_height / 2.0
            gap_bottom = pipe.gap_y + pipe.gap_height / 2.0

            overlaps_x = right >= pipe_left and left <= pipe_right
            in_gap = top >= gap_top and bottom <= gap_bottom
            if overlaps_x and not in_gap:
                self.state.alive = False
                self.last_crash_reason = "pipe"
                return

    def _check_bounds(self) -> None:
        if self.state.y <= self.plant.y_min:
            self.state.y = self.plant.y_min
            self.state.alive = False
            self.last_crash_reason = "ceiling"
        elif self.state.y + self.plant.bird_height >= self.plant.y_max:
            self.state.y = self.plant.y_max - self.plant.bird_height
            self.state.alive = False
            self.last_crash_reason = "ground"

    def run_experiment(
        self,
        spec: ExperimentSpec,
        command_fn: Callable[[Observation, float], ControlCommand],
    ) -> ExperimentResult:
        self.reset(
            initial_y=spec.initial_y,
            initial_vy=spec.initial_vy,
            pipes_enabled=spec.pipes_enabled,
            target_y=spec.target_y,
        )
        samples: list[dict[str, float | bool | str | None]] = []
        steps = max(1, int(spec.duration / self.plant.dt))
        for _ in range(steps):
            observation = self.observe()
            sample = self.step(command_fn(observation, self.plant.dt))
            samples.append(sample)
            if not self.state.alive and spec.pipes_enabled:
                break

        from .analytics import derive_experiment_result

        return derive_experiment_result(spec, samples, self.plant)


def _poly_term(coefficient: float, degree: int) -> str:
    coefficient_text = f"{coefficient:.3g}"
    if degree == 0:
        return coefficient_text
    if degree == 1:
        return f"{coefficient_text}s"
    return f"{coefficient_text}s^{degree}"


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return f"{value:.8f}"
    text = str(value)
    if "," in text:
        return '"' + text.replace('"', '""') + '"'
    return text
