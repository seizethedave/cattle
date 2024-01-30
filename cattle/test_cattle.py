import os
import unittest

from cattle.cattle_cli import main_args_inner

class TestCLI(unittest.TestCase):
    def test_run_local_suite(self):
        """
        Run the full cycle of exec/status/log/clean against the local fs.
        Definitely an integration test.
        """
        run_root = "/tmp/cattle-test-run"
        test_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), "example/flaky")

        proc = main_args_inner(["exec", test_config, "--local", "--run-root", run_root])
        self.assertEqual(proc.exit_code, 0)
        exec_id = proc.result_vars["execution_id"]

        proc = main_args_inner(["status", exec_id, "--local", "--run-root", run_root])
        self.assertEqual(proc.exit_code, 0)

        proc = main_args_inner(["log", exec_id, "--local", "--run-root", run_root])
        self.assertEqual(proc.exit_code, 0)

        proc = main_args_inner(["clean", exec_id, "--local", "--run-root", run_root])
        self.assertEqual(proc.exit_code, 0)

if __name__ == "__main__":
    unittest.main()
