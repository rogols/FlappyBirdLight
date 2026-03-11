import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from flappy_control.controllers import OnOffController, PIDController
from flappy_control.ui import AUTOMATIC, MANUAL, ControlTheoryApp, HIGH_SCORE_LIMIT, ScoreEntry


class UiStateTest(unittest.TestCase):
    def _make_app(self, path: Path) -> ControlTheoryApp:
        app = ControlTheoryApp.__new__(ControlTheoryApp)
        app.high_score_path = path
        app.high_scores = {"player": [], "controller": []}
        app.controllers = [OnOffController(), PIDController()]
        app.selected_controller = 1
        app.selected_parameter = 0
        app.parameter_input = None
        app.status = ""
        app.sim = SimpleNamespace(score=0, config=SimpleNamespace(pipe_speed_gain=0.01))
        return app

    def test_record_score_separates_player_and_controller(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = self._make_app(Path(temp_dir) / "scores.json")

            app.mode = MANUAL
            app.sim.score = 3
            app._record_score()

            app.mode = AUTOMATIC
            app.sim.score = 5
            app._record_score()

            self.assertEqual([(entry.name, entry.score) for entry in app.high_scores["player"]], [("Spelare", 3)])
            self.assertEqual(len(app.high_scores["controller"]), 1)
            self.assertEqual(app.high_scores["controller"][0].score, 5)
            self.assertIn("PID K=", app.high_scores["controller"][0].name)

    def test_load_high_scores_enforces_limit_and_sorting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scores.json"
            payload = {
                "player": [{"name": f"P{index}", "score": index} for index in range(HIGH_SCORE_LIMIT + 2)],
                "controller": [{"name": "PID", "score": 4}, {"name": "On-Off", "score": 7}],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

            app = self._make_app(path)
            loaded = app._load_high_scores()

            self.assertEqual(len(loaded["player"]), HIGH_SCORE_LIMIT)
            self.assertEqual(loaded["player"][0].score, HIGH_SCORE_LIMIT + 1)
            self.assertEqual([entry.score for entry in loaded["controller"]], [7, 4])

    def test_controller_scores_are_trimmed_to_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = self._make_app(Path(temp_dir) / "scores.json")
            app.mode = AUTOMATIC
            app.high_scores["controller"] = [ScoreEntry(name=f"C{index}", score=index) for index in range(HIGH_SCORE_LIMIT)]

            app.sim.score = HIGH_SCORE_LIMIT + 4
            app._record_score()

            self.assertEqual(len(app.high_scores["controller"]), HIGH_SCORE_LIMIT)
            self.assertEqual(app.high_scores["controller"][0].score, HIGH_SCORE_LIMIT + 4)

    def test_commit_parameter_input_sets_exact_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = self._make_app(Path(temp_dir) / "scores.json")
            app.mode = AUTOMATIC
            app.phase = "ready"
            app.selected_parameter = 1
            app.parameter_input = "12.5"
            app._prepare_round_state = lambda: None

            committed = app._commit_parameter_input()

            self.assertTrue(committed)
            self.assertAlmostEqual(app.controller.k, 12.5)
            self.assertIsNone(app.parameter_input)
            self.assertIn("Satte PID K till 12.500", app.status)


if __name__ == "__main__":
    unittest.main()
