# SDP.md: Flappy Bird Control Theory Learning Platform

## Summary
Transform the current single-file PyGame prototype into a classroom-ready learning app where students can:
- Play manually and observe the bird as a control object.
- Run repeatable impulse and step experiments on the bird's vertical dynamics.
- Derive and validate a transfer-function model of the bird from coded dynamics plus measured data.
- Compare on-off, PID, and higher-order transfer-function controllers while flying through simplified Flappy Bird scenarios.
- Inspect both time-domain and frequency-domain behavior, including impulse response, step response, and Bode plots.

The first complete release should be a single desktop app with guided lab flow, built-in tunable controllers, in-app plots, and optional export of experiment data/images.

## Key Changes

### 1. Restructure into a simulation-first architecture
Refactor the current script into separable subsystems so gameplay, experiments, and teaching tools all use the same plant:
- `plant/simulation` layer for bird vertical dynamics, timing, and disturbances.
- `gameplay` layer for pipes, scoring, collision, and manual/autopilot game modes.
- `controllers` layer for controller implementations behind one common interface.
- `analytics` layer for logging, response computation, fitting, metrics, and frequency-response generation.
- `ui/labs` layer for menus, guided exercises, plots, and parameter editing.

Define these core interfaces early and keep them stable:
- `PlantParams`: `gravity`, `flap_impulse`, `dt`, optional `drag`, optional saturation limits.
- `BirdState`: `time`, `y`, `vy`, optional `ay`, `alive`.
- `Observation`: bird state plus local environment features such as next-pipe gap center and distance.
- `ControlCommand`: binary flap request or normalized control effort that is converted into a flap event according to selected actuation mode.
- `Controller.update(observation, dt) -> ControlCommand`.
- `ExperimentSpec`: experiment type, duration, initial conditions, input profile, disturbance profile, sample rate.
- `ExperimentResult`: time series, response arrays, event markers, fitted model, and summary metrics.
- `TransferFunctionModel`: numerator coefficients, denominator coefficients, delay assumption, fit quality, and source method (`analytic` or `identified`).

Use light dependencies: `numpy`, `scipy`, and `matplotlib` in addition to `pygame`.

### 2. Make the bird an explicit control object
Replace ad hoc bird motion handling with a documented plant model used everywhere:
- Preserve the current discrete update law as the baseline "truth model".
- Expose the vertical channel as the main controlled system: flap input -> vertical acceleration/velocity/position.
- Add a plant-configuration screen showing the exact simulation parameters students will model.
- Log input/output data at fixed timestep so experiments are reproducible.

Modeling flow for students:
- Start from the coded update equations and derive a continuous or sampled-data approximation for the bird's vertical motion.
- Run an impulse experiment: one flap from a known initial condition, with pipes disabled.
- Compute and display the measured impulse response of position and velocity.
- Compute the step response as the cumulative integral of the impulse response and also allow direct step-like excitation via repeated flap scheduling.
- Fit low-order transfer-function models and compare measured vs predicted responses on the same plot.
- Show model mismatch metrics so students can judge whether a first-order or second-order approximation is adequate.

### 3. Build guided learning modes
The app should have four student-facing modes:
- `Manual Play`: current Flappy Bird gameplay, but with live telemetry overlay.
- `Plant Lab`: impulse/step experiments, model derivation prompts, and response plots.
- `Controller Lab`: select controller type, tune parameters, and observe closed-loop response without pipes.
- `Game Challenge`: run the chosen controller in the actual obstacle course and compare performance with manual play.

Guided-lab structure:
- Each mode should have a short instruction panel, current task, and success criterion.
- Labs should be stage-based, not open-ended first.
- Students can unlock "free exploration" after completing the guided path in a given module.

Minimum lab sequence:
1. Observe open-loop bird dynamics.
2. Measure impulse response from one flap.
3. Derive step response from the impulse response.
4. Propose a transfer function and validate it.
5. Tune on-off control to hold altitude.
6. Tune PID to track altitude or pipe-gap centerline.
7. Apply a higher-order transfer-function controller or compensator.
8. Compare closed-loop stability, overshoot, settling time, control effort, and game score.

### 4. Add controller families aligned with the course
Implement built-in controller templates with a shared parameter editor and identical metrics:
- On-off / bang-bang control with hysteresis and deadband.
- PID with configurable `Kp`, `Ki`, `Kd`, derivative filtering, anti-windup, and output saturation.
- Higher-order transfer-function controller in polynomial form, implemented as a discrete difference equation from user-defined numerator/denominator coefficients.
- Optional lead/lag presets packaged as special cases of the higher-order controller.

Use two target types:
- Fixed altitude hold in lab mode.
- Moving target based on the next pipe gap center in gameplay mode.

Standard closed-loop metrics to show for every run:
- Rise time.
- Overshoot.
- Settling time.
- Steady-state error.
- Number of flap events / control effort.
- Crash cause and survival time in game mode.

### 5. Add time-domain and frequency-domain analytics
Plotting must be first-class in the app:
- Time-series plots for `y(t)`, `vy(t)`, target, and control input.
- Impulse response and integrated step response views.
- Model-vs-measurement overlay plots.
- Controller comparison plots with multiple runs.

Frequency-domain support for first release:
- Generate Bode magnitude/phase plots from the fitted or analytic transfer function.
- Allow students to compare the plant Bode plot with the closed-loop result for a selected controller.
- Highlight gain crossover, phase margin, and qualitative stability interpretation, but keep the UI at an introductory level.
- Do not make state-space or pole placement the main path; transfer functions remain the central representation.

Export support:
- CSV export for experiment logs.
- PNG/SVG export for plots.
- Optional JSON export/import for controller settings and plant presets.
