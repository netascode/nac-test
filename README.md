[![Tests](https://github.com/netascode/nac-test/actions/workflows/test.yml/badge.svg)](https://github.com/netascode/nac-test/actions/workflows/test.yml)
![Python Support](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-informational "Python Support: 3.10, 3.11, 3.12, 3.13")

# nac-test

A CLI tool to render and execute [Robot Framework](https://robotframework.org/) tests using [Jinja](https://jinja.palletsprojects.com/) templating. Combining Robot's language agnostic syntax with the flexibility of Jinja templating allows dynamically rendering a set of test suites from the desired infrastructure state expressed in YAML syntax.

```
$ nac-test --help

 Usage: nac-test [OPTIONS]                                                      
                                                                                
 A CLI tool to render and execute Robot Framework tests using Jinja templating. 
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --data         -d      PATH                     Path to data YAML files.  │
│                                                    [env var: NAC_TEST_DATA]  │
│                                                    [required]                │
│ *  --templates    -t      DIRECTORY                Path to test templates.   │
│                                                    [env var:                 │
│                                                    NAC_TEST_TEMPLATES]       │
│                                                    [required]                │
│ *  --output       -o      DIRECTORY                Path to output directory. │
│                                                    [env var:                 │
│                                                    NAC_TEST_OUTPUT]          │
│                                                    [required]                │
│    --filters      -f      DIRECTORY                Path to Jinja filters.    │
│                                                    [env var:                 │
│                                                    NAC_TEST_FILTERS]         │
│    --tests                DIRECTORY                Path to Jinja tests.      │
│                                                    [env var: NAC_TEST_TESTS] │
│    --include      -i      TEXT                     Selects the test cases by │
│                                                    tag (include).            │
│                                                    [env var:                 │
│                                                    NAC_TEST_INCLUDE]         │
│    --exclude      -e      TEXT                     Selects the test cases by │
│                                                    tag (exclude).            │
│                                                    [env var:                 │
│                                                    NAC_TEST_EXCLUDE]         │
│    --processes            INTEGER                  Number of parallel        │
│                                                    processes for test        │
│                                                    execution (pabot          │
│                                                    --processes option),      │
│                                                    default is max(2, cpu     │
│                                                    count).                   │
│                                                    [env var:                 │
│                                                    NAC_TEST_PROCESS]         |
|    --render-only                                   Only render tests without │
│                                                    executing them.           │
│                                                    [env var:                 │
│                                                    NAC_TEST_RENDER_ONLY]     │
│    --dry-run                                       Dry run flag. See robot   │
│                                                    dry run mode.             │
│                                                    [env var:                 │
│                                                    NAC_TEST_DRY_RUN]         │
│    --verbosity    -v      [DEBUG|INFO|WARNING|ERR  Verbosity level.          │
│                           OR|CRITICAL]             [env var:                 │
│                                                    NAC_VALIDATE_VERBOSITY]   │
│                                                    [default: WARNING]        │
│    --version                                       Display version number.   │
│    --help                                          Show this message and     │
│                                                    exit.                     │
╰──────────────────────────────────────────────────────────────────────────────╯
```

All data from the YAML files (`--data` option) will first be combined into a single data structure which is then provided as input to the templating process. Each template in the `--templates` path will then be rendered and written to the `--output` path. If the `--templates` path has subfolders, the folder structure will be retained when rendering the templates.

After all templates have been rendered [Pabot](https://pabot.org/) will execute all test suites in parallel and create a test report in the `--output` path. The `--skiponfailure non-critical` argument will be used by default, meaning all failed tests with a `non-critical` tag will show up as "skipped" instead of "failed" in the final test report.

## Installation

Python 3.10+ is required to install `nac-test`. Don't have Python 3.10 or later? See [Python 3 Installation & Setup Guide](https://realpython.com/installing-python/).

`nac-validate` can be installed in a virtual environment using `pip` or `uv`:

```bash
# Using pip
pip install nac-test

# Using uv (recommended)
uv tools install nac-test
```

The following Robot libraries are included with `nac-test`:

- [RESTinstance](https://github.com/asyrjasalo/RESTinstance)
- [robotframework-requests](https://github.com/MarketSquare/robotframework-requests)
- [robotframework-jmespath](https://github.com/netascode/robotframework-jmespath)
- [robotframework-jsonlibrary](https://github.com/robotframework-thailand/robotframework-jsonlibrary)
- [robotframework-pabot](https://pabot.org/) for parallel test execution

Any other libraries can of course be added via `pip` or `uv`.

## Ansible Vault Support

Values in YAML files can be encrypted using [Ansible Vault](https://docs.ansible.com/ansible/latest/user_guide/vault.html). This requires Ansible (`ansible-vault` command) to be installed and the following two environment variables to be defined:

```
export ANSIBLE_VAULT_ID=dev
export ANSIBLE_VAULT_PASSWORD=Password123
```

`ANSIBLE_VAULT_ID` is optional, and if not defined will be omitted.

## Additional Tags

### Reading Environment Variables

The `!env` YAML tag can be used to read values from environment variables.

```yaml
root:
  name: !env VAR_NAME
```

## Example

`data.yaml` located in `./data` folder:

```yaml
---
root:
  children:
    - name: ABC
      param: value
    - name: DEF
      param: value
```

`test1.robot` located in `./templates` folder:

```
*** Settings ***
Documentation   Test1

*** Test Cases ***
{% for child in root.children | default([]) %}

Test {{ child.name }}
    Should Be Equal   {{ child.param }}   value
{% endfor %}
```

After running `nac-test` with the following parameters:

```shell
nac-test --data ./data --templates ./templates --output ./tests
```

The following rendered Robot test suite can be found in the `./tests` folder:

```
*** Settings ***
Documentation   Test1

*** Test Cases ***

Test ABC
    Should Be Equal   value   value

Test DEF
    Should Be Equal   value   value
```

As well as the test results and reports:

```shell
$ tree -L 1 tests
tests
├── log.html
├── output.xml
├── pabot_results
├── report.html
├── test1.robot
└── xunit.xml
```

## Custom Jinja Filters

Custom Jinja filters can be used by providing a set of Python classes where each filter is implemented as a separate `Filter` class in a `.py` file located in the `--filters` path. The class must have a single attribute named `name`, the filter name, and a `classmethod()` named `filter` which has one or more arguments. A sample filter can be found below.

```python
class Filter:
    name = "filter1"

    @classmethod
    def filter(cls, data):
        return str(data) + "_filtered"
```

## Custom Jinja Tests

Custom Jinja tests can be used by providing a set of Python classes where each test is implemented as a separate `Test` class in a `.py` file located in the `--tests` path. The class must have a single attribute named `name`, the test name, and a `classmethod()` named `test` which has one or more arguments. A sample test can be found below.

```python
class Test:
    name = "test1"

    @classmethod
    def test(cls, data1, data2):
        return data1 == data2
```

## Rendering Directives

Special rendering directives exist to render a single test suite per (YAML) list item. The directive can be added to the Robot template as a Jinja comment following this syntax:

```
{# iterate_list <YAML_PATH_TO_LIST> <LIST_ITEM_ID> <JINJA_VARIABLE_NAME> #}
```

After running `nac-test` with the data from the previous [example](#example) and the following template:

```
{# iterate_list root.children name child_name #}
*** Settings ***
Documentation   Test1

*** Test Cases ***
{% for child in root.children | default([]) %}
{% if child.name == child_name %}

Test {{ child.name }}
    Should Be Equal   {{ child.param }}   value
{% endif %}
{% endfor %}
```

The following test suites will be rendered:

```shell
$ tree -L 2 tests
tests
├── ABC
│   └── test1.robot
└── DEF
    └── test1.robot
```

A similar directive exists to put the test suites in a common folder though with a unique filename.

```
{# iterate_list_folder <YAML_PATH_TO_LIST> <LIST_ITEM_ID> <JINJA_VARIABLE_NAME> #}
```

The following test suites will be rendered:

```shell
$ tree -L 2 tests
tests
└── test1
    ├── ABC.robot
    └── DEF.robot
```

An additional directive exists to render a single test suite per (YAML) list item in chunks, which is useful for handling large datasets by splitting them across multiple template files. This is a variant of `iterate_list` that would still create separate folders.

> **Note:** This directive is experimental and may change in future versions. It is not subject to semantic versioning guarantees.

```
{# iterate_list_chunked <YAML_PATH_TO_LIST> <LIST_ITEM_ID> <JINJA_VARIABLE_NAME> <OBJECT_PATH> <CHUNK_SIZE> #}
```

All objects under the OBJECT_PATH will be counted and if their number is greater than the specified chunk size, the list will be split into multiple test suites with suffix `_2`, `_3`, etc.

Consider the following example:

```yaml
---
root:
  children:
    - name: ABC
      param: value
      nested_children:
        - name: Child1
          param: value
        - name: Child2
          param: value
        - name: Child3
          param: value
    - name: DEF
      param: value
      nested_children:
        - name: Child1
          param: value
```

After running `nac-test` with this data from the previous and the following template:

```
{# iterate_list_chunked root.children name child_name nested_children 2 #}
*** Settings ***
Documentation   Test1

*** Test Cases ***
{% for child in root.children | default([]) %}
{% if child.name == child_name %}

Test {{ child.name }}
    Should Be Equal   {{ child.param }}   value

{% for nested_child in child.nested_children | default([]) %}

Test {{ child.name }} Child {{ nested_child.name }}
    Should Be Equal   {{ nested_child.param }}   value
{% endfor %}

{% endif %}
{% endfor %}
```

Objects from the `nested_children` path will be counted and if their number is greater than the specified chunk size (`2`), the list will be split into multiple test suites with suffix `_002`, `_003`, etc. The following test suites will be rendered:

```shell
$ tree -L 2 tests
tests
├── ABC
│   ├── test1_001.robot
│   └── test1_002.robot
└── DEF
    └── test1_001.robot
```


## Select Test Cases By Tag

It is possible to include and exclude test cases by tag names with the `--include` and `--exclude` CLI options. These options are directly passed to the Pabot/Robot executor and are documented [here](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#by-tag-names).


## Parallel Execution Control

The number of parallel processes used by pabot can be controlled via the `--processes` option:

```bash
nac-test -d data/ -t templates/ -o output/ --processes 4
```

If not specified, pabot uses `max(2, cpu_count)` as the default number of processes. You can also set this via the `NAC_TEST_PROCESSES` environment variable.

This option applies to both suite-level and test-level parallelization (see next section).


## Test Case Parallelization

### Suite-Level Parallelization (Default)

By default, `nac-test` (via pabot) executes test **suites** (i.e., each robot file) in parallel. Each suite runs in its own process, and the `--processes` option controls how many suites can run simultaneously.

### Test-Level Parallelization

Suite-level parallelization may be inefficient for test suites containing multiple long-running test cases (e.g., >10 seconds each). If your test cases are independent and can run concurrently, you can enable **test-level parallelization** by adding the following metadata to the suite's settings:

```robot
*** Settings ***
Metadata        Test Concurrency     True
```

**Note:** This approach benefits only long-running tests. For short tests, the scheduling overhead and log collection may offset any performance gains.

**Tip:** The _Test Concurrency_ metadata is case-insensitive (_test concurrency_, _TEST CONCURRENCY_, etc.).

**Implementation:** `nac-test` checks the rendered robot files for the `Metadata` setting and instructs pabot to run each test within the respective suite in parallel (using pabot's `--testlevelsplit --ordering ordering.txt` arguments). You can inspect the `ordering.txt` file in the output directory.

**Disabling test-level parallelization:** Set the environment variable `NAC_TEST_NO_TESTLEVELSPLIT=1` to disable this feature.


## Advanced Robot Framework Options

You can pass additional Robot Framework options directly to `nac-test`, which are forwarded to the pabot/Robot Framework execution. This enables advanced use cases like custom variables, listeners, and logging configuration:

```bash
# Pass custom variables
nac-test -d data/ -t templates/ -o output/ --variable MY_VAR:value

# Multiple variables
nac-test -d data/ -t templates/ -o output/ --variable VAR1:value1 --variable VAR2:value2

# Custom log level
nac-test -d data/ -t templates/ -o output/ --loglevel DEBUG

# Add a listener
nac-test -d data/ -t templates/ -o output/ --listener MyListener.py

# Combine multiple options
nac-test -d data/ -t templates/ -o output/ --variable ENV:prod --loglevel INFO --listener MyListener
```

**Note:** Only Robot Framework options are supported. Pabot-specific options (like `--testlevelsplit`, `--pabotlib`, etc.) and test file paths are not allowed and will result in an error with exit code 252.

See the [Robot Framework User Guide](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#command-line-options) for all available options.
