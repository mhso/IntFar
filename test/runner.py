from abc import abstractmethod
import inspect

COL_HEADER = '\033[95m'
COL_OKBLUE = '\033[94m'
COL_OKGREEN = '\033[92m'
COL_WARNING = '\033[93m'
COL_FAIL = '\033[91m'
COL_ENDC = '\033[0m'
COL_BOLD = '\033[1m'
COL_UNDERLINE = '\033[4m'

def makeRegisteringDecorator(decorator):
    def new_decorator(func):
        # Call to new_decorator(method)
        # Exactly like old decorator, but output keeps track of what decorated it
        R = decorator(func) # apply foreignDecorator, like call to foreignDecorator(method) would have done
        R.decorator = new_decorator # keep track of decorator
        #R.original = func         # might as well keep track of everything!
        return R

    new_decorator.__name__ = decorator.__name__
    new_decorator.__doc__ = decorator.__doc__

    return new_decorator

def test(func):
    return func

test = makeRegisteringDecorator(test)

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.current_test = None
        self.tests = []
        self.test_args = None

    def before_all(self, *test_args):
        self.test_args = test_args

    @abstractmethod
    def before_test(self):
        pass

    def print_passed(self, name, desc):
        prefix = "" if self.current_test is None else f"{self.current_test} - "
        print(f"{COL_BOLD}{prefix}{COL_ENDC}{name} - {COL_OKGREEN}{desc}{COL_ENDC}", flush=True)

    def print_failed(self, name, desc):
        prefix = "" if self.current_test is None else f"{self.current_test} - "
        print(f"{COL_BOLD}{prefix}{COL_ENDC}{name} - {COL_FAIL}{desc}{COL_ENDC}", flush=True)

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

    def assert_exception(self, expr, exc_class, name):
        try:
            expr()
            self.failed += 1
            self.print_failed(name, "Failed! No exception was raised.")
        except Exception as exc:
            if isinstance(exc, type(exc_class)):
                self.passed += 1
                self.print_passed(name, f"Passed. Exception {exc_class} was raised.")
            else:
                self.failed += 1
                self.print_failed(name, f"Failed! Expected exception: {exc_class}, actual: {exc}.")

    def print_test_summary(self):
        self.current_test = None
        print("============================================================")
        print(f"{self.passed + self.failed} tests run.")
        self.print_passed("", f"{self.passed} passed.")
        self.print_failed("", f"{self.failed} failed.")

    def get_test_funcs(self, decorator_name):
        source_lines = inspect.getsourcelines(self.__class__)[0]
        for i, line in enumerate(source_lines):
            line = line.strip()
            if line.split('(')[0].strip() == '@'+decorator_name: # leaving a bit out
                next_line = source_lines[i+1]
                name = next_line.split('def')[1].split('(')[0].strip()
                func = self.__getattribute__(name)
                yield func

    def run_tests(self, tests_to_run=None):
        for test_func in self.get_test_funcs("test"):
            test_name = test_func.__name__
            if tests_to_run is None or test_name in tests_to_run:
                self.current_test = test_name
                self.before_test()
                test_func(*self.test_args)
        self.print_test_summary()
