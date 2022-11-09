import argparse
import os
import re
import sys
import yaml
from loguru import logger
from yaml import FullLoader as DefaultLoader

from contest import __version__
from contest.TestCase import TestCase
from contest.utilities import configure_yaml  # noqa: F401


sys.dont_write_bytecode = True
logger.remove()


def filter_tests(case_name, includes, excludes):
    """Check if the input case is valid

    Arguments:
        case_name (str): name of case
        includes (list): list of regex patterns to check against
        excludes (list): list of regex patterns to check against

    Returns:
        True is valid, False otherwise
    """
    for re_filter in excludes:
        if re.search(re_filter, case_name):
            logger.debug(f'Excluding {case_name}, matches pattern {re_filter}')
            return False

    if not includes:
        return True

    for re_filter in includes:
        if re.search(re_filter, case_name):
            logger.debug(f'Including {case_name}, matches pattern {re_filter}')
            return True
    return False


def test():
    """Run the specified test configuration"""
    parser = argparse.ArgumentParser(__file__)
    parser.add_argument('configuration', help='path to a YAML test configuration file')
    parser.add_argument('--fail', action='store_true', default=False, help='end execution on first failure')
    parser.add_argument('--filters', default=[], nargs='+', help='regex pattern for tests to match')
    parser.add_argument('--exclude-filters', default=[], nargs='+', help='regex pattern for tests to match')
    parser.add_argument('--verbose', action='store_true', default=False, help='verbose output')
    parser.add_argument('--version', action='version', version=f'contest.py v{__version__.__version__}')
    inputs = parser.parse_args()
    if inputs.verbose:
        logger.add(sys.stdout, format='{extra[test_case]}: {message}', level='DEBUG')
    else:
        logger.add(sys.stdout, format='{extra[test_case]}: {message}', level='CRITICAL')

    base_logger = logger.bind(test_case='contest')

    base_logger.critical(f'Loading {inputs.configuration}')
    test_matrix = yaml.load(open(inputs.configuration, 'r'), Loader=DefaultLoader)
    base_logger.debug(f'{inputs.configuration} Loaded')
    executable = test_matrix.get('executable', '')
    base_logger.debug(f'Root executable: {executable}')

    number_of_tests = len(test_matrix['test-cases'])
    base_logger.critical(f'Found {number_of_tests} tests')
    test_cases = [case for case in test_matrix['test-cases'] if filter_tests(case['name'], inputs.filters, inputs.exclude_filters)]
    number_of_tests_to_run = len(test_cases)
    base_logger.critical(f'Running {number_of_tests_to_run} tests')

    tests = []
    for test_case in test_cases:
        with logger.contextualize(test_case=test_case['name']):
            tests.append(
                TestCase(
                    test_case['name'],
                    test_case.get('executable', executable),
                    test_case.get('return-code', None),
                    test_case.get('argv', []),
                    test_case.get('stdin', ''),
                    test_case.get('stdout', ''),
                    test_case.get('stderr', ''),
                    test_case.get('ofstreams', []),
                    test_case.get('env', {}) if test_case.get('scrub-env', False) else {**os.environ, **test_case.get('env', {})},
                    test_case.get('extra-tests', []),
                    test_case.get('timeout', None),
                    os.path.join(os.path.dirname(inputs.configuration), 'test_output', test_case['name']),
                    test_case.get('resources', []),
                    test_case.get('setup', []),
                )
            )

    errors = 0
    tests_run = 0
    for test in tests:
        with logger.contextualize(test_case=test.case_name):
            errors += test.execute()
            tests_run += 1
            if inputs.fail and errors:
                break
    base_logger.critical(f'{tests_run-errors}/{tests_run} tests passed!')
    return errors


if __name__ == '__main__':
    sys.exit(test())
