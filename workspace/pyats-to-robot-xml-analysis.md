# PyATS results.json to Robot Framework output.xml Conversion Analysis

## Executive Summary

This document analyzes the pyATS `results.json` structure and compares it with Robot Framework's `output.xml` format to design a conversion strategy. The goal is to create a Robot-compatible output.xml from pyATS test results that can be visualized using Robot Framework tooling.

## 1. Structure Comparison

### 1.1 PyATS Structure (results.json)

```
TestSuite (Job)
├── Task (Test Script)
│   └── Testcase
│       ├── SetupSection
│       ├── TestSection (can contain Steps)
│       │   └── Step (optional)
│       └── CleanupSection
```

**Key Elements:**
- **TestSuite**: Top-level container (job execution)
- **Task**: Individual test script execution
- **Testcase**: Test class containing sections
- **Sections**: setup, test methods (TestSection), cleanup
- **Steps**: Optional sub-divisions within test methods (created with `with steps.start()`)

### 1.2 Robot Framework Structure (output.xml)

```
<robot>
└── <suite>
    └── <test>
        └── <kw> (keyword)
            ├── <msg>
            ├── <arg>
            └── <status>
```

**Key Elements:**
- **Suite**: Top-level test suite container
- **Test**: Individual test case
- **Keyword (kw)**: Atomic action/verification (like a function call)
- **Messages**: Log output from keywords
- **Status**: Pass/Fail with timing information

### 1.3 Mapping Strategy

| PyATS Element | Robot Element | Notes |
|---------------|---------------|-------|
| TestSuite (Job) | `<suite>` | Top-level suite |
| Task | `<suite>` (nested) | Nested suite for each test script |
| Testcase | `<test>` | Individual test case |
| SetupSection | `<kw name="Setup">` | Setup keyword |
| TestSection | `<kw name="[method_name]">` | Test method as keyword |
| Step | `<kw name="[step_name]">` | Nested keyword for steps |
| CleanupSection | `<kw name="Cleanup">` | Cleanup keyword |

## 2. PyATS Results Structure Analysis

### 2.1 File Locations

From the examined results directory:
```
workspace/pyats_results/
├── api/
│   ├── results.json
│   └── TaskLog.verify_sdwanmanager_*
├── d2d/
│   ├── sd-dc-c8kv-01/
│   │   ├── results.json
│   │   ├── TaskLog.*
│   │   ├── reporter.log
│   │   ├── env.txt
│   │   └── *.log (device-specific logs)
│   └── sd-dc-c8kv-02/
│       └── (similar structure)
└── combined_summary.html
```

### 2.2 Results.json Structure

**Top Level:**
```json
{
  "version": "3.4",
  "report": {
    "job_type": "easypy",
    "suite_name": "tmpyrmjj3gj_api_job",
    "type": "TestSuite",
    "id": "tmpyrmjj3gj_api_job_2026Jan26_12_31_33_099372",
    "name": "tmpyrmjj3gj_api_job",
    "starttime": "2026-01-26 12:31:37.586710+01:00",
    "stoptime": "2026-01-26 12:31:39.463937+01:00",
    "runtime": 1.877227,
    "summary": {
      "passed": 0,
      "passx": 0,
      "failed": 2,
      "errored": 0,
      "aborted": 0,
      "blocked": 0,
      "skipped": 0,
      "total": 2,
      "success_rate": 0.0
    },
    "result": {"value": "failed"},
    "totaltasks": 2,
    "tasks": [...]
  }
}
```

**Task Structure:**
```json
{
  "type": "Task",
  "id": "verify_sdwanmanager_all_sd_wan_edge_configurations_are_in_sync",
  "name": "verify_sdwanmanager_all_sd_wan_edge_configurations_are_in_sync",
  "script_type": "aetest",
  "starttime": "2026-01-26 12:31:37.794824+01:00",
  "stoptime": "2026-01-26 12:31:38.536117+01:00",
  "runtime": 0.741293,
  "description": "...",
  "logfile": "TaskLog.verify_sdwanmanager_all_sd_wan_edge_configurations_are_in_sync",
  "testscript": "/path/to/test.py",
  "xref": {
    "git": {
      "repo": "github.com/netascode/nac-test",
      "commit": "ff1565699308547ab87ba9dc89fce69a1e5642be",
      "branch": "pyats-robot-integrtion-tests",
      "file": "tests/integration/fixtures/..."
    }
  },
  "summary": {...},
  "result": {"value": "failed"},
  "sections": [...]
}
```

**Testcase Structure:**
```json
{
  "type": "Testcase",
  "id": "VerifySDWANManagerEdgeConfigSync",
  "name": "VerifySDWANManagerEdgeConfigSync",
  "testcase_type": "aetest",
  "starttime": "2026-01-26 12:31:37.833861+01:00",
  "stoptime": "2026-01-26 12:31:38.535585+01:00",
  "runtime": 0.701724,
  "description": "...",
  "xref": {...},
  "logs": {
    "file": "TaskLog.verify_sdwanmanager_all_sd_wan_edge_configurations_are_in_sync",
    "begin": 4128,
    "begin_lines": 17,
    "size": 46071,
    "size_lines": 208
  },
  "result": {"value": "failed"},
  "sections": [
    {"type": "SetupSection", ...},
    {"type": "TestSection", ...},
    {"type": "CleanupSection", ...}
  ]
}
```

**Step Structure (within TestSection):**
```json
{
  "type": "Step",
  "id": "STEP 1",
  "name": "SDWAN Edge Configuration Sync Status Verification",
  "starttime": "2026-01-26 12:31:38.479703+01:00",
  "stoptime": "2026-01-26 12:31:38.486585+01:00",
  "runtime": 0.006882,
  "logs": {
    "file": "TaskLog.verify_sdwanmanager_all_sd_wan_edge_configurations_are_in_sync",
    "begin": 29588,
    "begin_lines": 130,
    "size": 15437,
    "size_lines": 71
  },
  "result": {
    "value": "failed",
    "reason": "**SDWAN Edge Configuration Sync Status Check FAILED**..."
  },
  "details": ["Failed reason: ..."]
}
```

## 3. Keyword Mapping Strategy

### 3.1 Challenge: No Direct 1:1 Correspondence

PyATS doesn't have a direct equivalent to Robot's "keywords" concept. However, we can create logical mappings:

**Option 1: Flat Keyword Structure**
```xml
<test id="s1-t1" name="VerifySDWANManagerEdgeConfigSync">
  <kw name="Setup" type="SETUP">
    <status status="PASS" start="..." elapsed="..."/>
  </kw>
  <kw name="test_edge_config_sync" type="KEYWORD">
    <status status="FAIL" start="..." elapsed="...">
      Error message here
    </status>
  </kw>
  <kw name="Cleanup" type="TEARDOWN">
    <status status="PASS" start="..." elapsed="..."/>
  </kw>
</test>
```

**Option 2: Nested Keyword Structure with Steps**
```xml
<test id="s1-t1" name="VerifySDWANManagerEdgeConfigSync">
  <kw name="Setup" type="SETUP">
    <status status="PASS" start="..." elapsed="..."/>
  </kw>
  <kw name="test_edge_config_sync" type="KEYWORD">
    <kw name="STEP 1: SDWAN Edge Configuration Sync Status Verification" type="KEYWORD">
      <msg time="..." level="FAIL">**SDWAN Edge Configuration Sync Status Check FAILED**...</msg>
      <status status="FAIL" start="..." elapsed="...">
        Failure reason
      </status>
    </kw>
    <status status="FAIL" start="..." elapsed="..."/>
  </kw>
  <kw name="Cleanup" type="TEARDOWN">
    <status status="PASS" start="..." elapsed="..."/>
  </kw>
</test>
```

### 3.2 Recommended Approach: **Option 2 (Nested with Steps)**

Advantages:
- Preserves step-level granularity for detailed test results
- Allows visualization of which specific step failed
- More intuitive for users familiar with Robot's hierarchical structure
- Can include detailed failure messages at the step level

## 4. Log Data Integration

### 4.1 Available Log Files

From the examined results:
1. **TaskLog files**: Contain detailed execution logs
2. **reporter.log**: Contains structured event data
3. **Device-specific logs**: CLI interaction logs (e.g., `sd-dc-c8kv-01-cli-*.log`)
4. **env.txt**: Environment information

### 4.2 Log Integration Strategy

**Rich Data Sources:**
```json
"logs": {
  "file": "TaskLog.verify_sdwanmanager_all_sd_wan_edge_configurations_are_in_sync",
  "begin": 29588,
  "begin_lines": 130,
  "size": 15437,
  "size_lines": 71
}
```

**What to Extract:**
1. **Step-level details** from `result.reason` and `details` fields
2. **Log excerpts** from TaskLog files (using begin/size pointers)
3. **Failure diagnostics** from the detailed failure messages
4. **Device output** from device-specific CLI logs

**Integration as Robot Messages:**
```xml
<kw name="STEP 1: Verification">
  <msg time="2026-01-26T12:31:38.479703" level="INFO">
    Starting SDWAN Edge Configuration Sync Status Verification
  </msg>
  <msg time="2026-01-26T12:31:38.486585" level="FAIL">
    **SDWAN Edge Configuration Sync Status Check FAILED**

    Validation Results:
    [FAIL] Device 'test_device_CG1' (System IP: 100.1.1.1) configStatusMessage: Sync Pending
    [FAIL] Device 'test_device_CG2' (System IP: 100.1.1.2) configStatusMessage: Sync Pending
    [PASS] Device 'sd-dc-c8kv-01' (System IP: 10.0.0.1) configStatusMessage: In Sync
    ...
  </msg>
  <status status="FAIL" start="2026-01-26T12:31:38.479703" elapsed="0.006882">
    SDWAN Edge Configuration Sync Status Check FAILED
  </status>
</kw>
```

## 5. Proposed XML Structure

### 5.1 Complete Example

```xml
<?xml version="1.0" encoding="UTF-8"?>
<robot generator="PyATS-to-Robot Converter" generated="2026-01-26T12:31:39.463937" rpa="false" schemaversion="5">
  <suite id="s1" name="tmpyrmjj3gj_api_job" source="/var/folders/.../tmpyrmjj3gj_api_job.py">
    <suite id="s1-s1" name="verify_sdwanmanager_all_sd_wan_edge_configurations_are_in_sync">
      <test id="s1-s1-t1" name="VerifySDWANManagerEdgeConfigSync" line="60">
        <doc>
          [SDWAN-Manager] Verify All SD-WAN Edge Configurations Are In-Sync

          This test verifies that all SD-WAN edge devices with a configured system IP
          and that are managed have their configuration 'In Sync'.
        </doc>

        <kw name="setup" type="SETUP" owner="PyATS">
          <doc>Setup method that extends the generic base class setup.</doc>
          <status status="PASS" start="2026-01-26T12:31:37.875594+01:00" elapsed="0.11889"/>
        </kw>

        <kw name="test_edge_config_sync" type="KEYWORD" owner="PyATS">
          <doc>Entry point - delegates to base class orchestration.</doc>

          <kw name="STEP 1: SDWAN Edge Configuration Sync Status Verification" type="KEYWORD">
            <msg time="2026-01-26T12:31:38.479703+01:00" level="INFO">Starting verification step</msg>
            <msg time="2026-01-26T12:31:38.486585+01:00" level="FAIL">
**SDWAN Edge Configuration Sync Status Check FAILED**

One or more managed SDWAN edge devices do not have configuration status 'In Sync'.

**Validation Results:**
[FAIL] Device 'test_device_CG1' (System IP: 100.1.1.1) configStatusMessage: Sync Pending
[FAIL] Device 'test_device_CG2' (System IP: 100.1.1.2) configStatusMessage: Sync Pending
[PASS] Device 'sd-dc-c8kv-01' (System IP: 10.0.0.1) configStatusMessage: In Sync
[PASS] Device 'sd-dc-c8kv-02' (System IP: 10.0.0.2) configStatusMessage: In Sync

**Edge Configuration Sync Status:**
• Total checked devices: 8
• Devices 'In Sync': 5
• Devices out-of-sync: 3
            </msg>
            <status status="FAIL" start="2026-01-26T12:31:38.479703+01:00" elapsed="0.006882">
              SDWAN Edge Configuration Sync Status Check FAILED
            </status>
          </kw>

          <status status="FAIL" start="2026-01-26T12:31:38.054515+01:00" elapsed="0.438998"/>
        </kw>

        <kw name="cleanup" type="TEARDOWN" owner="PyATS">
          <doc>Clean up test resources and save test results.</doc>
          <status status="PASS" start="2026-01-26T12:31:38.528443+01:00" elapsed="0.00581"/>
        </kw>

        <status status="FAIL" start="2026-01-26T12:31:37.833861+01:00" elapsed="0.701724">
          SDWAN Edge Configuration Sync Status Check FAILED
        </status>
      </test>
      <status status="FAIL" start="2026-01-26T12:31:37.794824+01:00" elapsed="0.741293"/>
    </suite>

    <status status="FAIL" start="2026-01-26T12:31:37.586710+01:00" elapsed="1.877227"/>
  </suite>

  <statistics>
    <total>
      <stat pass="0" fail="2" skip="0">All Tests</stat>
    </total>
    <suite>
      <stat name="tmpyrmjj3gj_api_job" id="s1" pass="0" fail="2" skip="0">tmpyrmjj3gj_api_job</stat>
    </suite>
  </statistics>

  <errors/>
</robot>
```

## 6. Implementation Considerations

### 6.1 Timestamp Conversion

PyATS uses ISO 8601 with timezone:
```
"2026-01-26 12:31:37.586710+01:00"
```

Robot Framework uses ISO 8601 format:
```
"2026-01-26T12:31:37.586710"
```

**Conversion needed**: Replace space with 'T', optionally strip timezone.

### 6.2 Status Mapping

| PyATS Status | Robot Status | Notes |
|--------------|--------------|-------|
| passed | PASS | Direct mapping |
| failed | FAIL | Direct mapping |
| errored | FAIL | Treat as failure |
| aborted | FAIL | Treat as failure |
| blocked | SKIP | Treat as skip (test didn't run due to setup failure) |
| skipped | SKIP | Direct mapping |
| passx | PASS | Expected failure that passed |

### 6.3 ID Generation

Robot uses hierarchical IDs:
- Suite: `s1`, `s1-s1`, `s1-s2`
- Test: `s1-t1`, `s1-s1-t1`, `s1-s1-t2`

Algorithm:
```python
def generate_robot_id(parent_id, index, type):
    if type == 'suite':
        return f"{parent_id}-s{index}" if parent_id else f"s{index}"
    elif type == 'test':
        return f"{parent_id}-t{index}"
```

### 6.4 Log Message Enrichment

Extract from TaskLog files using the log pointers:
```python
def extract_log_excerpt(log_file, begin_bytes, size_bytes):
    with open(log_file, 'r') as f:
        f.seek(begin_bytes)
        return f.read(size_bytes)
```

Then parse and convert to Robot `<msg>` elements with appropriate levels (INFO, WARN, FAIL, ERROR).

## 7. Benefits of Conversion

### 7.1 Visualization

Robot Framework ecosystem provides:
- **rebot**: HTML report generation
- **robot.libdoc**: Documentation generation
- **robot.log**: Interactive log viewer with collapsible sections
- **Jenkins Robot Plugin**: CI/CD integration
- **Allure**: Modern reporting with test history

### 7.2 Unified Reporting

- Combine PyATS and Robot test results in a single report
- Use existing Robot reporting infrastructure
- Leverage Robot's test analytics and trending tools

### 7.3 Enhanced Detail

By including log excerpts and device output:
- More context for failures
- Step-by-step execution visualization
- Device interaction details visible in the report

## 8. Recommendations

### 8.1 Immediate Actions

1. **Use nested keyword structure** (Option 2) to preserve step granularity
2. **Include failure details** from `result.reason` and `details` fields as `<msg>` elements
3. **Map blocked tests to SKIP** status to indicate they didn't execute
4. **Generate hierarchical IDs** following Robot's convention

### 8.2 Enhanced Features

1. **Extract log excerpts**: Use the log file pointers to pull relevant sections into `<msg>` elements
2. **Include xref data**: Add git commit/branch info as test metadata or tags
3. **Device output**: For device tests, include CLI command output as messages
4. **Summary statistics**: Generate proper Robot statistics section with pass/fail counts

### 8.3 Optional Enhancements

1. **Tags**: Convert pyATS metadata to Robot tags for filtering
2. **Test documentation**: Include full descriptions from pyATS
3. **Timing visualization**: Preserve exact timing for performance analysis
4. **Links to artifacts**: Reference original pyATS logs from Robot report

## 9. Conclusion

Converting pyATS results.json to Robot Framework output.xml is feasible with a clear mapping strategy:

- **Suite → Suite → Test** hierarchy maps to **Job → Task → Testcase**
- **Keywords** can represent **Sections** (setup/test/cleanup) and **Steps**
- **Rich failure data** from pyATS can be embedded as Robot messages
- **Log artifacts** can be integrated for comprehensive reporting

The nested keyword structure with step-level detail provides the best balance of compatibility and information richness for visualization in Robot Framework tools.
