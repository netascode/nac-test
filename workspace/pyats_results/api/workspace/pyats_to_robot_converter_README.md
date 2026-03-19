# PyATS to Robot Framework XML Converter

A Python tool to convert pyATS `results.json` files to Robot Framework `output.xml` format for enhanced visualization and reporting.

## Features

- ✅ **Hierarchical Structure**: Converts pyATS TestSuite → Task → Testcase to Robot Suite → Suite → Test
- ✅ **Nested Keywords**: Maps pyATS sections (setup/test/cleanup) and steps to Robot keywords
- ✅ **Test Documentation**: Preserves test descriptions and documentation
- ✅ **Timing Information**: Maintains accurate start/stop times and elapsed durations
- ✅ **Log Excerpts**: Extracts and includes relevant log sections from TaskLog files
- ✅ **Failure Details**: Includes detailed failure messages with full context
- ✅ **Statistics**: Generates Robot-compatible test statistics
- ✅ **Batch Processing**: Recursively finds and converts all results.json files in a directory tree

## Installation

The converter is a standalone Python module with no external dependencies beyond the standard library:

```bash
# Make it executable
chmod +x pyats_to_robot_converter.py

# Or run with Python
python pyats_to_robot_converter.py
```

## Usage

### Command Line

```bash
# Convert all results in a directory
python pyats_to_robot_converter.py /path/to/pyats_results

# Convert multiple directories
python pyats_to_robot_converter.py /path/to/results1 /path/to/results2

# Verbose output
python pyats_to_robot_converter.py -v /path/to/pyats_results
```

### As a Module

```python
from pyats_to_robot_converter import PyATSToRobotConverter

# Initialize with results directory
converter = PyATSToRobotConverter("/path/to/pyats_results")

# Convert all results.json files found
converted_count = converter.convert_all()

# Or convert a specific file
output_path = converter.convert_file(Path("/path/to/results.json"))
```

## Output

The converter creates an `output.xml` file in the same directory as each `results.json` file:

```
pyats_results/
├── api/
│   ├── results.json
│   ├── output.xml          ← Generated
│   └── TaskLog.*
├── d2d/
│   ├── sd-dc-c8kv-01/
│   │   ├── results.json
│   │   ├── output.xml      ← Generated
│   │   └── TaskLog.*
│   └── sd-dc-c8kv-02/
│       ├── results.json
│       ├── output.xml      ← Generated
│       └── TaskLog.*
└── combined_summary.html
```

## Structure Mapping

### PyATS → Robot Framework

| PyATS Element | Robot Element | Description |
|---------------|---------------|-------------|
| TestSuite (Job) | `<suite>` | Top-level test suite |
| Task | `<suite>` (nested) | Test script as nested suite |
| Testcase | `<test>` | Individual test case |
| SetupSection | `<kw type="SETUP">` | Setup keyword |
| TestSection | `<kw type="KEYWORD">` | Test method as keyword |
| Step | `<kw>` (nested) | Step as nested keyword |
| CleanupSection | `<kw type="TEARDOWN">` | Cleanup keyword |

### Status Mapping

| PyATS Status | Robot Status | Notes |
|--------------|--------------|-------|
| passed | PASS | Direct mapping |
| failed | FAIL | Direct mapping |
| errored | FAIL | Treated as failure |
| aborted | FAIL | Treated as failure |
| blocked | SKIP | Test didn't run due to setup failure |
| skipped | SKIP | Direct mapping |
| passx | PASS | Expected failure that passed |

## Example Output

```xml
<?xml version="1.0" encoding="UTF-8"?>
<robot generator="PyATS-to-Robot Converter v1.0" generated="2026-01-26T12:31:39.463937" rpa="false" schemaversion="5">
  <suite id="s1" name="my_test_job">
    <suite id="s1-s1" name="my_test_script">
      <doc>Test script description from pyATS</doc>

      <test id="s1-s1-t1" name="MyTestCase" line="60">
        <doc>Test case description with full details</doc>

        <kw name="setup" type="SETUP" owner="PyATS">
          <doc>Setup method documentation</doc>
          <msg time="2026-01-26T12:31:37.875594" level="INFO">Starting: setup</msg>
          <msg time="2026-01-26T12:31:37.875594" level="DEBUG">Log excerpt from TaskLog...</msg>
          <status status="PASS" start="2026-01-26T12:31:37.875594" elapsed="0.118890"/>
        </kw>

        <kw name="test_my_verification" type="KEYWORD" owner="PyATS">
          <doc>Test method documentation</doc>
          <msg time="2026-01-26T12:31:38.054515" level="INFO">Starting: test_my_verification</msg>

          <!-- Nested step keyword -->
          <kw name="STEP 1: Verification" type="KEYWORD" owner="PyATS">
            <msg time="2026-01-26T12:31:38.479703" level="INFO">Starting: Verification</msg>
            <msg time="2026-01-26T12:31:38.486585" level="FAIL">
              Detailed failure message with all context
              - Device failures
              - Validation results
              - Recommendations
            </msg>
            <status status="FAIL" start="2026-01-26T12:31:38.479703" elapsed="0.006882">
              Failure summary
            </status>
          </kw>

          <status status="FAIL" start="2026-01-26T12:31:38.054515" elapsed="0.438998"/>
        </kw>

        <kw name="cleanup" type="TEARDOWN" owner="PyATS">
          <doc>Cleanup documentation</doc>
          <msg time="2026-01-26T12:31:38.528443" level="INFO">Starting: cleanup</msg>
          <status status="PASS" start="2026-01-26T12:31:38.528443" elapsed="0.005810"/>
        </kw>

        <status status="FAIL" start="2026-01-26T12:31:37.833861" elapsed="0.701724">
          Test failure summary
        </status>
      </test>

      <status status="FAIL" start="2026-01-26T12:31:37.794824" elapsed="0.741293"/>
    </suite>

    <status status="FAIL" start="2026-01-26T12:31:37.586710" elapsed="1.877227"/>
  </suite>

  <statistics>
    <total>
      <stat pass="0" fail="1" skip="0">All Tests</stat>
    </total>
    <tag/>
    <suite>
      <stat name="my_test_job" id="s1" pass="0" fail="1" skip="0">my_test_job</stat>
    </suite>
  </statistics>

  <errors/>
</robot>
```

## Viewing Results

### Using Robot Framework Tools

Generate HTML reports from the converted output.xml:

```bash
# Generate report and log
robot --rpa false --output output.xml --log log.html --report report.html pyats_results/api/

# Or use rebot
rebot --output output.xml pyats_results/api/output.xml
```

### Using Other Tools

- **Jenkins Robot Plugin**: Upload output.xml to Jenkins for CI/CD integration
- **Allure**: Use Allure's Robot Framework adapter
- **Custom Parsers**: Parse the XML with any standard XML parser

## Log Excerpt Extraction

The converter automatically extracts relevant log sections from pyATS TaskLog files:

- Uses byte offset pointers from `results.json` (begin/size fields)
- Filters out verbose debug messages (GIT, UTILS, etc.)
- Limits excerpt size to 10KB to prevent huge messages
- Includes meaningful log context for failures

## Implementation Details

### Key Classes

- **PyATSToRobotConverter**: Main converter class
  - `convert_all()`: Convert all results.json files found
  - `convert_file(path)`: Convert a single results.json file
  - `_add_suite()`: Recursively add suites
  - `_add_test()`: Add test cases
  - `_add_keyword()`: Add keywords (sections/steps)
  - `_extract_log_excerpt()`: Extract log excerpts from TaskLog files

### Design Decisions

1. **Nested Keywords**: Preserves pyATS step structure for detailed failure visualization
2. **Log Filtering**: Removes excessive debug logs while keeping meaningful content
3. **Hierarchical IDs**: Generates Robot-compatible IDs (s1, s1-s1, s1-s1-t1)
4. **Status Mapping**: Maps all pyATS statuses appropriately (blocked → SKIP)
5. **Timestamp Conversion**: Converts ISO 8601 timestamps from pyATS to Robot format

## Benefits

### Enhanced Visualization

- View pyATS results in Robot's interactive HTML log
- Collapsible sections for better navigation
- Step-by-step execution visualization
- Click to expand/collapse log details

### Unified Reporting

- Combine pyATS and Robot test results
- Single reporting infrastructure
- Consistent test analytics
- Cross-platform compatibility

### Rich Context

- Full failure details with diagnostics
- Device interaction logs
- Step-level granularity
- Timing information for performance analysis

## Troubleshooting

### XML Validation Errors

If the generated XML has validation issues:

```python
# Validate XML structure
import xml.etree.ElementTree as ET
tree = ET.parse('output.xml')
print("XML is valid!")
```

### Missing Log Excerpts

If log excerpts aren't appearing:
- Check that TaskLog files are in the same directory as results.json
- Verify the log file names match the `logs.file` field in results.json
- Check file permissions

### Encoding Issues

The converter uses UTF-8 encoding with error handling:
- Non-UTF-8 characters in logs are ignored gracefully
- HTML entities in XML are automatically escaped

## Limitations

- Does not support pyATS CommonSetup/CommonCleanup yet
- Tag conversion not yet implemented
- Git xref data is preserved but not displayed as Robot metadata

## Future Enhancements

- [ ] Add Robot tags from pyATS metadata
- [ ] Support CommonSetup/CommonCleanup
- [ ] Extract device CLI logs as separate messages
- [ ] Add git commit/branch info as test metadata
- [ ] Support for custom log excerpt patterns
- [ ] Merge multiple output.xml files into one

## Contributing

To extend or modify the converter:

1. **Add new section types**: Extend `_add_keyword()` method
2. **Change status mapping**: Modify `STATUS_MAP` dictionary
3. **Customize log extraction**: Override `_extract_log_excerpt()` method
4. **Add metadata**: Extend `_add_test()` to add Robot tags/metadata

## License

This tool is provided as-is for converting pyATS results to Robot Framework format.

## Support

For issues or questions:
- Check the generated XML structure
- Validate with Robot Framework's rebot tool
- Review the pyATS results.json structure
- Enable verbose output with `-v` flag
