# 2.1.0

## Features

- **Packaged templates, filters and tests** (EXPERIMENTAL, may change in future versions and is not subject to semantic versioning guarantees)
  - Add `--artifacts/--no-artifacts` CLI option (env `NAC_TEST_ARTIFACTS`) to opt in to loading templates, Jinja filters and Jinja tests from bundles and modules; it is off by default for now (implied by `--bundle` and `--module-dir`) and will become the default in a future version.
  - Bundles and the module are looked up relative to the current working directory (`nac/bundles/`, `nac/overrides.yaml`, `.terraform/` or `TF_DATA_DIR`), not the `-d` or `-t` location.
  - Templates, Jinja filters and Jinja tests can now also come from bundles dropped into the project (every `.zip`, `.tar.gz` or `.tgz` file and every directory in `nac/bundles/`, holding `tests/{templates,jinja_filters,jinja_tests}` at the bundle root) and from the `nac/tests/{templates,jinja_filters,jinja_tests}` directories of an installed Terraform/OpenTofu module, discovered through `nac-artifacts`. Local `-t`/`-f`/`--tests` take priority over the bundle, which takes priority over the module. Templates are replaced by relative path (several directories are merged into `<output>/merged_templates/`), filters and Jinja tests by their declared name. A single templates directory is used in place, so existing setups behave as before.
  - Several bundles are peers of one priority tier and may split templates, filters and Jinja tests between them; a template path, filter or Jinja test provided by two bundles is an error naming both, as are two bundles with the same manifest `name`. Bundles in `nac/bundles/` that provide nothing for nac-test are skipped.
  - Add `--bundle` (repeatable) and `--module-dir` CLI options (env `NAC_TEST_BUNDLE`, `NAC_TEST_MODULE_DIR`).
  - `overrides.yaml` can disable templates of lower layers (`disable: {templates: [...]}`, relative paths or globs): `nac/overrides.yaml` in the project disables templates of a bundle and the module, a bundle's `overrides.yaml` disables templates of the module. Local templates are never affected. Entries are declarative: one that matches nothing is not an error, and `--list-artifacts` shows disabled templates and entries that matched none.
  - `-t/--templates` is optional when a module or bundle provides templates (with `--artifacts`); nac-test exits with an error if no layer provides any.
  - Add `--list-artifacts` to show the layers, effective templates, filters and tests.
- robot rendering: added support for dicts as parent_key in `iterate_list_chunked`
- add `NAC_TEST_DUMP_YAML_DATA_MODEL` environment variable to also write the merged data model as YAML (alongside the JSON file) for post-run inspection/debugging. The YAML file is not auto-cleaned up and may contain sensitive values (passwords, tokens, credentials), so review and remove it manually.
- add support for SDWAN token authentication for pyATS test cases via SDWAN_USERNAME & SDWAN_API_TOKEN

## Performance

- yaml parser: enabled C-accelerated parser/emitter (`ruamel.yaml.clib` / `pure=False`) in YAML utilities. Speeds up YAML loading and data model merge operations by ~3x on CPython.
- pyATS execution performance enhancements:
  - Replace batched device barriers with flat semaphore for D2D execution, eliminating idle time when devices finish at different speeds (#901)
  - broker: removed the per-command SSH liveness probe from the connection broker; dead sessions are now recovered by reconnecting and retrying the command once. Removes ~0.77s of event-loop blocking per test and the fleet-wide slowdown it caused.
  - broker: command rejections (SubCommandFailure) no longer trigger a full SSH disconnect and cache wipe; only transport-level failures do. Eliminates a 4.7x per-failure penalty on devices with unsupported commands.
  - broker: disconnect all devices concurrently during broker shutdown via `asyncio.gather`, reducing post-test teardown from O(n × disconnect_time) to O(max(disconnect_time)) also for user-provided testbeds where timeout settings might be missing.

## Bug Fixes

- controller URLs: embedded credentials (userinfo) and trailing slashes are stripped from URLs shown in auth-failure banners, the HTML report (`controller_url`, curl and ping hints) and the pre-flight log. Passwords containing unencoded `/`, `?` or `#` are covered, and `extract_host()` no longer returns the port or userinfo for schemeless URLs. The `AuthCache` invalidation log line no longer prints the raw URL.
- dependencies: update nac-yaml to 2.1.0: `!vault` values are now decrypted with the password from `ANSIBLE_VAULT_PASSWORD`.
- dependencies: pin `scrapli<2026.10.0` to prevent breaking changes and installation failures introduced in scrapli 2026.10+ (#965).
- jinja filters/tests: two files in the same directory declaring the same filter or test name now raise an error instead of one silently replacing the other depending on directory listing order. Files are loaded in sorted order. A filter or test directory that relied on listing order to pick one of two same-named files now fails; rename or remove one of them.
- Genie parsers that fire supplementary commands (e.g. VRF resolution) now work in broker mode

## Other Changes

- pyats: **Breaking Change**: `SSHTestBase.parse_output()` is now async. Custom pyATS test cases calling it must use `await self.parse_output(...)`.
- python: dropped support for Python 3.10 (end-of-life). Python 3.11 is now the minimum supported version.
- **Internal merged data model file format changed to JSON**: For performance reasons, the internal temporary file used to pass the merged data model to test subprocesses is now written as JSON (`merged_data_model_test_variables.json`, previously `.yaml`). This has no effect on your YAML data files or data model structure. The standard `self.data_model` API is unaffected. It only matters if your tests or scripts read the file directly via the `MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH` environment variable — in that case, switch from YAML parsing to `json.load()`. Note two JSON serialization differences versus the previous YAML format: non-string mapping keys (e.g. integer keys such as VLAN IDs used as keys) are coerced to strings, and values that JSON cannot represent natively (e.g. unquoted YAML dates parsed as `datetime.date`) are written as their string form. Quote such keys/values in your data files if you need them preserved as strings anyway.

# 2.0.1

## Bug Fixes

- dependencies: pin `scrapli<2026.10.0` to prevent breaking changes and installation failures introduced in scrapli 2026.10+.
- dependencies: exclude pyATS and Genie 26.9 due to missing aarch64 wheels.
- dependencies: backport updated python and dependabot dependency versions.

# 2.0.0

## Major Features

- **pyATS Integration** (EXPERIMENTAL): Full support for pyATS operational test cases
  - Initial support for ACI, SD-WAN, and Catalyst Center architectures
  - IOS-XE Direct-to-Device (D2D) SSH tests for SD-WAN and Catalyst Center
  - Experimental `--pyats` and `--robot` flags to limit test execution to one framework
  - **Windows**: Robot tests only — PyATS libraries are not available on Windows. For PyATS tests, use WSL2 as an alternative.
  - **macOS requires Python 3.12+**: Earlier Python versions have known fork/SSL incompatibilities causing crashes during pyATS execution.
- **Combined Dashboard**: New `combined_summary.html` report linking Robot and pyATS summaries
- **Merged xUnit Output**: Robot and pyATS results merged into single `xunit.xml` for CI/CD integration
- **Diagnostic Collection**: `--diagnostic` flag wraps execution to collect troubleshooting info (env, packages, logs)
- **Fail-Fast Authentication**: Controller authentication validated before pyATS test execution starts

## Breaking Changes

- **Robot artifacts moved**: Output files (`log.html`, `report.html`, etc.) now created in `robot_results/` subdirectory; links in root directory for backward compatibility
- **Robot suite names changed**: Top-level Robot suite names now start with `Robot Results` instead of the output directory name. Use Robot's `--name MyProject` argument to override the top-level suite name when needed.
- **RESTinstance removed from core dependencies**: The `RESTinstance` Robot library has been removed. Users who still need RESTinstance can install it separately alongside nac-test.
- **Robot Framework arguments require `--` separator**: Additional Robot Framework arguments must now be passed after the `--` separator (e.g., `nac-test ... -- --variable X:Y`). Arguments passed directly without the separator are no longer accepted. Certain Robot options (like `--include`, `--exclude`, `--outputdir`) are controlled by nac-test and cannot be passed via `--`; use the corresponding nac-test options instead (e.g., `-i`/`--include`, `-e`/`--exclude`, `-o`/`--output`).
- **Removed legacy `iac-test` entrypoint**: Use `nac-test` instead.
- **nac-yaml v2.0**: YAML file merge behavior has changed (can affect data model merging results):
  - Within-file duplicates now disable merging for that entire list: if any input file contains duplicate dict items in a list, that list is concatenated (no merging) to preserve within-file duplicates. This can result in more items than before.
  - Relaxed matching logic: list dict items now merge when all shared primitive keys match; unique primitive keys present on only one side no longer prevent merging. Items that previously stayed separate may now be combined.
  - Details and examples: https://github.com/netascode/nac-yaml/pull/34

## CLI Changes

- **Added `--verbose`**: Enables verbose output for nac-test, Robot Framework, and pyATS execution
- **Added `--loglevel`** (replaces `--verbosity`): Control log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Deprecated `--verbosity`**: Hidden alias for `--loglevel`, will be removed in future version

## Environment Variable Changes

- **Renamed**: `NO_TESTLEVELSPLIT` → `NAC_TEST_DISABLE_TESTLEVELSPLIT` (now requires explicit `true`/`yes`/`1`)
- **Removed**: `NAC_VALIDATE_VERBOSITY` (was incorrectly named; use `NAC_TEST_LOGLEVEL`)

## Other Improvements

- Upgraded pabot to 5.2.2
- Streamlined CLI output with cleaner progress reporting
- `--minimal-reports` reduces pyATS HTML report size by 80-95% (only failed tests include full details)
- Consolidated rendered Robot templates, pabot intermediate files, and Robot result files under `robot_results/` to avoid output-root namespace collisions

# 1.2.3

- Exclude jsonpath-ng 1.8.0 due to upstream regression (#603)

# 1.2.2

- Add NETCONF related packages

# 1.2.1

- Fix path handling on Windows platform

# 1.2.0

- Add `--processes` CLI argument to configure the number of parallel processes for test execution
- Increase robot loglevel to `DEBUG` when verbosity of `nac-tool` is set to `DEBUG`
- Add `robotframework-jmespath` as a direct dependency
- Add support for test case parallelization for capable suites
- Return Robot/Pabot exit codes and improve error messages
- Add support for passing extra Robot Framework options to `nac-test`
- EXPERIMENTAL: Add support for chunking templates using the `iterate_list_chunked` directive

# 1.1.0

- Enhance error handling and logging
- Migrate to `uv` package manager
- Update license references

# 1.0.0

- BREAKING CHANGE: Rename tool from `iac-test` to `nac-test`
- Modernize CLI interface using [typer](https://github.com/fastapi/typer)
- BREAKING CHANGE: Do not deduplicate items in a list of primitive values, for example a list of strings
- BREAKING CHANGE: Deduplicate items in a list of dictionaries consistently, regardless of whether they are in the same file or not
- Randomize pabot port to avoid conflicts with multiple instances of `nac-test` running in parallel
- Be more strict about undefined variables in Jinja templates

# 0.2.6

- Fix issue with directly nested lists in YAML files

# 0.2.5

- Add dry-run option
- Make Robot include and exclude tags available in render process (`robot_include_tags` and `robot_exclude_tags` variables)

# 0.2.4

- Also copy non-robot files to temporary directory used for executing the tests

# 0.2.3

- Handle file errors gracefully
- Allow empty YAML files

# 0.2.2

- Do not merge YAML dictionary list items, where each list item has unique attributes with primitive values

# 0.2.1

- Fix issue with YAML attributes named `tag`
- Fix multiple instances of `include` and `exclude` CLI arguments

# 0.2.0

- Add support for ansible-vault encrypted values
- Add `!env` tag to read values from environment variables

# 0.1.5

- Fix bug related to nested template directories

# 0.1.4

- Upgrade to Robot Framework 6.x
- Add option to provide CLI arguments as environment variables

# 0.1.3

- Add xUnit output (`xunit.xml`)

# 0.1.2

- Add custom Jinja tests
- Add iterate_list_folder rendering directive

# 0.1.1

- Add CLI options to select test cases by tag
- Add Requests and JSONlibrary

# 0.1.0

- Initial release
