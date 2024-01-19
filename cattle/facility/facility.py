"""
Writing a new facility.
Each facility needs the following operations:

should_run
run
dry_run
"""

class Facility:
    pass

class IdempotentFacility(Facility):
    def should_run(self):
        return True
