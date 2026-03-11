import unittest

from flappy_control.core import ControlCommand, ExperimentSpec, FlappySimulation


class CoreTest(unittest.TestCase):
    def test_flap_reduces_velocity(self) -> None:
        sim = FlappySimulation()
        sim.reset(pipes_enabled=False, initial_y=300.0)
        sample = sim.step(ControlCommand(flap=True, effort=1.0))
        self.assertLess(sample["vy"], 0.0)

    def test_manual_open_loop_descends_without_flap(self) -> None:
        sim = FlappySimulation()
        sim.reset(pipes_enabled=False, initial_y=300.0)
        first = sim.step(ControlCommand())
        second = sim.step(ControlCommand())
        self.assertGreater(float(second["y"]), float(first["y"]))

    def test_pipe_score_increments(self) -> None:
        sim = FlappySimulation()
        sim.reset(pipes_enabled=True, initial_y=300.0)
        sim.pipes[0].x = -sim.pipes[0].width - 1.0
        sim.step(ControlCommand())
        self.assertGreaterEqual(sim.score, 1)

    def test_run_experiment_is_deterministic(self) -> None:
        sim_a = FlappySimulation(seed=11)
        sim_b = FlappySimulation(seed=11)
        spec = ExperimentSpec(
            name="determinism",
            duration=1.0,
            initial_y=300.0,
            pipes_enabled=False,
            target_y=300.0,
            input_profile="none",
        )
        result_a = sim_a.run_experiment(spec, lambda _obs, _dt: ControlCommand())
        result_b = sim_b.run_experiment(spec, lambda _obs, _dt: ControlCommand())
        self.assertEqual(result_a.samples, result_b.samples)


if __name__ == "__main__":
    unittest.main()
