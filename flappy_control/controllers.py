from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

from .core import ControlCommand, Observation


class BaseController:
    name = "Base"

    def reset(self) -> None:
        return

    def update(self, observation: Observation, dt: float) -> ControlCommand:
        return ControlCommand()

    def editable_parameters(self) -> list[str]:
        return []

    def adjust(self, key: str, delta: float) -> None:
        if hasattr(self, key):
            setattr(self, key, getattr(self, key) + delta)


@dataclass
class OnOffController(BaseController):
    name: str = "On-Off"
    deadband: float = 16.0
    hysteresis: float = 6.0
    min_interval: float = 0.12
    _latched: bool = field(default=False, init=False)
    _time_since_flap: float = field(default=999.0, init=False)

    def reset(self) -> None:
        self._latched = False
        self._time_since_flap = 999.0

    def update(self, observation: Observation, dt: float) -> ControlCommand:
        self._time_since_flap += dt
        error = observation.state.y - observation.target_y
        high_threshold = self.deadband + self.hysteresis
        low_threshold = max(0.0, self.deadband - self.hysteresis)

        if error > high_threshold:
            self._latched = True
        elif error < low_threshold:
            self._latched = False

        flap = self._latched and self._time_since_flap >= self.min_interval
        if flap:
            self._time_since_flap = 0.0
        return ControlCommand(flap=flap, effort=1.0 if self._latched else 0.0, label=self.name)

    def editable_parameters(self) -> list[str]:
        return ["deadband", "hysteresis", "min_interval"]


@dataclass
class PIDController(BaseController):
    name: str = "PID"
    kp: float = 0.065
    ki: float = 0.018
    kd: float = 0.045
    derivative_filter: float = 0.18
    output_min: float = 0.0
    output_max: float = 1.0
    anti_windup: float = 0.5
    min_interval: float = 0.08
    integral: float = field(default=0.0, init=False)
    prev_error: float = field(default=0.0, init=False)
    filtered_derivative: float = field(default=0.0, init=False)
    pulse_accumulator: float = field(default=0.0, init=False)
    time_since_flap: float = field(default=999.0, init=False)

    def reset(self) -> None:
        self.integral = 0.0
        self.prev_error = 0.0
        self.filtered_derivative = 0.0
        self.pulse_accumulator = 0.0
        self.time_since_flap = 999.0

    def update(self, observation: Observation, dt: float) -> ControlCommand:
        self.time_since_flap += dt
        error = observation.state.y - observation.target_y
        raw_derivative = (error - self.prev_error) / max(dt, 1e-9)
        alpha = max(0.0, min(1.0, self.derivative_filter))
        self.filtered_derivative = alpha * self.filtered_derivative + (1.0 - alpha) * raw_derivative

        proposed_integral = self.integral + error * dt
        output = self.kp * error + self.ki * proposed_integral + self.kd * self.filtered_derivative
        clamped = max(self.output_min, min(self.output_max, output))

        if abs(output - clamped) < 1e-9:
            self.integral = proposed_integral
        else:
            self.integral += self.anti_windup * (clamped - output) * dt

        self.prev_error = error
        self.pulse_accumulator += clamped
        flap = self.pulse_accumulator >= 1.0 and self.time_since_flap >= self.min_interval
        if flap:
            self.pulse_accumulator -= 1.0
            self.time_since_flap = 0.0
        return ControlCommand(flap=flap, effort=clamped, label=self.name)

    def editable_parameters(self) -> list[str]:
        return [
            "kp",
            "ki",
            "kd",
            "derivative_filter",
            "anti_windup",
            "min_interval",
        ]


@dataclass
class TransferFunctionController(BaseController):
    name: str = "Polynomial"
    numerator: list[float] = field(default_factory=lambda: [0.22, 0.12])
    denominator: list[float] = field(default_factory=lambda: [1.0, 1.6, 0.7])
    output_min: float = 0.0
    output_max: float = 1.0
    min_interval: float = 0.08
    _error_history: list[float] = field(default_factory=list, init=False)
    _output_history: list[float] = field(default_factory=list, init=False)
    _pulse_accumulator: float = field(default=0.0, init=False)
    _time_since_flap: float = field(default=999.0, init=False)

    def reset(self) -> None:
        self._error_history.clear()
        self._output_history.clear()
        self._pulse_accumulator = 0.0
        self._time_since_flap = 999.0

    def update(self, observation: Observation, dt: float) -> ControlCommand:
        self._time_since_flap += dt
        error = observation.state.y - observation.target_y
        bz, az = continuous_tf_to_discrete(self.numerator, self.denominator, dt)
        self._error_history.insert(0, error)
        self._output_history.insert(0, 0.0)
        self._error_history = self._error_history[: len(bz)]
        self._output_history = self._output_history[: len(az)]

        value = 0.0
        for index, coefficient in enumerate(bz):
            if index < len(self._error_history):
                value += coefficient * self._error_history[index]
        for index in range(1, len(az)):
            if index - 1 < len(self._output_history):
                value -= az[index] * self._output_history[index - 1]
        value /= az[0]

        value = max(self.output_min, min(self.output_max, value))
        self._output_history[0] = value
        self._pulse_accumulator += value
        flap = self._pulse_accumulator >= 1.0 and self._time_since_flap >= self.min_interval
        if flap:
            self._pulse_accumulator -= 1.0
            self._time_since_flap = 0.0
        return ControlCommand(flap=flap, effort=value, label=self.name)

    def editable_parameters(self) -> list[str]:
        return ["num0", "num1", "den1", "den2", "min_interval"]

    def adjust(self, key: str, delta: float) -> None:
        if key == "num0":
            self.numerator[0] += delta
        elif key == "num1":
            if len(self.numerator) == 1:
                self.numerator.append(delta)
            else:
                self.numerator[1] += delta
        elif key == "den1":
            if len(self.denominator) < 2:
                self.denominator.append(1.0)
            self.denominator[1] += delta
        elif key == "den2":
            if len(self.denominator) < 3:
                while len(self.denominator) < 3:
                    self.denominator.append(0.0)
            self.denominator[2] += delta
        elif key == "min_interval":
            self.min_interval = max(0.02, self.min_interval + delta)

    def summary(self) -> str:
        num = ", ".join(f"{value:.3f}" for value in self.numerator)
        den = ", ".join(f"{value:.3f}" for value in self.denominator)
        return f"N=[{num}] D=[{den}]"


def controller_factory() -> list[BaseController]:
    return [
        OnOffController(),
        PIDController(),
        TransferFunctionController(),
    ]


def continuous_tf_to_discrete(numerator: Iterable[float], denominator: Iterable[float], dt: float) -> tuple[list[float], list[float]]:
    """Backward-Euler substitution s=(1-z^-1)/dt -> causal IIR coefficients."""
    num = [float(value) for value in numerator]
    den = [float(value) for value in denominator]
    order = max(len(num), len(den)) - 1
    num = [0.0] * (order + 1 - len(num)) + num
    den = [0.0] * (order + 1 - len(den)) + den

    q = [-1.0 / dt, 1.0 / dt]
    num_poly = _expand_poly(num, q)
    den_poly = _expand_poly(den, q)
    num_poly = _pad_leading(num_poly, len(den_poly))
    den_poly = _pad_leading(den_poly, len(num_poly))

    az = den_poly[:]
    bz = num_poly[:]
    lead = az[0]
    if abs(lead) < 1e-9:
        return [0.0, 0.0], [1.0, 0.0]
    az = [value / lead for value in az]
    bz = [value / lead for value in bz]
    return list(reversed(bz)), list(reversed(az))


def _expand_poly(coefficients: list[float], q: list[float]) -> list[float]:
    order = len(coefficients) - 1
    result = [0.0]
    for index, coefficient in enumerate(coefficients):
        power = order - index
        term = [1.0]
        for _ in range(power):
            term = _convolve(term, q)
        term = [coefficient * value for value in term]
        result = _poly_add(result, term)
    return result


def _convolve(left: list[float], right: list[float]) -> list[float]:
    result = [0.0] * (len(left) + len(right) - 1)
    for i, left_value in enumerate(left):
        for j, right_value in enumerate(right):
            result[i + j] += left_value * right_value
    return result


def _poly_add(left: list[float], right: list[float]) -> list[float]:
    left = _pad_leading(left, len(right))
    right = _pad_leading(right, len(left))
    return [a + b for a, b in zip(left, right)]


def _pad_leading(values: list[float], length: int) -> list[float]:
    if len(values) >= length:
        return values[:]
    return [0.0] * (length - len(values)) + values
