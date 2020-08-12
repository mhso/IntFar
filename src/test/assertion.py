COL_HEADER = '\033[95m'
COL_OKBLUE = '\033[94m'
COL_OKGREEN = '\033[92m'
COL_WARNING = '\033[93m'
COL_FAIL = '\033[91m'
COL_ENDC = '\033[0m'
COL_BOLD = '\033[1m'
COL_UNDERLINE = '\033[4m'

def print_passed(text):
    print(f"{COL_OKGREEN}{text}{COL_ENDC}")

def print_failed(text):
    print(f"{COL_FAIL}{text}{COL_ENDC}")

class Assertion:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def assert_true(self, value, name):
        if value:
            self.passed += 1
            print_passed(f"{name} passed. Value was {value}.")
        else:
            self.failed += 1
            print_failed(f"{name} failed! Value was {value}.")

    def assert_equals(self, value, expected, name):
        if value == expected:
            self.passed += 1
            print_passed(f"{name} passed. {expected} = {value}.")
        else:
            self.failed += 1
            print_failed(f"{name} failed! Expected: {expected}, actual: {value}.")

    def print_test_summary(self):
        print(f"{self.passed + self.failed} tests run.")
        print_passed(f"{self.passed} tests passed.")
        print_failed(f"{self.failed} tests failed.")
