import unittest

from flappy_control.core import ControlCommand, ExperimentSpec, FlappySimulation


class CoreTest(unittest.TestCase):
    def test_flap_reduces_velocity(self) -> None:
        sim = FlappySimulation()
        sim.reset(pipes_enabled=False, initial_y=sim.center_y)
        sample = sim.step(ControlCommand(flap=True, effort=1.0))
        self.assertLess(sample["vy"], 0.0)

    def test_higher_flap_effort_increases_climb_rate(self) -> None:
        sim = FlappySimulation()
        sim.reset(pipes_enabled=False, initial_y=sim.center_y)
        baseline = sim.step(ControlCommand(flap=True, effort=1.0))

        sim.reset(pipes_enabled=False, initial_y=sim.center_y)
        boosted = sim.step(ControlCommand(flap=True, effort=1.75))

        self.assertLess(float(boosted["vy"]), float(baseline["vy"]))

    def test_default_plant_has_meaningful_climb_after_single_flap(self) -> None:
        sim = FlappySimulation()
        initial_y = sim.center_y
        sim.reset(pipes_enabled=False, initial_y=initial_y)
        sim.step(ControlCommand(flap=True, effort=1.0))
        for _ in range(5):
            sim.step(ControlCommand())
        self.assertLess(sim.state.y, initial_y - sim.pixels_to_world_y(35.0))

    def test_manual_open_loop_descends_without_flap(self) -> None:
        sim = FlappySimulation()
        sim.reset(pipes_enabled=False, initial_y=sim.center_y)
        first = sim.step(ControlCommand())
        second = sim.step(ControlCommand())
        self.assertGreater(float(second["y"]), float(first["y"]))

    def test_pipe_score_increments(self) -> None:
        sim = FlappySimulation()
        sim.reset(pipes_enabled=True, initial_y=sim.center_y)
        sim.pipes[0].x = -sim.pipes[0].width - sim.pixels_to_world_x(1.0)
        sim.step(ControlCommand())
        self.assertGreaterEqual(sim.score, 1)

    def test_run_experiment_is_deterministic(self) -> None:
        sim_a = FlappySimulation(seed=11)
        sim_b = FlappySimulation(seed=11)
        spec = ExperimentSpec(
            name="determinism",
            duration=1.0,
            initial_y=sim_a.center_y,
            pipes_enabled=False,
            target_y=sim_a.center_y,
            input_profile="none",
        )
        result_a = sim_a.run_experiment(spec, lambda _obs, _dt: ControlCommand())
        result_b = sim_b.run_experiment(spec, lambda _obs, _dt: ControlCommand())
        self.assertEqual(result_a.samples, result_b.samples)


if __name__ == "__main__":
    unittest.main()
