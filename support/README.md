# nac-test Support Tools

This directory contains diagnostic and troubleshooting tools for nac-test.

## Diagnostic Collection Script

**Script:** `nac-test-diagnostic.sh`

A cross-platform (macOS/Linux) script that collects comprehensive diagnostic information to help troubleshoot nac-test issues.

### When to Use

Use this script when:

- nac-test crashes, hangs, or shows unexpected errors
- Tests fail with unclear error messages
- You're experiencing platform-specific issues (especially on macOS)
- You need to provide diagnostic information for a GitHub issue

### What It Collects

| Category | Information Collected |
|----------|----------------------|
| **System** | OS version, architecture, CPU, memory |
| **Python** | Version, executable path, virtual environment |
| **Packages** | nac-test, nac-test-pyats-common, PyATS versions |
| **Environment** | Relevant env vars (with sensitive values filtered) |
| **Configuration** | PyATS config, multiprocessing settings |
| **Network** | SSL certificates, proxy settings, connectivity |
| **Crash Reports** | macOS crash reports (before and during execution) |
| **Execution** | nac-test output with debug flags enabled |
| **Results** | PyATS results, HTML reports, archives |

### What It Does NOT Collect

The script is designed with security in mind:

- **Passwords** are automatically masked (`***MASKED***`)
- **Usernames** are automatically masked (`***USER_MASKED***`)
- **Tokens** (including JWTs) are automatically masked
- **URLs with embedded credentials** are masked
- **API keys and secrets** are automatically masked
- **Environment variables** containing sensitive keywords are filtered out

> **Note:** PyATS archive files (`.zip`) are included for completeness but may contain logs with credentials if debug logging was enabled. The script warns about this in its output.

### Usage

1. Navigate to your nac-test project directory (where your `data/` and `tests/` folders are)

2. Set your environment variables as you normally would:
   ```bash
   export SDWAN_URL=https://your-controller.example.com
   export SDWAN_USERNAME=your-username
   export SDWAN_PASSWORD=your-password
   # ... other variables
   ```

3. Run the diagnostic script:
   ```bash
   # Download and run (if not already in repo)
   curl -O https://raw.githubusercontent.com/netascode/nac-test/main/support/nac-test-diagnostic.sh
   chmod +x nac-test-diagnostic.sh
   ./nac-test-diagnostic.sh

   # Or if you have the repo cloned
   /path/to/nac-test/support/nac-test-diagnostic.sh
   ```

4. The script will:
   - Collect system and environment information
   - Run `nac-test` with debug flags
   - Capture any crash reports generated during execution
   - Package everything into a `.zip` file

5. Output:
   ```
   nac-test-diagnostics-YYYYMMDD_HHMMSS/     # Directory with all collected files
   nac-test-diagnostics-YYYYMMDD_HHMMSS.zip  # Compressed archive for sharing
   ```

### Sharing Diagnostic Output

When opening a GitHub issue:

1. Run the diagnostic script as described above
2. Review the generated `.zip` file if you have concerns about sensitive data
3. Attach the `.zip` file to your GitHub issue
4. Reference any specific files in the archive that show the problem

### Script Version

The script displays its version at the start of execution. When reporting issues, please include the script version in your report.

Current version: **4.1**

### Troubleshooting the Script Itself

If the diagnostic script fails to run:

- **Permission denied**: Run `chmod +x nac-test-diagnostic.sh`
- **bash not found**: The script requires bash. On some systems, try `bash ./nac-test-diagnostic.sh`
- **Commands not found**: Some optional diagnostics may fail if tools aren't installed (e.g., `lsof`, `tree`). This is normal and won't affect the core diagnostics.
