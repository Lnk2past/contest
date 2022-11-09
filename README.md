# contest

[![Build Status](https://github.com/Lnk2past/contest/workflows/Build/badge.svg)](https://github.com/Lnk2past/contest/actions)
[![PyPI version shields.io](https://img.shields.io/pypi/v/contest.svg)](https://pypi.python.org/pypi/contest/)
![Python](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8%20%7C%203.9-red)
![Platforms](https://img.shields.io/badge/platform-windows%20%7C%20mac%20%7C%20linux-yellow)

A `CON`sole application `TEST`er

## Introduction

`contest` is a testing application that exercises a program with configured input and then checks the output with some expected content. Simply: `contest` validates executable output given specific inputs.

### Motivation

I wrote this for a class that I teach to help with grading. Given the configuration driven nature of it (how else should a testing framework/tool work?) `contest` lets me define multiple test cases for particular programs (assignments) so that not only is grading easier for me, but I can integrate assignments into a grading pipeline so that I can do as little work as possible and my students can get immediate feedback on submissions. Assignments here are usually single-file programs that are not necessarily unit-testable without adding in boilerplate and nonstandard language features. Letting students build normal programs and then verify their behavior is the goal.

## Installation

```shell
pip install contest
```

You may install from this repo, clone and simply:

```shell
python setup.py install
```

## How It Works

### Overview

YAML is the preferred choice of input for `contest` for a few reasons, but most notably for its easy to follow syntax and allowance of multiline strings (sorry JSON). `contest` consumes an input file that specifies at least one executable and then whatever additional information is provided. Check out the test skeleton below to see what can be specified; the main ones though are the input and output streams `stdout`, `stderr`, and `stderr` as well and CLI inputs `argv`. You can specify newly generated files that you expect to be created and even go further and specify custom tests (as `Python` files) that cover the things simple I/O comparisons do not. Lastly, you may also specify environment variables to be set during the execution; and you may also scrub the environment before adding custom keys. Note that scrubbing the environment may prevent your executable from running altogether! For now you are better off allowing your current environment to persist and simply overwrite what needs to be set. Environment variables specified within a test-case take precedence over what is in your current environment.

#### Test Skeleton

```yaml
executable:                 # !!str, name of the executable to use for all tests
test-cases:                 # !!seq, list of all test cases
    - name:                 # !!str, name of the test
      scrub-env:            # !!bool, flag to remove the current environment
      env:                  # !!map, environment variables to set
      resources:            # !!seq, list of resources to copy to the test directory, need to provide a src and dst
      executable:           # !!str, name of the executable to use for this test case only
      argv:                 # !!seq, list of arguments to pass to the executable
      stdin:                # !!str || !!seq inputs to standard input stream
        # * see below
      return-code:           # !!int, expected return code
      stdout:               # !!str || !!seq || !!map, expected output in standard output stream
        # ** see below
      stderr:               # !!str || !!seq || !!map, expected output in standard error stream
        # ** see below
      ofstreams:            # !!seq, list of files to compare
            # *** see below
      extra-tests:          # !!seq, list of additional modules to load for additional tests
```

\* The stdin field can either be a block of text (one entry to stdin per line) or can be provided as a list.

\*\* These fields can either be text blocks, lists, or dictionaries. As a text block or list, it should be the expected output as is. As dictionaries the following fields are allowed:

```yaml
text:         # !!str, expected output as a string
file:         # !!str, file containing the text to compare against. useful for keeping the size of these files small if desired
empty:        # !!bool, flag to explicitly check if a stream is empty or nonempty. all other checks are ignored
start:        # !!int, 0-indexed line offset to specify where to start comparisons
count:        # !!int, number of lines to compare
```

All fields are optional, so long as whatever is (or is not) specified makes sense.

\*\*\* These fields are dictionaries and in addition to the fields specified above, the following fields are allowed:

```yaml
test-file:    # !!str, path to file generated, absolute or relative to the executable
exists:       # !!bool, flag to check if the file exists. all other checks are ignored
binary:       # !!bool, flag to indicate the file is binary
```

Other than `test-file`, each field is optional, so long as whatever is (or is not) specified makes sense.

## Basic Usage

Given some configuration you can run `contest` using the following:

```shell
contest <path to configuration file>
```

This will parse the configuration and run the specified test case(s). In the configuration file each test case is defined under the `test-cases` node in the recipe; simply add a new section as desired. You will just need to make sure each test is named uniquely. Here is an example of a test recipe (taken from `examples/native_console_app`):

```yaml
executable: hello_world.exe
test-cases:
  - name: standard
    stdin: Lnk2past
    stdout: |
      Hello! What is your name?
      Welcome to the world, Lnk2past!
```

Let us break down what this is specifying:

1. The name of the `executable` to run is

    ```text
    hello_world.exe
    ```

2. We have a single test-case named

    ```text
    standard
    ```

3. We define the input to `stdin`, which is a single entry:

    ```text
    Lnk2past
    ```

4. We define the output to `stdout`, which is:

    ```text
    Hello! What is your name?
    Welcome to the world, Lnk2past!
    ```

This is really the equivalent of the following in some shell environment:

```shell
~/project> ./hello_world.exe
Hello! What is your name?
Lnk2past
Welcome to the world, Lnk2past!
```

This means that when running the executable `hello_world.exe` we can expect the input in step 3 to yield the output in step 4. `contest` does this comparison for you! This allows you to write tests that would reflect actual use cases of your executable. Add as many tests as you like to cover various pathways through your program and to cover the various errors your program may encounter.

Check out the other examples under the `examples` directory.

### Test Directories

`contest` will run each test-case in a separate directory, and will create those directories in the same directory containing the test recipe. This ensures minimal conflict between test cases. For example, if your test recipe contains test cases "foo" and "bar" and is located in "C:\Users\Lnk2past\MyProject", then you can expect the following directory structure:

```text
C:\Users\Lnk2past\MyProject\
|---src\...
|---include\...
|---contest_recipe.yaml
|---test_output\
    |---foo\...
    |---bar\...
```

Even if your test-case produces no output on disk, the test-output directory will be created.

### Filtering Tests

You can filter your test-recipes to only run a select few. This may be useful during debugging to only run your new test without needing to run the entire test recipe. You can do this via the `--filter` option. This expects some `regular expression` to filter on. e.g. we can test only those tests that are marked with a specific keyword in their names, say "tracking", by doing the following:

```shell
contest test_recipe.yaml --filter "tracking"
```

Likewise, you can exclude specific tests in order if they are problematic or if you are focusing on other tests. simply use the `--exclude-filters` or `--exclude` for short. So long as you know `regex` you can do whatever you like for filtering your tests!
