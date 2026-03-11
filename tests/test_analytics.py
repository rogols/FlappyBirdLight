import unittest

from flappy_control.analytics import analytic_transfer_function, bode_points, integrate_response
from flappy_control.core import ExperimentSpec, FlappySimulation


class AnalyticsTest(unittest.TestCase):
    def test_integrate_response(self) -> None:
        self.assertEqual(integrate_response([1.0, 1.0, 1.0], 0.5), [0.5, 1.0, 1.5])

    def test_bode_points_returns_monotonic_frequency_grid(self) -> None:
        model = analytic_transfer_function(FlappySimulation().plant)
        points = bode_points(model, count=12)
        self.assertEqual(len(points), 12)
        self.assertTrue(all(points[index][0] < points[index + 1][0] for index in range(len(points) - 1)))

    def test_experiment_produces_model_and_metrics(self) -> None:
        sim = FlappySimulation()
        spec = ExperimentSpec(
            name="unit-impulse",
            duration=2.0,
            initial_y=300.0,
            pipes_enabled=False,
            target_y=300.0,
            input_profile="single_flap",
        )
        fired = {"value": False}

        def command_fn(_observation, _dt):
            from flappy_control.core import ControlCommand

            if not fired["value"]:
                fired["value"] = True
                return ControlCommand(flap=True, effort=1.0)
            return ControlCommand()

        result = sim.run_experiment(spec, command_fn)
        self.assertGreater(len(result.samples), 0)
        self.assertIn("settling_time", result.metrics)
        self.assertEqual(len(result.impulse_response), len(result.samples))
        self.assertGreaterEqual(result.model.fit_quality, 0.0)


if __name__ == "__main__":
    unittest.main()
