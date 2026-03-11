import unittest

from flappy_control.controllers import OnOffController, PIDController, TransferFunctionController, continuous_tf_to_discrete
from flappy_control.core import BirdState, Observation


def make_observation(y: float, target: float = 300.0) -> Observation:
    return Observation(
        state=BirdState(time=0.0, y=y, vy=0.0, ay=0.0, alive=True),
        target_y=target,
        next_pipe_gap_y=None,
        next_pipe_distance=None,
        score=0,
        pipes_enabled=False,
    )


class ControllerTest(unittest.TestCase):
    def test_on_off_flaps_when_below_target_band(self) -> None:
        controller = OnOffController(deadband=5.0, hysteresis=2.0, min_interval=0.0)
        command = controller.update(make_observation(320.0, 300.0), 1 / 30)
        self.assertTrue(command.flap)

    def test_pid_output_is_clamped(self) -> None:
        controller = PIDController(kp=1.0, ki=0.0, kd=0.0, output_max=0.5)
        command = controller.update(make_observation(600.0, 300.0), 1 / 30)
        self.assertLessEqual(command.effort, 0.5)

    def test_transfer_controller_generates_discrete_coefficients(self) -> None:
        bz, az = continuous_tf_to_discrete([0.2, 0.1], [1.0, 1.2, 0.4], 1 / 30)
        self.assertEqual(len(bz), len(az))
        self.assertNotEqual(sum(abs(value) for value in bz), 0.0)

    def test_transfer_controller_runs(self) -> None:
        controller = TransferFunctionController()
        command = controller.update(make_observation(340.0, 300.0), 1 / 30)
        self.assertGreaterEqual(command.effort, 0.0)
        self.assertLessEqual(command.effort, 1.0)


if __name__ == "__main__":
    unittest.main()
