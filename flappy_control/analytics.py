from __future__ import annotations

from dataclasses import dataclass
import math

from .core import ExperimentResult, ExperimentSpec, PlantParams, TransferFunctionModel


def derive_experiment_result(
    spec: ExperimentSpec,
    samples: list[dict[str, float | bool | str | None]],
    plant: PlantParams,
) -> ExperimentResult:
    detrended_y = _detrend_signal(samples, "y")
    impulse_response = _estimate_impulse_response(detrended_y)
    step_response = integrate_response(impulse_response, plant.dt)
    metrics = compute_time_metrics(samples, spec.target_y)
    model = identify_transfer_function(samples, plant)
    notes = build_lab_notes(spec, plant, model)
    return ExperimentResult(
        spec=spec,
        samples=samples,
        impulse_response=impulse_response,
        step_response=step_response,
        metrics=metrics,
        model=model,
        notes=notes,
    )


def compute_time_metrics(
    samples: list[dict[str, float | bool | str | None]],
    target_y: float | None,
) -> dict[str, float | str | None]:
    if not samples:
        return {}

    times = [float(sample["time"]) for sample in samples]
    ys = [float(sample["y"]) for sample in samples]
    flaps = sum(1 for sample in samples if sample.get("flap"))
    alive = bool(samples[-1].get("alive", True))
    final_y = ys[-1]
    target = target_y if target_y is not None else ys[0]
    initial_error = ys[0] - target
    final_error = final_y - target
    peak_error = max(abs(y - target) for y in ys)
    overshoot = max(0.0, peak_error - abs(initial_error))

    settling_time = None
    band = 12.0
    for index in range(len(ys)):
        tail = ys[index:]
        if all(abs(value - target) <= band for value in tail):
            settling_time = times[index]
            break

    rise_time = None
    if abs(initial_error) > 1e-9:
        threshold = 0.1 * abs(initial_error)
        for time_value, value in zip(times, ys):
            if abs(value - target) <= threshold:
                rise_time = time_value
                break

    return {
        "rise_time": rise_time,
        "overshoot": overshoot,
        "settling_time": settling_time,
        "steady_state_error": final_error,
        "control_effort": sum(float(sample.get("control_effort", 0.0)) for sample in samples),
        "flap_count": float(flaps),
        "survival_time": times[-1],
        "crash_reason": "stable" if alive else str(samples[-1].get("crash_reason", "unknown")),
    }


def identify_transfer_function(
    samples: list[dict[str, float | bool | str | None]],
    plant: PlantParams,
) -> TransferFunctionModel:
    if len(samples) < 3:
        return TransferFunctionModel(
            numerator=[0.0],
            denominator=[1.0],
            delay=0.0,
            fit_quality=0.0,
            source_method="identified",
            description="Insufficient samples",
        )

    dt = plant.dt
    phi_rows: list[tuple[float, float, float]] = []
    outputs: list[float] = []
    for previous, current in zip(samples[:-1], samples[1:]):
        vy = float(previous["vy"])
        flap = 1.0 if previous.get("flap") else 0.0
        measured_acc = (float(current["vy"]) - vy) / max(dt, 1e-9)
        phi_rows.append((vy, flap, 1.0))
        outputs.append(measured_acc)

    a, b, c = solve_normal_equations(phi_rows, outputs)
    drag = max(0.0, -a)
    gain = max(0.001, -b)
    predicted = [a * vy + b * flap + c for vy, flap, _ in phi_rows]
    residual = rmse(outputs, predicted)
    baseline = max(rmse(outputs, [sum(outputs) / len(outputs)] * len(outputs)), 1e-9)
    fit_quality = max(0.0, 1.0 - residual / baseline)

    description = (
        "Continuous approximation from sampled bird dynamics: "
        "y'' + a y' = -b u + bias"
    )
    return TransferFunctionModel(
        numerator=[-gain],
        denominator=[1.0, drag, 0.0],
        delay=0.0,
        fit_quality=fit_quality,
        source_method="identified",
        description=description,
    )


def analytic_transfer_function(plant: PlantParams) -> TransferFunctionModel:
    return TransferFunctionModel(
        numerator=[-plant.flap_impulse / max(plant.dt, 1e-9)],
        denominator=[1.0, plant.drag, 0.0],
        delay=0.0,
        fit_quality=1.0,
        source_method="analytic",
        description="Continuous approximation derived from the simulation update law.",
    )


def integrate_response(signal: list[float], dt: float) -> list[float]:
    total = 0.0
    integrated: list[float] = []
    for value in signal:
        total += value * dt
        integrated.append(total)
    return integrated


def bode_points(
    model: TransferFunctionModel,
    count: int = 100,
    start: float = 0.1,
    stop: float = 15.0,
) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for index in range(count):
        ratio = index / max(1, count - 1)
        frequency = start * ((stop / start) ** ratio)
        s = complex(0.0, frequency)
        numerator = evaluate_polynomial(model.numerator, s)
        denominator = evaluate_polynomial(model.denominator, s)
        if abs(denominator) < 1e-12:
            continue
        value = numerator / denominator
        magnitude = 20.0 * math.log10(max(abs(value), 1e-12))
        phase = math.degrees(math.atan2(value.imag, value.real))
        points.append((frequency, magnitude, phase))
    return points


def closed_loop_bode(
    plant_model: TransferFunctionModel,
    controller_model: TransferFunctionModel,
    count: int = 100,
) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for frequency, _, _ in bode_points(plant_model, count=count):
        s = complex(0.0, frequency)
        plant_value = evaluate_polynomial(plant_model.numerator, s) / evaluate_polynomial(plant_model.denominator, s)
        controller_value = evaluate_polynomial(controller_model.numerator, s) / evaluate_polynomial(controller_model.denominator, s)
        loop = plant_value * controller_value
        value = loop / (1.0 + loop)
        magnitude = 20.0 * math.log10(max(abs(value), 1e-12))
        phase = math.degrees(math.atan2(value.imag, value.real))
        points.append((frequency, magnitude, phase))
    return points


def evaluate_polynomial(coefficients: list[float], variable: complex) -> complex:
    result = complex(0.0, 0.0)
    order = len(coefficients) - 1
    for index, coefficient in enumerate(coefficients):
        power = order - index
        result += coefficient * (variable ** power)
    return result


def solve_normal_equations(rows: list[tuple[float, ...]], outputs: list[float]) -> tuple[float, ...]:
    width = len(rows[0])
    gram = [[0.0 for _ in range(width)] for _ in range(width)]
    rhs = [0.0 for _ in range(width)]

    for row, output in zip(rows, outputs):
        for i in range(width):
            rhs[i] += row[i] * output
            for j in range(width):
                gram[i][j] += row[i] * row[j]

    return gaussian_elimination(gram, rhs)


def gaussian_elimination(matrix: list[list[float]], rhs: list[float]) -> tuple[float, ...]:
    size = len(rhs)
    for pivot in range(size):
        best_row = max(range(pivot, size), key=lambda index: abs(matrix[index][pivot]))
        matrix[pivot], matrix[best_row] = matrix[best_row], matrix[pivot]
        rhs[pivot], rhs[best_row] = rhs[best_row], rhs[pivot]
        pivot_value = matrix[pivot][pivot]
        if abs(pivot_value) < 1e-9:
            continue
        for column in range(pivot, size):
            matrix[pivot][column] /= pivot_value
        rhs[pivot] /= pivot_value
        for row in range(size):
            if row == pivot:
                continue
            factor = matrix[row][pivot]
            for column in range(pivot, size):
                matrix[row][column] -= factor * matrix[pivot][column]
            rhs[row] -= factor * rhs[pivot]
    return tuple(rhs)


def rmse(left: list[float], right: list[float]) -> float:
    if not left:
        return 0.0
    mean_square = sum((a - b) ** 2 for a, b in zip(left, right)) / len(left)
    return math.sqrt(mean_square)


def build_lab_notes(
    spec: ExperimentSpec,
    plant: PlantParams,
    model: TransferFunctionModel,
) -> list[str]:
    analytic = analytic_transfer_function(plant)
    return [
        f"Experiment: {spec.name}",
        "Model the bird vertical dynamics as y'' + a y' = -b u + g.",
        f"Analytic approximation: {analytic.pretty()}",
        f"Identified model fit: {model.pretty()} with quality={model.fit_quality:.3f}",
        "Impulse response comes from one flap event; step response is the time integral of the impulse response.",
        "Use the Bode plot to connect controller aggressiveness to crossover and phase lag.",
    ]


def _detrend_signal(samples: list[dict[str, float | bool | str | None]], key: str) -> list[float]:
    values = [float(sample[key]) for sample in samples]
    baseline = values[0] if values else 0.0
    return [value - baseline for value in values]


def _estimate_impulse_response(values: list[float]) -> list[float]:
    if len(values) < 2:
        return values
    response = [0.0]
    for previous, current in zip(values[:-1], values[1:]):
        response.append(current - previous)
    return response
