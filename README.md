# Flappy Bird Control Theory Lab

Flappy Bird Control Theory Lab is a PyGame app that turns Flappy Bird into a controlled-system playground. The bird uses one shared physical plant model in both human play and controller-driven play, so students can compare a person and a controller against the same dynamics, pipe timing, and scoring rules.

## Purpose

The project is built for control-theory teaching around a concrete process:
- the bird is the plant
- a flap is an impulsive input
- gravity and mass are modeled in SI units
- the pipe course is the disturbance and tracking environment

The current shipped app intentionally exposes two runtime views only:
- `Manual Play`: the user operates the bird.
- `Automatic Play`: the selected controller operates the bird after the user tunes parameters and starts the run.

Both modes use the same game mechanics and both score by counting passed pipes. At game over, the app shows separate high-score tables for human runs and controller runs. Controller entries include the tuned parameter summary in the recorded name.

## Current Scope

### In the app
- Manual gameplay with original-style Flappy Bird visuals from the bundled asset pack.
- Automatic gameplay with live controller tuning for on-off, PID, and polynomial controllers.
- Shared score handling across both modes.
- Persistent high-score storage in `high_scores.json`.
- Separate player and controller leaderboards.

### In the codebase
- A reusable physical simulation core in SI units.
- Controller implementations behind a common interface.
- Analytics and experiment utilities that support the broader teaching roadmap.
- Automated tests for simulation and controller behavior.

## Controls

### Global
- `M`: switch to manual play
- `A`: switch to automatic play

### Manual Play
- `Space`: start the round and flap
- `R`: reset the current round

### Automatic Play
- `1/2/3`: choose controller family
- `Tab`: cycle the editable controller parameter
- `+/-`: tune the selected parameter
- `E`: enter an exact numeric value for the selected parameter
- `Enter`: start the automatic run with the current settings
- `R`: reset the current round and controller state

## Physics Model

The vertical motion is modeled as:

```text
y_dot = v
v_dot = g - c v
v(t+) = v(t-) - J / m    at each flap event
```

Where:
- `g = 9.81 m/s^2`
- `m` is bird mass in kilograms
- `J` is the flap impulse in `N*s`
- `c` is the linear drag term

This keeps the plant definition independent from whichever controller happens to be driving it.

## Project Structure

- [FlappyBirdLight.py](/mnt/c/Development/FlappyBirdLight/FlappyBirdLight.py): app entrypoint.
- [flappy_control/core.py](/mnt/c/Development/FlappyBirdLight/flappy_control/core.py): physical plant and gameplay simulation.
- [flappy_control/controllers.py](/mnt/c/Development/FlappyBirdLight/flappy_control/controllers.py): on-off, PID, and polynomial controllers.
- [flappy_control/analytics.py](/mnt/c/Development/FlappyBirdLight/flappy_control/analytics.py): analysis helpers retained from the broader teaching roadmap.
- [flappy_control/ui.py](/mnt/c/Development/FlappyBirdLight/flappy_control/ui.py): two-view PyGame interface, live tuning, and high-score presentation.
- [tests](/mnt/c/Development/FlappyBirdLight/tests): automated regression coverage.
- [SDP.md](/mnt/c/Development/FlappyBirdLight/SDP.md): the broader original software development plan for the teaching platform.

## Installation

```bash
python3 -m pip install -r requirements.txt
python3 FlappyBirdLight.py
```

Run tests with:

```bash
python3 -m unittest discover -s tests -v
```

## Repository Notes

- `SDP.md` captures the larger roadmap for a richer control-theory learning platform. The current production UI has been narrowed to the two gameplay views above.
- High scores are persisted locally in `high_scores.json`.
- The bundled art lives under [flappy-bird-assets](/mnt/c/Development/FlappyBirdLight/flappy-bird-assets) with its own attribution files.
