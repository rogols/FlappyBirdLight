# Flappy Bird Control Theory Lab

Flappy Bird Control Theory Lab turns a minimal PyGame Flappy Bird prototype into a learning environment for introductory control theory. Students can move from manual play to plant identification, transfer-function reasoning, controller tuning, and closed-loop gameplay in one application.

## Purpose

The project is designed for students who are learning:
- open-loop and closed-loop behavior
- impulse and step response
- transfer functions in polynomial form
- on-off control, PID control, and higher-order compensators
- how modeling assumptions affect controller performance

The bird is treated as the control object. The app exposes the bird dynamics as a reusable plant, lets students run repeatable experiments, and visualizes both time-domain and frequency-domain behavior.

## Learning Flow

The intended classroom progression is:
1. Play the game manually and observe the vertical dynamics.
2. Run a one-flap impulse experiment in Plant Lab.
3. Inspect the integrated step response.
4. Compare an analytic plant model with an identified model.
5. Tune on-off, PID, and polynomial controllers.
6. Apply the tuned controller to pipe-gap tracking in the actual game challenge.

The implementation roadmap for this progression is captured in [SDP.md](SDP.md).

## Current Features

- Manual Play mode with the original flap-and-avoid gameplay loop.
- Plant Lab with impulse response, integrated step response, model-validation, and Bode views.
- Controller Lab with on-off, PID, and generic polynomial controllers.
- Game Challenge mode that tracks the next pipe-gap centerline.
- Asset-backed visuals using the bundled original-style Flappy Bird backgrounds, bird sprites, pipes, digits, and overlays.
- CSV and JSON export for experiment logs.
- Optional PNG plot export when `matplotlib` is available.
- Deterministic simulation core and automated tests for analytics and controllers.

## Project Structure

- [FlappyBirdLight.py](FlappyBirdLight.py): app entrypoint.
- [flappy_control/core.py](flappy_control/core.py): plant, experiment, and gameplay simulation core.
- [flappy_control/controllers.py](flappy_control/controllers.py): controller families and transfer-function discretization.
- [flappy_control/analytics.py](flappy_control/analytics.py): response analysis, model identification, and Bode generation.
- [flappy_control/ui.py](flappy_control/ui.py): PyGame interface and teaching workflow.
- [tests](tests): regression coverage for the non-UI core.

## Installation

Install the runtime dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the application:

```bash
python3 FlappyBirdLight.py
```

Run the test suite:

```bash
python3 -m unittest discover -s tests -v
```

## Controls

### Main Menu
- `1`: Manual Play
- `2`: Plant Lab
- `3`: Controller Lab
- `4`: Game Challenge
- `Esc`: Return to menu

### Manual Play
- `Space`: flap
- `R`: restart

### Plant Lab
- `I`: run impulse experiment
- `S`: show integrated step response
- `M`: show measured vs modeled response
- `B`: show Bode magnitude
- `E`: export CSV/JSON
- `P`: export plot PNG

### Controller Lab and Game Challenge
- `1/2/3`: choose controller family
- `Tab`: select editable parameter
- `+/-`: tune the selected parameter
- `R`: rerun with current settings
- `E`: export CSV/JSON
- `P`: export plot PNG

## Development Notes

- The UI is built around a fixed simulation canvas that is scaled into a resizable application window.
- The plant is shared across gameplay and analysis to keep the educational models grounded in the same dynamics students interact with.
- Frequency-domain work stays transfer-function-centric; state-space methods are intentionally not the primary path.

## Roadmap

Near-term improvements that still fit the SDP:
- richer guided-lab prompts and unlock flow
- multi-run controller comparison views
- scenario presets for easier and harder pipe courses
- packaging and dependency setup for classroom deployment

## Attribution

The project includes Flappy Bird asset files under [flappy-bird-assets](flappy-bird-assets). See [flappy-bird-assets/README.md](flappy-bird-assets/README.md) and the asset license files for attribution details.
