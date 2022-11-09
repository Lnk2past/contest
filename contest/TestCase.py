import os
import pathlib
import shutil
from itertools import zip_longest
from subprocess import run, PIPE, TimeoutExpired

from loguru import logger
from PIL import Image, ImageChops

from contest.utilities import chdir
from contest.utilities.importer import import_from_source


class TestCase:
    def __init__(
        self,
        case_name,
        exe,
        return_code,
        argv,
        stdin,
        stdout,
        stderr,
        ofstreams,
        env,
        extra_tests,
        timeout,
        test_home,
        resources,
        setup
    ):
        """Initialize test case inputs

        Arguments:
            case_name (str): name of the test
            exe (str): executable to test
            return_code (int): return code of the execution
            argv (list): list of command line arguments
            stdin (list): list of inputs that are passed to stdin
            stdout (str): expected output to stdout
            stderr (str): expected output to stderr
            ofstreams (list): list of pairs of file names and content
            env (dict): dictionary of environment variables to set in the execution space
            extra_tests (list): list of additional modules to load for testing
            test_home (str): directory to run the test out of
            resources (list): list of resources to copy to the test directory
            setup (list): list of commands to run before executing the core test
        """
        logger.debug(f'Constructing test case {case_name}')
        self.case_name = case_name
        self.exe = exe
        self.return_code = return_code
        self.argv = argv
        self.stdin = self._setup_istream(stdin)
        self.stdout = self._setup_ostream(stdout)
        self.stderr = self._setup_ostream(stderr)
        self.ofstreams = [self._setup_ofstream(ofs) for ofs in ofstreams]
        self.env = env
        self.extra_tests = extra_tests
        self.timeout = timeout
        self.test_home = test_home
        self.setup = setup

        shutil.rmtree(self.test_home, ignore_errors=True)
        pathlib.Path(self.test_home).mkdir(parents=True, exist_ok=True)
        for resource in resources:
            if isinstance(resource, str):
                shutil.copytree(resource, pathlib.Path(self.test_home)/resource)
            elif isinstance(resource, dict):
                shutil.copytree(resource['src'], pathlib.Path(self.test_home)/resource['dst'])

        self.test_args = self._setup_test_process(self.exe, self.argv)
        for step in self.setup:
            step = self._setup_test_process(step)
            with chdir.ChangeDirectory(self.test_home):
                logger.debug(f'Running setup: {step}')
                run(step, stdout=PIPE, stderr=PIPE, cwd=pathlib.Path.cwd())

    def _setup_istream(self, stream):
        if isinstance(stream, list):
            return os.linesep.join(stream)
        elif isinstance(stream, str):
            return stream
        raise RuntimeError('input streams must be a string or a list!')

    def _setup_ostream(self, stream):
        spec = stream if isinstance(stream, dict) else {}
        if isinstance(stream, str):
            spec['text'] = stream.splitlines(keepends=True)
        elif isinstance(stream, list):
            spec['text'] = stream
        elif isinstance(stream, dict) and 'text' in spec:
            spec['text'] = spec['text'].splitlines(keepends=True)
        elif not isinstance(stream, dict):
            raise RuntimeError('output streams must be a dictionary, string, or a list!')
        if 'start' not in spec:
            spec['start'] = 0
        if 'count' not in spec:
            spec['count'] = -1
        return spec

    def _setup_ofstream(self, stream):
        if isinstance(stream, dict):
            if 'file' in stream:
                stream['file'] = os.path.join('..', '..', stream['file'])
            return self._setup_ostream(stream)
        raise RuntimeError('output file streams must be a dictionary!')

    def _setup_test_process(self, cmd, argv=[]):
        """Properly sets the relative paths for the executable and contructs the
        argument list for the executable.

        Returns:
            list of the executable and arguments to be passed to subprocess.run
        """
        splexe = cmd.split()
        splexe.extend(argv)
        for idx, sp in enumerate(splexe):
            sp = pathlib.Path(self.test_home, '..', '..', sp)
            if sp.exists():
                sp = sp.resolve()
                splexe[idx] = str(sp)
        return splexe

    def execute(self):
        """Execute the test

        Returns:
            Number of errors encountered
        """
        logger.critical('Starting test')
        logger.debug(f'Test Home: {self.test_home}')
        logger.debug(f'Running: {self.test_args}')
        with chdir.ChangeDirectory(self.test_home):
            errors = 0
            try:
                proc = run(self.test_args, input=self.stdin, stdout=PIPE, stderr=PIPE, cwd=pathlib.Path.cwd(),
                           timeout=self.timeout, universal_newlines=True, env=self.env)
            except TimeoutExpired:
                logger.critical('Your program took too long to run! Perhaps you have an infinite loop?')
                errors += 1

            if self.return_code is not None and int(self.return_code) != proc.returncode:
                logger.critical(f'FAILURE:\n         Expected return code {self.return_code}, received {proc.returncode}')
                errors += 1

            if 'file' in self.stdout:
                self.stdout['text'] = open(self.stdout['file'])
            if 'file' in self.stderr:
                self.stderr['text'] = open(self.stderr['file'])

            errors += self.check_streams('stdout', self.stdout, proc.stdout.splitlines(keepends=True))
            errors += self.check_streams('stderr', self.stderr, proc.stderr.splitlines(keepends=True))

            try:
                for ofstream in self.ofstreams:
                    file_type = ofstream.get('type', 'text')
                    logger.debug(f'Performing {file_type} comparison')
                    if file_type == 'text':
                        if 'file' in ofstream:
                            ofstream['text'] = open(ofstream['file'], 'r')
                        errs = self.check_streams(ofstream['test-file'], ofstream, open(ofstream['test-file'], 'r'))
                        if errs:
                            logger.critical(f'Errors found checking streams: {errs}')
                        errors += errs
                    elif file_type == 'binary':
                        if 'file' in ofstream:
                            ofstream['text'] = open(ofstream['file'], 'rb')
                        errs = self.check_streams(ofstream['test-file'], ofstream, open(ofstream['test-file'], 'rb'))
                        if errs:
                            logger.critical(f'Errors found checking binary streams: {errs}')
                        errors += errs
                    elif file_type == 'image':
                        f_image = Image.open(ofstream['file'])
                        t_image = Image.open(ofstream['test-file'])
                        diff = ImageChops.difference(f_image, t_image)
                        if diff.getbbox():
                            errors += 1
                            logger.critical('Errors found checking images')
            except FileNotFoundError:
                logger.critical(f'FAILURE:\n        Could not find output file {ofstream["test-file"]}')
                errors += 1
            for extra_test in self.extra_tests:
                logger.debug(f'Running extra test: {extra_test}')
                extra_test = import_from_source(extra_test)
                if not extra_test.test():
                    errors += 1
                    logger.critical('Failed!')

            if not errors:
                logger.critical('OK!')

        return int(errors > 0)

    @staticmethod
    def check_streams(stream, expected, received):
        """Compares two output streams, line by line

        Arguments:
            stream (str): name of stream being tested
            expected (dict): expected content of stream and details for comparing
            received (str): stream output from the test

        Returns:
            0 for no error, 1 for error
        """
        logger.debug(f'Comparing {stream} streams line by line')

        if 'empty' in expected:
            if expected['empty'] and received:
                logger.critical(f'FAILURE:\nExpected {stream} to be empty')
                return 1
            elif not expected['empty'] and not received:
                logger.critical(f'FAILURE:\nExpected {stream} to be nonempty')
                return 1
            return 0

        if 'ignore' in expected:
            logger.debug('Ignoring stream')
            return 0

        for line_number, (e, r) in enumerate(zip_longest(expected['text'], received)):
            if line_number < expected['start']:
                continue
            logger.debug(f'{stream} line {line_number}:\n"{e}"\n"{r}"\n')
            if e != r:
                if None in [e, r]:
                    logger.critical('ERROR: Expected and received streams do not have equal length!')
                    e = '' if e is None else e
                    r = '' if r is None else r
                i = 0
                while True:
                    s1 = e[i:i+5]
                    s2 = r[i:i+5]
                    if not s1 == s2:
                        for idx, (a, b) in enumerate(zip(s1, s2)):
                            if not a == b:
                                i = i + idx
                                break
                        else:
                            i = i + min(len(s1), len(s2))
                        break
                    i = i + 5
                e = f'        Expected "{e}"'
                r = f'        Received "{r}"'
                error_location = (' '*18) + (' '*i) + '^ ERROR'
                logger.critical(f'FAILURE:\n{e}\n{r}\n{error_location}')
                return 1
            if line_number - expected['start'] + 1 == expected['count']:
                logger.debug(f'Checked {expected["count"]} lines, breaking')
                break
        return 0
