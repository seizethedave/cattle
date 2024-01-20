"""
A flaky config that requires retries to eventually finish.
"""

from cattle.facility.facility import Facility

class FlakyAction(Facility):
    """
    FlakyAction requires multiple attempts to successfully complete.
    """
    def __init__(self, attempts=3):
        self.total_attempts = attempts
        self.remaining_attempts = attempts

    def should_run(self):
        return True

    def run(self):
        if self.remaining_attempts > 0:
            self.remaining_attempts -= 1

        if self.remaining_attempts > 0:
            raise Exception("not working yet")

    def dry_run(self):
        return [f"flaky action (attempts={self.total_attempts})"]

steps = [
    FlakyAction(1),
    FlakyAction(2),
    FlakyAction(3),
]
