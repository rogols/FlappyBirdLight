import unittest

from flappy_control.controllers import OnOffController, PIDController, TransferFunctionController, continuous_tf_to_discrete, controller_factory
from flappy_control.core import BirdState, FlappySimulation, Observation


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
        controller = PIDController(k=1.0, ti=0.0, td=0.0, output_max=0.5)
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

    def test_default_controllers_make_progress_in_game(self) -> None:
        for controller in controller_factory():
            sim = FlappySimulation(seed=7)
            sim.reset(pipes_enabled=True, target_y=sim.center_y)
            controller.reset()
            for _ in range(900):
                observation = sim.observe()
                observation.target_y = observation.next_pipe_gap_y if observation.next_pipe_gap_y is not None else sim.center_y
                command = controller.update(observation, sim.plant.dt)
                sim.step(command)
                if not sim.state.alive:
                    break
            self.assertGreaterEqual(sim.score, 1, msg=f"{controller.name} did not pass any pipes")


if __name__ == "__main__":
    unittest.main()
