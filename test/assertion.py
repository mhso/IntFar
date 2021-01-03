COL_HEADER = '\033[95m'
COL_OKBLUE = '\033[94m'
COL_OKGREEN = '\033[92m'
COL_WARNING = '\033[93m'
COL_FAIL = '\033[91m'
COL_ENDC = '\033[0m'
COL_BOLD = '\033[1m'
COL_UNDERLINE = '\033[4m'

class Assertion:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.current_test = None

    def set_current_test(self, name):
        self.current_test = name

    def print_passed(self, name, desc):
        prefix = "" if self.current_test is None else f"{self.current_test} - "
        print(f"{COL_BOLD}{prefix}{COL_ENDC}{name} - {COL_OKGREEN}{desc}{COL_ENDC}")

    def print_failed(self, name, desc):
        prefix = "" if self.current_test is None else f"{self.current_test} - "
        print(f"{COL_BOLD}{prefix}{COL_ENDC}{name} - {COL_FAIL}{desc}{COL_ENDC}")

    def assert_true(self, value, name):
        if value:
            self.passed += 1
            self.print_passed(name, f"Passed. Value was {value}.")
        else:
            self.failed += 1
            self.print_failed(name, f"Failed! Value was {value}.")

    def assert_false(self, value, name):
        if not value:
            self.passed += 1
            self.print_passed(name, f"Passed. Value was {value}.")
        else:
            self.failed += 1
            self.print_failed(name, f"Failed! Value was {value}.")

    def assert_equals(self, value, expected, name):
        if value == expected:
            self.passed += 1
            self.print_passed(name, f"Passed. Value was {value}.")
        else:
            self.failed += 1
            self.print_failed(name, f"Failed! Expected: {expected}, actual: {value}.")

    def print_test_summary(self):
        self.current_test = None
        print("============================================================")
        print(f"{self.passed + self.failed} tests run.")
        self.print_passed("", f"{self.passed} passed.")
        self.print_failed("", f"{self.failed} failed.")
