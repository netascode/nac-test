#!/bin/bash
###############################################################################
# NAC-Test Diagnostic Collection Script v5.0
# CROSS-PLATFORM edition for macOS and Linux troubleshooting
# ARCHITECTURE-AGNOSTIC - works with any NaC architecture
#
# This script will:
# 1. Detect your operating system (macOS or Linux)
# 2. Read your existing environment variables (no configuration needed!)
# 3. Run comprehensive platform-specific diagnostics
# 4. Execute YOUR nac-test command and capture all output
# 5. Collect crash reports, system logs, and debug info
# 6. Zip everything for analysis (credentials are masked)
#
# Usage:
#   ./nac-test-diagnostic.sh -o <output_dir> "<your nac-test command>"
#
# Examples:
#   ./nac-test-diagnostic.sh -o ./results "nac-test -d ./data -t ./tests -o ./results --pyats"
#   ./nac-test-diagnostic.sh -o ./out "nac-test -d ./data -f ./filters -t ./tests -o ./out --robot"
#
# Prerequisites:
#   - Activate your virtual environment BEFORE running this script
#   - Set your environment variables (SDWAN_*, APIC_*, CC_*, etc.) BEFORE running
#   - Run from the directory where you normally run nac-test
#
# Supported Platforms:
#   - macOS (Darwin) - Intel and Apple Silicon
#   - Linux (Ubuntu, RHEL, CentOS, Debian, etc.)
#
# Supported Architectures:
#   - ACI (APIC_URL, APIC_USERNAME, APIC_PASSWORD)
#   - SD-WAN (SDWAN_URL, SDWAN_USERNAME, SDWAN_PASSWORD)
#   - Catalyst Center (CC_URL, CC_USERNAME, CC_PASSWORD)
#   - And any other NaC architecture
###############################################################################

set -o pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

###############################################################################
# ARGUMENT PARSING
###############################################################################

print_usage() {
    echo "Usage: $0 -o <output_dir> \"<nac-test command>\""
    echo ""
    echo "Arguments:"
    echo "  -o <output_dir>    Path to nac-test output directory (required)"
    echo "  <nac-test command> Your full nac-test command in quotes (required)"
    echo ""
    echo "Examples:"
    echo "  $0 -o ./results \"nac-test -d ./data -t ./tests -o ./results --pyats\""
    echo "  $0 -o ./out \"nac-test -d ./data -f ./filters -t ./tests -o ./out\""
    echo ""
    echo "Prerequisites:"
    echo "  1. Activate your virtual environment first"
    echo "  2. Set your environment variables (SDWAN_*, APIC_*, CC_*, etc.)"
    echo "  3. Run from the directory where you normally run nac-test"
}

OUTPUT_DIR=""
NAC_TEST_COMMAND=""

while getopts "o:h" opt; do
    case $opt in
        o)
            OUTPUT_DIR="$OPTARG"
            ;;
        h)
            print_usage
            exit 0
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            print_usage
            exit 1
            ;;
    esac
done

shift $((OPTIND-1))

# The remaining argument is the nac-test command
NAC_TEST_COMMAND="$*"

# Validate required arguments
if [ -z "$OUTPUT_DIR" ]; then
    echo -e "${RED}Error: Output directory (-o) is required${NC}"
    echo ""
    print_usage
    exit 1
fi

if [ -z "$NAC_TEST_COMMAND" ]; then
    echo -e "${RED}Error: nac-test command is required${NC}"
    echo ""
    print_usage
    exit 1
fi

###############################################################################
# OS DETECTION
###############################################################################

OS_TYPE=$(uname -s)
OS_RELEASE=""
OS_PRETTY_NAME=""

case "$OS_TYPE" in
    Darwin)
        OS_PRETTY_NAME="macOS $(sw_vers -productVersion 2>/dev/null || echo 'Unknown')"
        IS_MACOS=true
        IS_LINUX=false
        ;;
    Linux)
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS_PRETTY_NAME="$PRETTY_NAME"
            OS_RELEASE="$ID"
        else
            OS_PRETTY_NAME="Linux (Unknown Distribution)"
            OS_RELEASE="unknown"
        fi
        IS_MACOS=false
        IS_LINUX=true
        ;;
    *)
        echo "Unsupported OS: $OS_TYPE"
        echo "This script supports macOS and Linux only."
        exit 1
        ;;
esac

###############################################################################
# DETECT ARCHITECTURE FROM ENVIRONMENT VARIABLES
###############################################################################

detect_architecture() {
    local arch="Unknown"

    if [ -n "$APIC_URL" ] || [ -n "$ACI_URL" ]; then
        arch="ACI"
    elif [ -n "$SDWAN_URL" ]; then
        arch="SD-WAN"
    elif [ -n "$CC_URL" ]; then
        arch="Catalyst Center"
    elif [ -n "$MERAKI_API_KEY" ]; then
        arch="Meraki"
    elif [ -n "$ISE_URL" ]; then
        arch="ISE"
    elif [ -n "$FMC_URL" ]; then
        arch="FMC"
    elif [ -n "$NDO_URL" ]; then
        arch="NDO"
    elif [ -n "$NDFC_URL" ]; then
        arch="NDFC"
    fi

    echo "$arch"
}

DETECTED_ARCH=$(detect_architecture)

###############################################################################
# SETUP DIAGNOSTIC DIRECTORY
###############################################################################

DIAG_DIR="nac-test-diagnostics-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$DIAG_DIR"

# Master log file
MASTER_LOG="$DIAG_DIR/MASTER_LOG.txt"

# Function to log to both console and master log
log() {
    echo -e "$1" | tee -a "$MASTER_LOG"
}

###############################################################################
# CREDENTIAL MASKING FUNCTION
###############################################################################

mask_credentials_in_file() {
    local file="$1"

    if [ ! -f "$file" ]; then
        return
    fi

    local temp_file="${file}.masking"
    cp "$file" "$temp_file"

    # Mask known credential variables from environment (if set)
    # ACI
    [ -n "$APIC_PASSWORD" ] && sed -i.bak "s|$APIC_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    [ -n "$APIC_USERNAME" ] && sed -i.bak "s|$APIC_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null
    [ -n "$ACI_PASSWORD" ] && sed -i.bak "s|$ACI_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    [ -n "$ACI_USERNAME" ] && sed -i.bak "s|$ACI_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null

    # SD-WAN
    [ -n "$SDWAN_PASSWORD" ] && sed -i.bak "s|$SDWAN_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    [ -n "$SDWAN_USERNAME" ] && sed -i.bak "s|$SDWAN_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null

    # Catalyst Center
    [ -n "$CC_PASSWORD" ] && sed -i.bak "s|$CC_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    [ -n "$CC_USERNAME" ] && sed -i.bak "s|$CC_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null

    # IOS-XE (D2D)
    [ -n "$IOSXE_PASSWORD" ] && sed -i.bak "s|$IOSXE_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    [ -n "$IOSXE_USERNAME" ] && sed -i.bak "s|$IOSXE_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null

    # Meraki
    [ -n "$MERAKI_API_KEY" ] && sed -i.bak "s|$MERAKI_API_KEY|***MASKED***|g" "$temp_file" 2>/dev/null

    # ISE
    [ -n "$ISE_PASSWORD" ] && sed -i.bak "s|$ISE_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    [ -n "$ISE_USERNAME" ] && sed -i.bak "s|$ISE_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null

    # FMC
    [ -n "$FMC_PASSWORD" ] && sed -i.bak "s|$FMC_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    [ -n "$FMC_USERNAME" ] && sed -i.bak "s|$FMC_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null

    # NDO
    [ -n "$NDO_PASSWORD" ] && sed -i.bak "s|$NDO_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    [ -n "$NDO_USERNAME" ] && sed -i.bak "s|$NDO_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null

    # NDFC
    [ -n "$NDFC_PASSWORD" ] && sed -i.bak "s|$NDFC_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    [ -n "$NDFC_USERNAME" ] && sed -i.bak "s|$NDFC_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null

    # Pattern-based masking (case-insensitive)

    # Password variations - key=value format
    sed -i.bak 's/[Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd][[:space:]]*=[[:space:]]*[^[:space:]]*/password=***MASKED***/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/[Pp][Aa][Ss][Ss][Ww][Dd][[:space:]]*=[[:space:]]*[^[:space:]]*/passwd=***MASKED***/g' "$temp_file" 2>/dev/null

    # Password variations - key: value format (YAML)
    sed -i.bak 's/[Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd][[:space:]]*:[[:space:]]*[^[:space:]]*/password: ***MASKED***/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/[Pp][Aa][Ss][Ss][Ww][Dd][[:space:]]*:[[:space:]]*[^[:space:]]*/passwd: ***MASKED***/g' "$temp_file" 2>/dev/null

    # Username variations - key=value format
    sed -i.bak 's/[Uu][Ss][Ee][Rr][Nn][Aa][Mm][Ee][[:space:]]*=[[:space:]]*[^[:space:]]*/username=***USER_MASKED***/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/[Uu][Ss][Ee][Rr][[:space:]]*=[[:space:]]*[^[:space:]]*/user=***USER_MASKED***/g' "$temp_file" 2>/dev/null

    # Username variations - key: value format (YAML)
    sed -i.bak 's/[Uu][Ss][Ee][Rr][Nn][Aa][Mm][Ee][[:space:]]*:[[:space:]]*[^[:space:]]*/username: ***USER_MASKED***/g' "$temp_file" 2>/dev/null

    # Token variations
    sed -i.bak 's/[Tt][Oo][Kk][Ee][Nn][[:space:]]*=[[:space:]]*[^[:space:]]*/token=***MASKED***/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/[Tt][Oo][Kk][Ee][Nn][[:space:]]*:[[:space:]]*[^[:space:]]*/token: ***MASKED***/g' "$temp_file" 2>/dev/null

    # Secret variations
    sed -i.bak 's/[Ss][Ee][Cc][Rr][Ee][Tt][[:space:]]*=[[:space:]]*[^[:space:]]*/secret=***MASKED***/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/[Ss][Ee][Cc][Rr][Ee][Tt][[:space:]]*:[[:space:]]*[^[:space:]]*/secret: ***MASKED***/g' "$temp_file" 2>/dev/null

    # API key variations
    sed -i.bak 's/[Aa][Pp][Ii][_-]*[Kk][Ee][Yy][[:space:]]*=[[:space:]]*[^[:space:]]*/apikey=***MASKED***/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/[Aa][Pp][Ii][_-]*[Kk][Ee][Yy][[:space:]]*:[[:space:]]*[^[:space:]]*/apikey: ***MASKED***/g' "$temp_file" 2>/dev/null

    # Auth variations
    sed -i.bak 's/[Aa][Uu][Tt][Hh][[:space:]]*=[[:space:]]*[^[:space:]]*/auth=***MASKED***/g' "$temp_file" 2>/dev/null

    # JSON format: "key": "value"
    sed -i.bak 's/"[Pp]assword"[[:space:]]*:[[:space:]]*"[^"]*"/"password": "***MASKED***"/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/"[Tt]oken"[[:space:]]*:[[:space:]]*"[^"]*"/"token": "***MASKED***"/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/"[Ss]ecret"[[:space:]]*:[[:space:]]*"[^"]*"/"secret": "***MASKED***"/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/"[Uu]sername"[[:space:]]*:[[:space:]]*"[^"]*"/"username": "***USER_MASKED***"/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/"[Uu]ser"[[:space:]]*:[[:space:]]*"[^"]*"/"user": "***USER_MASKED***"/g' "$temp_file" 2>/dev/null
    sed -i.bak 's/"[Aa]pi[_-]*[Kk]ey"[[:space:]]*:[[:space:]]*"[^"]*"/"apikey": "***MASKED***"/g' "$temp_file" 2>/dev/null

    # URL-embedded credentials (https://user:pass@host)
    sed -i.bak 's|://[^/:@]*:[^/@]*@|://***:***@|g' "$temp_file" 2>/dev/null

    # Bearer tokens
    sed -i.bak 's/[Bb]earer[[:space:]][^[:space:]]*/Bearer ***MASKED***/g' "$temp_file" 2>/dev/null

    # Authorization headers
    sed -i.bak 's/[Aa]uthorization[[:space:]]*:[[:space:]]*[^[:space:]]*/Authorization: ***MASKED***/g' "$temp_file" 2>/dev/null

    # JWT tokens (eyJ...base64.base64.base64)
    sed -i.bak 's/eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*/***JWT_MASKED***/g' "$temp_file" 2>/dev/null

    # X-XSRF-Token and similar headers
    sed -i.bak 's/[Xx]-[Xx][Ss][Rr][Ff]-[Tt]oken[[:space:]]*:[[:space:]]*[^[:space:]]*/X-XSRF-Token: ***MASKED***/g' "$temp_file" 2>/dev/null

    # JSESSIONID cookies
    sed -i.bak 's/JSESSIONID[[:space:]]*=[[:space:]]*[^[:space:];]*/JSESSIONID=***MASKED***/g' "$temp_file" 2>/dev/null

    # Move masked file back and cleanup
    mv "$temp_file" "$file"
    rm -f "${temp_file}.bak" "${file}.bak" 2>/dev/null
}

# Function to safely collect command output
collect() {
    local name="$1"
    local cmd="$2"
    local output_file="$DIAG_DIR/${name}.txt"

    log "  Collecting: $name"

    {
        echo "=== $name ==="
        echo "Timestamp: $(date)"
        echo "Command: $cmd"
        echo "OS: $OS_TYPE"
        echo ""
        eval "$cmd" 2>&1 || echo "COMMAND FAILED WITH EXIT CODE: $?"
    } > "$output_file"

    # Apply comprehensive credential masking
    mask_credentials_in_file "$output_file"
}

###############################################################################
# HEADER
###############################################################################

log ""
log "${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
log "${CYAN}║        NAC-Test Diagnostic Collection v5.0                       ║${NC}"
log "${CYAN}║              Architecture-Agnostic Edition                        ║${NC}"
log "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
log ""
log "${GREEN}=== NAC-Test Diagnostic Collection v5.0 ===${NC}"
log "Timestamp: $(date)"
log "Platform: ${CYAN}$OS_PRETTY_NAME${NC}"
log "Architecture: ${CYAN}$DETECTED_ARCH${NC}"
log ""
log "Output directory: ${YELLOW}$OUTPUT_DIR${NC}"
log "nac-test command: ${YELLOW}$NAC_TEST_COMMAND${NC}"
log ""

###############################################################################
# VERIFY ENVIRONMENT
###############################################################################

log "${BLUE}=== Verifying Environment ===${NC}"

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    log "${YELLOW}WARNING: No virtual environment detected (VIRTUAL_ENV not set)${NC}"
    log "${YELLOW}         Make sure you activated your venv before running this script${NC}"
else
    log "  Virtual environment: ${GREEN}$VIRTUAL_ENV${NC}"
fi

# Check if nac-test is available
if ! command -v nac-test &> /dev/null; then
    log "${RED}ERROR: nac-test command not found${NC}"
    log "${RED}       Make sure your virtual environment is activated${NC}"
    exit 1
fi

log "  nac-test found: ${GREEN}$(which nac-test)${NC}"

###############################################################################
# COLLECT ENVIRONMENT VARIABLE STATUS (NOT VALUES)
###############################################################################

log ""
log "${BLUE}=== Environment Variable Status ===${NC}"

collect "010_env_var_status" "
echo '=== NaC Environment Variables (values masked) ==='
echo ''

echo '--- Controller URLs ---'
[ -n \"\$APIC_URL\" ] && echo 'APIC_URL=*** SET ***' || echo 'APIC_URL=(not set)'
[ -n \"\$ACI_URL\" ] && echo 'ACI_URL=*** SET ***' || echo 'ACI_URL=(not set)'
[ -n \"\$SDWAN_URL\" ] && echo 'SDWAN_URL=*** SET ***' || echo 'SDWAN_URL=(not set)'
[ -n \"\$CC_URL\" ] && echo 'CC_URL=*** SET ***' || echo 'CC_URL=(not set)'
[ -n \"\$ISE_URL\" ] && echo 'ISE_URL=*** SET ***' || echo 'ISE_URL=(not set)'
[ -n \"\$FMC_URL\" ] && echo 'FMC_URL=*** SET ***' || echo 'FMC_URL=(not set)'
[ -n \"\$NDO_URL\" ] && echo 'NDO_URL=*** SET ***' || echo 'NDO_URL=(not set)'
[ -n \"\$NDFC_URL\" ] && echo 'NDFC_URL=*** SET ***' || echo 'NDFC_URL=(not set)'
echo ''

echo '--- Controller Credentials ---'
[ -n \"\$APIC_USERNAME\" ] && echo 'APIC_USERNAME=*** SET ***' || echo 'APIC_USERNAME=(not set)'
[ -n \"\$APIC_PASSWORD\" ] && echo 'APIC_PASSWORD=*** SET ('\${#APIC_PASSWORD}' chars) ***' || echo 'APIC_PASSWORD=(not set)'
[ -n \"\$ACI_USERNAME\" ] && echo 'ACI_USERNAME=*** SET ***' || echo 'ACI_USERNAME=(not set)'
[ -n \"\$ACI_PASSWORD\" ] && echo 'ACI_PASSWORD=*** SET ('\${#ACI_PASSWORD}' chars) ***' || echo 'ACI_PASSWORD=(not set)'
[ -n \"\$SDWAN_USERNAME\" ] && echo 'SDWAN_USERNAME=*** SET ***' || echo 'SDWAN_USERNAME=(not set)'
[ -n \"\$SDWAN_PASSWORD\" ] && echo 'SDWAN_PASSWORD=*** SET ('\${#SDWAN_PASSWORD}' chars) ***' || echo 'SDWAN_PASSWORD=(not set)'
[ -n \"\$CC_USERNAME\" ] && echo 'CC_USERNAME=*** SET ***' || echo 'CC_USERNAME=(not set)'
[ -n \"\$CC_PASSWORD\" ] && echo 'CC_PASSWORD=*** SET ('\${#CC_PASSWORD}' chars) ***' || echo 'CC_PASSWORD=(not set)'
[ -n \"\$ISE_USERNAME\" ] && echo 'ISE_USERNAME=*** SET ***' || echo 'ISE_USERNAME=(not set)'
[ -n \"\$ISE_PASSWORD\" ] && echo 'ISE_PASSWORD=*** SET ('\${#ISE_PASSWORD}' chars) ***' || echo 'ISE_PASSWORD=(not set)'
echo ''

echo '--- Device Credentials (D2D) ---'
[ -n \"\$IOSXE_USERNAME\" ] && echo 'IOSXE_USERNAME=*** SET ***' || echo 'IOSXE_USERNAME=(not set)'
[ -n \"\$IOSXE_PASSWORD\" ] && echo 'IOSXE_PASSWORD=*** SET ('\${#IOSXE_PASSWORD}' chars) ***' || echo 'IOSXE_PASSWORD=(not set)'
echo ''

echo '--- API Keys ---'
[ -n \"\$MERAKI_API_KEY\" ] && echo 'MERAKI_API_KEY=*** SET ('\${#MERAKI_API_KEY}' chars) ***' || echo 'MERAKI_API_KEY=(not set)'
echo ''

echo '--- Insecure/SSL Settings ---'
[ -n \"\$APIC_INSECURE\" ] && echo \"APIC_INSECURE=\$APIC_INSECURE\" || echo 'APIC_INSECURE=(not set)'
[ -n \"\$CC_INSECURE\" ] && echo \"CC_INSECURE=\$CC_INSECURE\" || echo 'CC_INSECURE=(not set)'
echo ''

echo '--- NAC Test Configuration ---'
[ -n \"\$NAC_TEST_DEBUG\" ] && echo \"NAC_TEST_DEBUG=\$NAC_TEST_DEBUG\" || echo 'NAC_TEST_DEBUG=(not set)'
[ -n \"\$NAC_API_CONCURRENCY\" ] && echo \"NAC_API_CONCURRENCY=\$NAC_API_CONCURRENCY\" || echo 'NAC_API_CONCURRENCY=(not set)'
[ -n \"\$NAC_SSH_CONCURRENCY\" ] && echo \"NAC_SSH_CONCURRENCY=\$NAC_SSH_CONCURRENCY\" || echo 'NAC_SSH_CONCURRENCY=(not set)'
[ -n \"\$NAC_TEST_PROCESSES\" ] && echo \"NAC_TEST_PROCESSES=\$NAC_TEST_PROCESSES\" || echo 'NAC_TEST_PROCESSES=(not set)'
"

###############################################################################
# SYSTEM INFORMATION
###############################################################################

log ""
log "${BLUE}=== Collecting System Information ===${NC}"

collect "020_system_info" "
echo 'OS Type: $OS_TYPE'
echo 'OS Name: $OS_PRETTY_NAME'
uname -a
"

if $IS_MACOS; then
    collect "021_macos_details" "
sw_vers
echo ''
echo 'Architecture:'
arch
uname -m
echo ''
echo 'Hardware:'
sysctl -n machdep.cpu.brand_string 2>/dev/null || echo 'CPU info unavailable'
sysctl -n hw.memsize 2>/dev/null | awk '{print \"Memory: \" \$1/1024/1024/1024 \" GB\"}' || echo 'Memory info unavailable'
"
else
    collect "021_linux_details" "
cat /etc/os-release 2>/dev/null || echo 'OS release info unavailable'
echo ''
echo 'Hardware:'
grep 'model name' /proc/cpuinfo 2>/dev/null | head -1 || echo 'CPU info unavailable'
free -h 2>/dev/null || echo 'Memory info unavailable'
"
fi

###############################################################################
# PYTHON ENVIRONMENT
###############################################################################

log ""
log "${BLUE}=== Collecting Python Environment ===${NC}"

collect "030_python_version" "python --version 2>&1 && python3 --version 2>&1"

collect "031_python_path" "
which python
which python3
echo ''
echo 'VIRTUAL_ENV: $VIRTUAL_ENV'
echo 'Python executable: $(python -c \"import sys; print(sys.executable)\")'
"

collect "032_pip_packages" "
echo '=== All installed packages ==='
pip freeze 2>/dev/null || uv pip freeze 2>/dev/null || echo 'Cannot list packages'
"

collect "033_nac_packages" "
echo '=== NaC-related packages ==='
(pip freeze 2>/dev/null || uv pip freeze 2>/dev/null) | grep -iE '^nac-|^pyats|^unicon|^genie' || echo 'No NaC packages found'
"

collect "034_pyats_version" "
python -c 'import pyats; print(f\"PyATS version: {pyats.__version__}\")' 2>&1 || echo 'PyATS not installed or import failed'
"

###############################################################################
# MULTIPROCESSING CONFIGURATION
###############################################################################

log ""
log "${BLUE}=== Collecting Multiprocessing Configuration ===${NC}"

collect "040_mp_start_method" "
python << 'PYEOF'
import multiprocessing
import sys
import platform

print(f'Python version: {sys.version}')
print(f'Platform: {platform.platform()}')
print(f'Default start method: {multiprocessing.get_start_method()}')
print(f'Available methods: {multiprocessing.get_all_start_methods()}')

# Check for fork safety on macOS
if sys.platform == 'darwin':
    import os
    fork_safety = os.environ.get('OBJC_DISABLE_INITIALIZE_FORK_SAFETY', 'NOT SET')
    print(f'OBJC_DISABLE_INITIALIZE_FORK_SAFETY: {fork_safety}')
PYEOF
"

###############################################################################
# PYATS CONFIGURATION
###############################################################################

log ""
log "${BLUE}=== Collecting PyATS Configuration ===${NC}"

collect "050_pyats_config" "
echo '=== PyATS Configuration Files ==='
echo ''
echo '--- ~/.pyats/pyats.conf ---'
if [ -f ~/.pyats/pyats.conf ]; then
    cat ~/.pyats/pyats.conf
else
    echo '(file does not exist)'
fi
echo ''
echo '--- PYATS_CONFIGURATION env var ---'
echo \"PYATS_CONFIGURATION=\${PYATS_CONFIGURATION:-'(not set)'}\"
"

###############################################################################
# SSL AND NETWORK CONFIGURATION
###############################################################################

log ""
log "${BLUE}=== Collecting Network Configuration ===${NC}"

collect "060_ssl_certs" "
python -c '
import ssl
import certifi
print(f\"Default CA file: {ssl.get_default_verify_paths().cafile}\")
print(f\"Default CA path: {ssl.get_default_verify_paths().capath}\")
print(f\"Certifi CA: {certifi.where()}\")
'
"

###############################################################################
# CRASH REPORT BASELINE (macOS only)
###############################################################################

if $IS_MACOS; then
    log ""
    log "${BLUE}=== Establishing Crash Report Baseline (macOS) ===${NC}"

    CRASH_BASELINE=$(date +%s)
    CRASH_BASELINE_HUMAN=$(date)

    mkdir -p "$DIAG_DIR/crash_reports_PRE_EXISTING"
    mkdir -p "$DIAG_DIR/crash_reports_NEW_DURING_RUN"

    # Copy existing Python crash reports
    find ~/Library/Logs/DiagnosticReports -name "python*" -newer /tmp 2>/dev/null | head -20 | while read f; do
        cp "$f" "$DIAG_DIR/crash_reports_PRE_EXISTING/" 2>/dev/null
    done

    PRE_CRASH_COUNT=$(ls "$DIAG_DIR/crash_reports_PRE_EXISTING/" 2>/dev/null | wc -l | tr -d ' ')
    log "  Found $PRE_CRASH_COUNT pre-existing Python crash reports"
fi

###############################################################################
# EXECUTE NAC-TEST COMMAND
###############################################################################

log ""
log "${YELLOW}╔══════════════════════════════════════════════════════════════════╗${NC}"
log "${YELLOW}║              EXECUTING NAC-TEST COMMAND                          ║${NC}"
log "${YELLOW}╚══════════════════════════════════════════════════════════════════╝${NC}"
log ""
log "Command: ${CYAN}$NAC_TEST_COMMAND${NC}"
log "Output directory: ${CYAN}$OUTPUT_DIR${NC}"
log ""

# Set debug environment variables for better diagnostics
export NAC_TEST_DEBUG=true
export PYTHONFAULTHANDLER=1
export PYTHONDEVMODE=1

if $IS_MACOS; then
    export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
fi

# Record start time
NAC_TEST_START=$(date +%s)

# Execute the user's nac-test command
log "${YELLOW}Starting nac-test execution...${NC}"
log ""

{
    echo "=== nac-test execution ==="
    echo "Timestamp: $(date)"
    echo "Command: $NAC_TEST_COMMAND"
    echo "Working directory: $(pwd)"
    echo ""
    echo "=== Environment (debug flags) ==="
    echo "NAC_TEST_DEBUG=$NAC_TEST_DEBUG"
    echo "PYTHONFAULTHANDLER=$PYTHONFAULTHANDLER"
    echo "PYTHONDEVMODE=$PYTHONDEVMODE"
    [ -n "$OBJC_DISABLE_INITIALIZE_FORK_SAFETY" ] && echo "OBJC_DISABLE_INITIALIZE_FORK_SAFETY=$OBJC_DISABLE_INITIALIZE_FORK_SAFETY"
    echo ""
    echo "=== Execution Output ==="
    echo ""
    eval "$NAC_TEST_COMMAND" 2>&1
    NAC_TEST_EXIT=$?
    echo ""
    echo "=== Execution Complete ==="
    echo "Exit code: $NAC_TEST_EXIT"
} > "$DIAG_DIR/100_nac_test_execution.txt" 2>&1

NAC_TEST_EXIT=${PIPESTATUS[0]}
NAC_TEST_END=$(date +%s)
NAC_TEST_DURATION=$((NAC_TEST_END - NAC_TEST_START))

# Apply credential masking to the execution output
mask_credentials_in_file "$DIAG_DIR/100_nac_test_execution.txt"

log ""
log "${GREEN}nac-test execution completed${NC}"
log "  Exit code: $NAC_TEST_EXIT"
log "  Duration: ${NAC_TEST_DURATION}s"

###############################################################################
# COLLECT NEW CRASH REPORTS (macOS only)
###############################################################################

if $IS_MACOS; then
    log ""
    log "${BLUE}=== Collecting New Crash Reports ===${NC}"

    sleep 2  # Give system time to write crash reports

    # Find crash reports created after our baseline
    find ~/Library/Logs/DiagnosticReports -name "python*" -newer "$DIAG_DIR" 2>/dev/null | while read f; do
        cp "$f" "$DIAG_DIR/crash_reports_NEW_DURING_RUN/" 2>/dev/null
    done

    NEW_CRASH_COUNT=$(ls "$DIAG_DIR/crash_reports_NEW_DURING_RUN/" 2>/dev/null | wc -l | tr -d ' ')

    if [ "$NEW_CRASH_COUNT" -gt 0 ]; then
        log "  ${RED}⚠️  $NEW_CRASH_COUNT NEW crash report(s) generated during execution!${NC}"
    else
        log "  ${GREEN}No new crash reports generated${NC}"
    fi
fi

###############################################################################
# COLLECT NAC-TEST OUTPUT
###############################################################################

log ""
log "${BLUE}=== Collecting nac-test Output ===${NC}"

if [ -d "$OUTPUT_DIR" ]; then
    # Copy results.json files
    find "$OUTPUT_DIR" -name "results.json" -exec cp {} "$DIAG_DIR/" \; 2>/dev/null

    # Copy HTML reports (just the summary)
    find "$OUTPUT_DIR" -name "*summary*.html" -exec cp {} "$DIAG_DIR/" \; 2>/dev/null

    # Copy log files
    find "$OUTPUT_DIR" -name "*.log" -exec cp {} "$DIAG_DIR/" \; 2>/dev/null

    # Copy recent archives
    collect "110_pyats_archives" "
echo 'Recent PyATS archives:'
find '$OUTPUT_DIR' -name '*.zip' -mmin -60 2>/dev/null | head -20
echo ''
echo '⚠️  WARNING: PyATS archives (.zip files) contain raw execution logs that'
echo '   MAY INCLUDE CREDENTIALS if verbose/debug logging was enabled.'
echo '   These archives are included for diagnostic completeness, but please'
echo '   review them before sharing if you have concerns about credential exposure.'
"

    ARCHIVE_COUNT=0
    for archive in $(find "$OUTPUT_DIR" -name '*.zip' -mmin -60 2>/dev/null | head -5); do
        cp "$archive" "$DIAG_DIR/" 2>/dev/null && ARCHIVE_COUNT=$((ARCHIVE_COUNT + 1))
    done
    log "  Copied $ARCHIVE_COUNT recent PyATS archives"
    if [ "$ARCHIVE_COUNT" -gt 0 ]; then
        log "  ${YELLOW}⚠️  WARNING: Archives may contain logs with credentials - review before sharing${NC}"
    fi
else
    log "  ${YELLOW}Output directory not found: $OUTPUT_DIR${NC}"
fi

###############################################################################
# CREATE SUMMARY
###############################################################################

log ""
log "${BLUE}=== Creating Summary ===${NC}"

FILE_COUNT=$(find "$DIAG_DIR" -type f | wc -l)

{
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║           NAC-TEST DIAGNOSTIC SUMMARY v5.0                       ║"
    echo "║              Architecture-Agnostic Edition                        ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Collection timestamp: $(date)"
    echo "Script version: 5.0"
    echo ""
    echo "DETECTED ARCHITECTURE: $DETECTED_ARCH"
    echo ""
    echo "PLATFORM:"
    echo "  OS Type: $OS_TYPE"
    echo "  OS Name: $OS_PRETTY_NAME"
    echo ""
    echo "PYTHON:"
    echo "  Version: $(python --version 2>&1)"
    echo "  Executable: $(which python)"
    echo "  VIRTUAL_ENV: $VIRTUAL_ENV"
    echo ""
    echo "NAC-TEST COMMAND:"
    echo "  $NAC_TEST_COMMAND"
    echo ""
    echo "NAC-TEST EXECUTION:"
    echo "  Exit code: $NAC_TEST_EXIT"
    echo "  Duration: ${NAC_TEST_DURATION}s"
    echo ""
    echo "OUTPUT DIRECTORY: $OUTPUT_DIR"
    echo ""
    echo "FILES COLLECTED: $FILE_COUNT"
    echo ""
    if $IS_MACOS; then
        echo "CRASH REPORTS:"
        PRE_COUNT=$(ls "$DIAG_DIR/crash_reports_PRE_EXISTING/" 2>/dev/null | wc -l | tr -d ' ')
        NEW_COUNT=$(ls "$DIAG_DIR/crash_reports_NEW_DURING_RUN/" 2>/dev/null | wc -l | tr -d ' ')
        echo "  Pre-existing (before nac-test): $PRE_COUNT"
        echo "  New (during nac-test run):      $NEW_COUNT"
        if [ "$NEW_COUNT" -gt 0 ]; then
            echo "  >>> CRASHES OCCURRED DURING EXECUTION <<<"
        fi
        echo ""
    fi
    echo "══════════════════════════════════════════════════════════════════"
    echo "                    CREDENTIAL MASKING NOTICE"
    echo "══════════════════════════════════════════════════════════════════"
    echo ""
    echo "The following credential patterns have been masked in text/JSON/log files:"
    echo "  - Passwords (password, passwd) in key=value, key: value, JSON formats"
    echo "  - Usernames (username, user) in key=value, key: value, JSON formats"
    echo "  - Tokens (token, bearer, JWT)"
    echo "  - Secrets, API keys, Authorization headers"
    echo "  - URL-embedded credentials (https://user:pass@host)"
    echo "  - JSESSIONID cookies and X-XSRF-Token headers"
    echo ""
    echo "⚠️  WARNING: PyATS archive files (.zip) contain raw execution logs"
    echo "   that MAY INCLUDE CREDENTIALS if debug logging was enabled."
    echo "   These archives are included for diagnostic completeness."
    echo "   Please review archive contents before sharing if concerned."
    echo ""
} > "$DIAG_DIR/000_SUMMARY.txt"

###############################################################################
# FINAL CREDENTIAL MASKING PASS
###############################################################################

log "  Performing final credential masking..."
find "$DIAG_DIR" -name "*.txt" -type f 2>/dev/null | while read f; do
    mask_credentials_in_file "$f"
done

find "$DIAG_DIR" -name "*.json" -type f 2>/dev/null | while read f; do
    mask_credentials_in_file "$f"
done

find "$DIAG_DIR" -name "*.log" -type f 2>/dev/null | while read f; do
    mask_credentials_in_file "$f"
done

###############################################################################
# CREATE ZIP ARCHIVE
###############################################################################

ZIP_NAME="${DIAG_DIR}.zip"
log ""
log "Creating archive: $ZIP_NAME"
zip -r "$ZIP_NAME" "$DIAG_DIR" > /dev/null

log ""
log "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
log "${GREEN}║              DIAGNOSTIC COLLECTION COMPLETE                       ║${NC}"
log "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
log ""
log "Archive: ${GREEN}$ZIP_NAME${NC}"
log "Size: $(ls -lh "$ZIP_NAME" | awk '{print $5}')"
log "Files: $FILE_COUNT"
log ""
log "Platform: ${CYAN}$OS_PRETTY_NAME${NC}"
log "Architecture: ${CYAN}$DETECTED_ARCH${NC}"
log ""

if $IS_MACOS; then
    PRE_COUNT=$(ls "$DIAG_DIR/crash_reports_PRE_EXISTING/" 2>/dev/null | wc -l | tr -d ' ')
    NEW_COUNT=$(ls "$DIAG_DIR/crash_reports_NEW_DURING_RUN/" 2>/dev/null | wc -l | tr -d ' ')
    log "Crash Reports:"
    log "  - Pre-existing (before run): ${PRE_COUNT} files"
    log "  - New (during nac-test run): ${NEW_COUNT} files"
    if [ "$NEW_COUNT" -gt 0 ]; then
        log ""
        log "${RED}⚠️  NEW CRASH REPORTS DETECTED!${NC}"
        log "${RED}   Check crash_reports_NEW_DURING_RUN/ for details${NC}"
    fi
    log ""
fi

log "${YELLOW}Please send the file '$ZIP_NAME' for analysis.${NC}"
log "${YELLOW}NOTE: Credentials have been masked in all text, JSON, and log files.${NC}"
log ""
log "${RED}⚠️  IMPORTANT: PyATS archive files (.zip) contain raw execution logs${NC}"
log "${RED}   that MAY INCLUDE CREDENTIALS if debug logging was enabled.${NC}"
log "${RED}   Please review archive contents before sharing if concerned.${NC}"
log ""
