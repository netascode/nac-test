# nac-test Support Tools

This directory contains diagnostic and troubleshooting tools for nac-test.

## Diagnostic Collection Script

**Script:** `nac-test-diagnostic.sh`

A cross-platform (macOS/Linux), architecture-agnostic script that collects comprehensive diagnostic information to help troubleshoot nac-test issues.

### When to Use

Use this script when:

- nac-test crashes, hangs, or shows unexpected errors
- Tests fail with unclear error messages
- You're experiencing platform-specific issues (especially on macOS)
- You need to provide diagnostic information for a GitHub issue

### Supported Architectures

The script automatically detects your NaC architecture based on environment variables:

| Architecture | Detection Variables |
|-------------|---------------------|
| ACI | `APIC_URL`, `ACI_URL` |
| SD-WAN | `SDWAN_URL` |
| Catalyst Center | `CC_URL` |
| Meraki | `MERAKI_API_KEY` |
| ISE | `ISE_URL` |
| FMC | `FMC_URL` |
| NDO | `NDO_URL` |
| NDFC | `NDFC_URL` |

### What It Collects

| Category | Information Collected |
|----------|----------------------|
| **System** | OS version, architecture, CPU, memory |
| **Python** | Version, executable path, virtual environment |
| **Packages** | nac-test, nac-test-pyats-common, PyATS versions |
| **Environment** | Which env vars are SET (not their values) |
| **Configuration** | PyATS config, multiprocessing settings |
| **Network** | SSL certificates |
| **Crash Reports** | macOS crash reports (before and during execution) |
| **Execution** | Your nac-test command output with debug flags |
| **Results** | PyATS results, HTML reports, archives |

### What It Does NOT Collect

The script is designed with security in mind:

- **Passwords** are automatically masked (`***MASKED***`)
- **Usernames** are automatically masked (`***USER_MASKED***`)
- **Tokens** (including JWTs) are automatically masked
- **URLs with embedded credentials** are masked
- **API keys and secrets** are automatically masked
- **Environment variable values** are never logged (only whether they're SET)

> **Note:** PyATS archive files (`.zip`) are included for completeness but may contain logs with credentials if debug logging was enabled. The script warns about this in its output.

### Usage

**Prerequisites:**
1. Activate your virtual environment
2. Set your environment variables as you normally would
3. Navigate to your project directory (where you run nac-test from)

**Syntax:**
```bash
./nac-test-diagnostic.sh -o <output_dir> "<your nac-test command>"
```

**Examples:**

```bash
# SD-WAN with PyATS tests
./nac-test-diagnostic.sh -o ./results "nac-test -d ./data -t ./tests -o ./results --pyats"

# ACI with Robot Framework tests
./nac-test-diagnostic.sh -o ./output "nac-test -d ./data -t ./tests -o ./output --robot"

# With filters
./nac-test-diagnostic.sh -o ./out "nac-test -d ./data -f ./filters -t ./tests -o ./out"
```

**Step-by-step:**

1. Activate your virtual environment:
   ```bash
   source .venv/bin/activate
   ```

2. Set your environment variables:
   ```bash
   # For SD-WAN:
   export SDWAN_URL=https://your-sdwan-manager.example.com
   export SDWAN_USERNAME=admin
   export SDWAN_PASSWORD=your-password
   export IOSXE_USERNAME=admin
   export IOSXE_PASSWORD=device-password

   # For ACI:
   export APIC_URL=https://your-apic.example.com
   export APIC_USERNAME=admin
   export APIC_PASSWORD=your-password

   # For Catalyst Center:
   export CC_URL=https://your-catalyst-center.example.com
   export CC_USERNAME=admin
   export CC_PASSWORD=your-password
   ```

3. Download and run the diagnostic script:
   ```bash
   curl -O https://raw.githubusercontent.com/netascode/nac-test/main/support/nac-test-diagnostic.sh
   chmod +x nac-test-diagnostic.sh
   ./nac-test-diagnostic.sh -o ./results "nac-test -d ./data -t ./tests -o ./results --pyats"
   ```

4. Output:
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

Current version: **5.0**

### Troubleshooting the Script Itself

If the diagnostic script fails to run:

- **Permission denied**: Run `chmod +x nac-test-diagnostic.sh`
- **bash not found**: The script requires bash. On some systems, try `bash ./nac-test-diagnostic.sh`
- **nac-test not found**: Make sure your virtual environment is activated
- **Missing -o argument**: You must specify the output directory with `-o`
