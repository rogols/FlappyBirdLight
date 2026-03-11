# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows a simple unreleased-first workflow.

## [Unreleased]

## [0.2.0] - 2026-03-11

### Added
- Modular simulation architecture with a reusable bird plant, experiment runner, and transfer-function model representation.
- Plant Lab for impulse response, integrated step response, analytic vs identified model comparison, and Bode analysis.
- Controller Lab with tunable on-off, PID, and polynomial transfer-function controllers.
- Game Challenge mode that applies the selected controller to pipe-gap tracking.
- Asset-driven world rendering using the bundled Flappy Bird sprite pack for backgrounds, pipes, bird animation, score digits, and overlays.
- CSV and JSON export for experiment logs and optional PNG plot export.
- Root project documentation in `README.md`, `CHANGELOG.md`, and `SDP.md`.
- Automated tests for the simulation core, analytics, and controllers.

### Changed
- Replaced the original single-file prototype with a package-based architecture.
- Redesigned the UI to use a resizable layout, card-based information panels, bounded plots, and clearer instructional text.

### Known Limitations
- Runtime still depends on external installation of `pygame`, `numpy`, `matplotlib`, and `scipy`.
- The teaching flow is guided and informative, but not yet a full assessment or progress-tracking system.
