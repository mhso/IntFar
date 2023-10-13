import argparse
from glob import glob
import importlib

if __name__ == "__main__":
    tests = [x.replace("\\", "/").split("/")[-1].split(".")[0].split("_")[1] for x in glob("test/test_*.py")]

    parser = argparse.ArgumentParser(description="Test all the things.")

    parser.add_argument("tests", type=str, choices=tests, nargs="+")
    parser.add_argument("-t", "--test-names", type=str, nargs="+", help="Specific tests to run.")

    args = parser.parse_args()

    for module_tests in args.tests:
        module = importlib.import_module(f"test.test_{module_tests}")
        test_runner = module.__getattribute__("TestWrapper")()
        tests_to_run = args.test_names
        if tests_to_run == []:
            tests_to_run = None

        test_runner.run_tests(tests_to_run)
        test_runner.after_all()
