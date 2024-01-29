import subprocess
import unittest
import os

from cattle.cattle_cli import main_args_inner

class TestCLI(unittest.TestCase):
    def test_run_local_suite(self):
        """
        Run the full cycle of exec/status/log/clean against the local fs.
        Definitely an integration test.
        """
        run_root = "/tmp/cattle-test-run"

        result = main_args_inner(["exec", os.path.abspath("../example/flaky"), "--local", "--run-root", run_root])
        if result.exit_code != 0:
            self.fail(f"cattle exec failed.")

        exec_id = result.result_vars["execution_id"]

        statusproc = main_args_inner(["status", exec_id, "--local", "--run-root", run_root])
        self.assertEqual(statusproc.exit_code, 0)

        logproc = main_args_inner(["log", exec_id, "--local", "--run-root", run_root])
        self.assertEqual(logproc.exit_code, 0)

        cleanproc = main_args_inner(["clean", exec_id, "--local", "--run-root", run_root])
        self.assertEqual(cleanproc.exit_code, 0)

if __name__ == "__main__":
    unittest.main()
