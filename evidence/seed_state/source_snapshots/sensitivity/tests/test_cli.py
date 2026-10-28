import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monogrowlab.cli import build_parser, forwarded_arguments, main, resolve_project_root


class CliTests(unittest.TestCase):
    def test_analyze_forwards_repeated_primary_variants(self):
        args = build_parser().parse_args(
            [
                "analyze",
                "--input",
                "run.jsonl",
                "--output-dir",
                "analysis",
                "--primary-variant",
                "a-strict",
                "--primary-variant",
                "b-strict",
            ]
        )
        forwarded = forwarded_arguments(args)
        self.assertEqual(forwarded.count("--primary-variant"), 2)
        self.assertIn("a-strict", forwarded)
        self.assertIn("b-strict", forwarded)

    def test_explicit_invalid_project_root_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {}, clear=True), patch(
                "pathlib.Path.cwd", return_value=Path(directory)
            ):
                with self.assertRaisesRegex(RuntimeError, "not a MonoGrowLab"):
                    resolve_project_root(Path(directory))

    @patch("monogrowlab.cli.subprocess.run")
    def test_run_uses_python_without_shell(self, mocked_run):
        mocked_run.return_value.returncode = 0
        project_root = Path(__file__).resolve().parents[1]
        result = main(
            [
                "--project-root",
                str(project_root),
                "run",
                "--config",
                "configs/smoke.json",
            ]
        )
        self.assertEqual(result, 0)
        command = mocked_run.call_args.args[0]
        self.assertEqual(command[0], __import__("sys").executable)
        self.assertTrue(command[1].endswith("run_bsds_robustness_v2.py"))
        self.assertNotIn("shell", mocked_run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
