#!/bin/bash
###############################################################################
# NAC-Test Diagnostic Collection Script v4.1
# CROSS-PLATFORM edition for macOS and Linux troubleshooting
#
# This script will:
# 1. Detect your operating system (macOS or Linux)
# 2. Activate your virtual environment
# 3. Set environment variables (EDIT THE VALUES BELOW!)
# 4. Run comprehensive platform-specific diagnostics
# 5. Actually execute nac-test and capture all output
# 6. Collect crash reports, system logs, and debug info
# 7. Zip everything for analysis (credentials are masked)
#
# Usage:
#   1. Edit the configuration section below
#   2. Run: bash nac-test-diagnostic.sh
#   3. Send the resulting .zip file
#
# Supported Platforms:
#   - macOS (Darwin) - Intel and Apple Silicon
#   - Linux (Ubuntu, RHEL, CentOS, Debian, etc.)
###############################################################################

###############################################################################
# ██████╗ ██████╗ ███╗   ██╗███████╗██╗ ██████╗ ██╗   ██╗██████╗  █████╗ ████████╗██╗ ██████╗ ███╗   ██╗
#██╔════╝██╔═══██╗████╗  ██║██╔════╝██║██╔════╝ ██║   ██║██╔══██╗██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║
#██║     ██║   ██║██╔██╗ ██║█████╗  ██║██║  ███╗██║   ██║██████╔╝███████║   ██║   ██║██║   ██║██╔██╗ ██║
#██║     ██║   ██║██║╚██╗██║██╔══╝  ██║██║   ██║██║   ██║██╔══██╗██╔══██║   ██║   ██║██║   ██║██║╚██╗██║
#╚██████╗╚██████╔╝██║ ╚████║██║     ██║╚██████╔╝╚██████╔╝██║  ██║██║  ██║   ██║   ██║╚██████╔╝██║ ╚████║
# ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝     ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
#
# !!!! EDIT THESE VALUES BEFORE RUNNING !!!!
###############################################################################

# Path to your virtual environment (the directory containing bin/activate)
VENV_PATH=".venv"

# SD-WAN Manager credentials
SDWAN_URL="https://YOUR-SDWAN-MANAGER-IP-OR-HOSTNAME"
SDWAN_USERNAME="admin"
SDWAN_PASSWORD="YOUR-PASSWORD-HERE"

# IOS-XE Device credentials (for D2D tests)
IOSXE_USERNAME="admin"
IOSXE_PASSWORD="YOUR-DEVICE-PASSWORD-HERE"

# Path to your data directory (NAC YAML files)
DATA_DIR="./data"

# Path to your tests directory
TESTS_DIR="./tests"

# Output directory for nac-test results
OUTPUT_DIR="./nac-test-results"

###############################################################################
# END OF CONFIGURATION - DO NOT EDIT BELOW THIS LINE
###############################################################################

set -o pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Detect OS
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

DIAG_DIR="nac-test-diagnostics-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$DIAG_DIR"

# Master log file - captures EVERYTHING
MASTER_LOG="$DIAG_DIR/MASTER_LOG.txt"

# Function to log to both console and master log
log() {
    echo -e "$1" | tee -a "$MASTER_LOG"
}

# Comprehensive credential masking function
# This function applies all credential masking patterns to a file
mask_credentials_in_file() {
    local file="$1"

    if [ ! -f "$file" ]; then
        return
    fi

    # Create a temporary file for sed operations
    local temp_file="${file}.masking"
    cp "$file" "$temp_file"

    # First pass: Mask known credential variables (exact matches)
    if [ -n "$SDWAN_PASSWORD" ]; then
        sed -i.bak "s|$SDWAN_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    fi
    if [ -n "$IOSXE_PASSWORD" ]; then
        sed -i.bak "s|$IOSXE_PASSWORD|***MASKED***|g" "$temp_file" 2>/dev/null
    fi
    if [ -n "$SDWAN_USERNAME" ]; then
        sed -i.bak "s|$SDWAN_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null
    fi
    if [ -n "$IOSXE_USERNAME" ]; then
        sed -i.bak "s|$IOSXE_USERNAME|***USER_MASKED***|g" "$temp_file" 2>/dev/null
    fi

    # Second pass: Pattern-based masking (case-insensitive where possible)
    # Note: macOS sed doesn't support -i without extension, so we use .bak

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

    # Token variations - key=value and key: value
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

# Function to safely collect command output (masks sensitive data)
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

# Start master logging
exec > >(tee -a "$MASTER_LOG") 2>&1

log "${BLUE}=== NAC-Test Diagnostic Collection v4.1 ===${NC}"
log "${CYAN}Cross-Platform Edition (macOS + Linux)${NC}"
log "Started at: $(date)"
log "Output directory: $DIAG_DIR"
log ""
log "Detected OS: ${GREEN}$OS_PRETTY_NAME${NC}"
log "OS Type: $OS_TYPE"
if $IS_LINUX; then
    log "Distribution: $OS_RELEASE"
fi
log ""

###############################################################################
# STEP 1: ACTIVATE VIRTUAL ENVIRONMENT
###############################################################################
log "${YELLOW}>>> STEP 1: Activating Virtual Environment <<<${NC}"

if [ -f "$VENV_PATH/bin/activate" ]; then
    log "Found venv at: $VENV_PATH"
    source "$VENV_PATH/bin/activate"
    log "Activated venv. Python is now: $(which python)"
    log "VIRTUAL_ENV=$VIRTUAL_ENV"
else
    log "${RED}ERROR: Virtual environment not found at $VENV_PATH${NC}"
    log "Please edit VENV_PATH in this script"
    log "Looking for venv in common locations..."

    for try_path in ".venv" "venv" "../.venv" "../venv"; do
        if [ -f "$try_path/bin/activate" ]; then
            log "Found venv at: $try_path"
            VENV_PATH="$try_path"
            source "$VENV_PATH/bin/activate"
            log "Activated venv. Python is now: $(which python)"
            break
        fi
    done

    if [ -z "$VIRTUAL_ENV" ]; then
        log "${RED}FATAL: Could not find virtual environment${NC}"
        log "Please set VENV_PATH correctly and re-run"
        exit 1
    fi
fi

###############################################################################
# STEP 2: SET ENVIRONMENT VARIABLES
###############################################################################
log ""
log "${YELLOW}>>> STEP 2: Setting Environment Variables <<<${NC}"

# Export credentials (these get masked in output files)
export SDWAN_URL
export SDWAN_USERNAME
export SDWAN_PASSWORD
export IOSXE_USERNAME
export IOSXE_PASSWORD

# NAC-TEST specific debug flags (from nac_test/core/constants.py)
export NAC_TEST_DEBUG=true
export NAC_API_CONCURRENCY=5
export NAC_SSH_CONCURRENCY=5

# Python debug flags
export PYTHONFAULTHANDLER=1
export PYTHONUNBUFFERED=1
export PYTHONASYNCIODEBUG=1
export PYTHONDEVMODE=1
export PYTHONTRACEMALLOC=1

# macOS-specific: Disable fork safety check (prevents SSL crashes after fork)
if $IS_MACOS; then
    export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
fi

# PyATS/Unicon debug levels
export PYATS_LOG_LEVEL=DEBUG
export UNICON_LOG_LEVEL=DEBUG
export GENIE_LOG_LEVEL=DEBUG

# SSL configuration
if [ -f "$VIRTUAL_ENV/lib/python3.12/site-packages/certifi/cacert.pem" ]; then
    export SSL_CERT_FILE="$VIRTUAL_ENV/lib/python3.12/site-packages/certifi/cacert.pem"
elif [ -f "$VIRTUAL_ENV/lib/python3.11/site-packages/certifi/cacert.pem" ]; then
    export SSL_CERT_FILE="$VIRTUAL_ENV/lib/python3.11/site-packages/certifi/cacert.pem"
elif [ -f "$VIRTUAL_ENV/lib/python3.10/site-packages/certifi/cacert.pem" ]; then
    export SSL_CERT_FILE="$VIRTUAL_ENV/lib/python3.10/site-packages/certifi/cacert.pem"
fi

# Linux-specific environment
if $IS_LINUX; then
    # Ensure proper locale
    export LC_ALL=C.UTF-8
    export LANG=C.UTF-8
fi

log "Environment variables set:"
log "  SDWAN_URL=$SDWAN_URL"
log "  SDWAN_USERNAME=$SDWAN_USERNAME"
log "  SDWAN_PASSWORD=****** (length=${#SDWAN_PASSWORD})"
log "  IOSXE_USERNAME=$IOSXE_USERNAME"
log "  IOSXE_PASSWORD=****** (length=${#IOSXE_PASSWORD})"
log ""
log "  NAC-TEST Debug:"
log "    NAC_TEST_DEBUG=$NAC_TEST_DEBUG"
log "    NAC_API_CONCURRENCY=$NAC_API_CONCURRENCY"
log "    NAC_SSH_CONCURRENCY=$NAC_SSH_CONCURRENCY"
log ""
log "  Python Debug:"
log "    PYTHONFAULTHANDLER=$PYTHONFAULTHANDLER"
log "    PYTHONUNBUFFERED=$PYTHONUNBUFFERED"
log "    PYTHONASYNCIODEBUG=$PYTHONASYNCIODEBUG"
log "    PYTHONDEVMODE=$PYTHONDEVMODE"
log "    PYTHONTRACEMALLOC=$PYTHONTRACEMALLOC"
log ""
if $IS_MACOS; then
    log "  macOS Fork Safety:"
    log "    OBJC_DISABLE_INITIALIZE_FORK_SAFETY=$OBJC_DISABLE_INITIALIZE_FORK_SAFETY"
    log ""
fi
log "  PyATS/Unicon/Genie Debug:"
log "    PYATS_LOG_LEVEL=$PYATS_LOG_LEVEL"
log "    UNICON_LOG_LEVEL=$UNICON_LOG_LEVEL"
log "    GENIE_LOG_LEVEL=$GENIE_LOG_LEVEL"
log ""
log "  SSL Configuration:"
log "    SSL_CERT_FILE=$SSL_CERT_FILE"
log ""

###############################################################################
# SECTION 1: SYSTEM INFORMATION (Platform-Specific)
###############################################################################
log "${YELLOW}>>> SECTION 1: System Information <<<${NC}"

if $IS_MACOS; then
    # macOS System Information
    collect "001_os_version" "sw_vers"
    collect "002_uname_full" "uname -a"
    collect "003_hostname" "hostname"
    collect "004_whoami" "whoami && id"
    collect "005_cpu_arch" "arch"
    collect "006_sysctl_cpu" "sysctl -n machdep.cpu.brand_string"
    collect "007_cpu_cores" "sysctl -n hw.ncpu && sysctl -n hw.physicalcpu"
    collect "008_memory" "sysctl -n hw.memsize && vm_stat"
    collect "009_disk_space" "df -h"
    collect "010_system_profiler" "system_profiler SPSoftwareDataType SPHardwareDataType 2>/dev/null | head -50"
    collect "011_rosetta_check" "sysctl -n sysctl.proc_translated 2>/dev/null || echo 'Not running under Rosetta'"
else
    # Linux System Information
    collect "001_os_version" "cat /etc/os-release 2>/dev/null || cat /etc/*-release 2>/dev/null | head -20"
    collect "002_uname_full" "uname -a"
    collect "003_hostname" "hostname && hostname -f 2>/dev/null"
    collect "004_whoami" "whoami && id"
    collect "005_cpu_arch" "uname -m && arch"
    collect "006_cpu_info" "cat /proc/cpuinfo | grep -E 'model name|processor|cores|MHz' | head -20"
    collect "007_cpu_cores" "nproc && lscpu 2>/dev/null | head -20"
    collect "008_memory" "free -h && cat /proc/meminfo | head -20"
    collect "009_disk_space" "df -h"
    collect "010_lsb_release" "lsb_release -a 2>/dev/null || echo 'lsb_release not available'"
    collect "011_kernel_version" "cat /proc/version"
    collect "012_boot_info" "uptime && who -b 2>/dev/null"
fi

###############################################################################
# SECTION 2: SECURITY (Platform-Specific)
###############################################################################
log ""
log "${YELLOW}>>> SECTION 2: Security Configuration <<<${NC}"

if $IS_MACOS; then
    # macOS Security
    collect "020_sip_status" "csrutil status 2>/dev/null || echo 'Cannot check SIP status'"
    collect "021_gatekeeper" "spctl --status 2>/dev/null || echo 'Cannot check Gatekeeper'"
    collect "022_python_quarantine" "xattr -l \$(which python) 2>/dev/null || echo 'No quarantine attributes'"
    collect "023_sitepackages_quarantine" "
if [ -n \"\$VIRTUAL_ENV\" ]; then
    find \"\$VIRTUAL_ENV/lib\" -name '*.so' -exec xattr -l {} \\; 2>/dev/null | head -50
else
    echo 'No VIRTUAL_ENV set'
fi"
    collect "024_python_codesign" "codesign -dvv \$(which python) 2>&1 || echo 'Cannot check code signature'"
    collect "025_tcc_check" "
echo 'TCC Database (privacy permissions):'
ls -la ~/Library/Application\\ Support/com.apple.TCC/ 2>/dev/null || echo 'No TCC database access'
echo ''
echo 'Terminal Full Disk Access can affect crash report collection.'
"
else
    # Linux Security
    collect "020_selinux_status" "
if command -v getenforce &>/dev/null; then
    getenforce
    sestatus 2>/dev/null | head -20
else
    echo 'SELinux not installed'
fi"
    collect "021_apparmor_status" "
if command -v aa-status &>/dev/null; then
    aa-status 2>/dev/null | head -30
elif [ -f /sys/module/apparmor/parameters/enabled ]; then
    cat /sys/module/apparmor/parameters/enabled
else
    echo 'AppArmor not installed/enabled'
fi"
    collect "022_capabilities" "
echo 'Python capabilities:'
getcap \$(which python3) 2>/dev/null || echo 'No special capabilities'
echo ''
echo 'Process capabilities:'
cat /proc/self/status | grep -i cap"
    collect "023_security_limits" "cat /etc/security/limits.conf 2>/dev/null | grep -v '^#' | grep -v '^$' || echo 'Cannot read limits.conf'"
    collect "024_sudo_config" "sudo -l 2>/dev/null | head -20 || echo 'Cannot check sudo config'"
    collect "025_firewall_status" "
if command -v ufw &>/dev/null; then
    ufw status verbose 2>/dev/null || echo 'Cannot check ufw'
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --state 2>/dev/null
    firewall-cmd --list-all 2>/dev/null | head -30
elif command -v iptables &>/dev/null; then
    iptables -L -n 2>/dev/null | head -30 || echo 'Cannot list iptables rules'
else
    echo 'No firewall detected'
fi"
fi

###############################################################################
# SECTION 3: RESOURCE LIMITS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 3: Resource Limits <<<${NC}"

collect "030_ulimit" "ulimit -a"
collect "031_file_descriptors" "
echo 'Current process FD limit:'
ulimit -n
echo ''
echo 'Open files by this shell:'
ls -la /proc/\$\$/fd 2>/dev/null | wc -l || echo 'Cannot count (not Linux or no /proc)'
"

if $IS_MACOS; then
    collect "032_launchctl_limits" "launchctl limit 2>/dev/null || echo 'Cannot get launchctl limits'"
    collect "033_sysctl_limits" "sysctl kern.maxfiles kern.maxfilesperproc kern.maxproc 2>/dev/null"
else
    collect "032_system_limits" "
echo '/proc/sys/fs/file-max:'
cat /proc/sys/fs/file-max 2>/dev/null
echo ''
echo '/proc/sys/fs/file-nr:'
cat /proc/sys/fs/file-nr 2>/dev/null
echo ''
echo '/proc/sys/kernel/pid_max:'
cat /proc/sys/kernel/pid_max 2>/dev/null
echo ''
echo '/proc/sys/kernel/threads-max:'
cat /proc/sys/kernel/threads-max 2>/dev/null"
    collect "033_cgroups" "
echo 'Cgroup v2 check:'
if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
    echo 'Cgroup v2 is enabled'
    cat /sys/fs/cgroup/cgroup.controllers
else
    echo 'Cgroup v1 or not mounted'
fi
echo ''
echo 'Memory cgroup limits:'
cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null || echo 'Cannot read memory cgroup'
echo ''
echo 'CPU cgroup:'
cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null || echo 'Cannot read CPU cgroup'"
    collect "034_systemd_limits" "
if command -v systemctl &>/dev/null; then
    systemctl show --property=DefaultLimitNOFILE --property=DefaultLimitNPROC 2>/dev/null
else
    echo 'systemd not available'
fi"
fi

###############################################################################
# SECTION 4: PYTHON ENVIRONMENT
###############################################################################
log ""
log "${YELLOW}>>> SECTION 4: Python Environment <<<${NC}"

collect "040_python_version" "python --version && python3 --version 2>/dev/null"
collect "041_python_path" "which python && which python3 2>/dev/null"
collect "042_python_prefix" "python -c 'import sys; print(sys.prefix)'"
collect "043_python_executable" "python -c 'import sys; print(sys.executable)'"
collect "044_python_platform" "python -c 'import platform; print(platform.platform()); print(platform.python_implementation()); print(platform.machine())'"
collect "045_sys_path" "python -c 'import sys; print(chr(10).join(sys.path))'"
collect "046_pip_version" "pip --version"
collect "047_pip_freeze" "pip freeze"
collect "048_pip_list" "pip list --format=columns"
collect "049_pip_check" "pip check 2>&1 || echo 'Dependency conflicts detected'"

###############################################################################
# SECTION 5: CRITICAL PACKAGES
###############################################################################
log ""
log "${YELLOW}>>> SECTION 5: Critical Package Verification <<<${NC}"

collect "050_pyats_version" "pip show pyats 2>/dev/null || echo 'pyats NOT INSTALLED'"
collect "051_pyats_contrib" "pip show pyats.contrib 2>/dev/null || echo 'pyats.contrib NOT INSTALLED - THIS MAY CAUSE ISSUES'"
collect "052_genie_version" "pip show genie 2>/dev/null || echo 'genie NOT INSTALLED'"
collect "053_unicon_version" "pip show unicon 2>/dev/null || echo 'unicon NOT INSTALLED'"
collect "054_paramiko_version" "pip show paramiko 2>/dev/null || echo 'paramiko NOT INSTALLED'"
collect "055_httpx_version" "pip show httpx 2>/dev/null || echo 'httpx NOT INSTALLED'"
collect "056_nac_test_version" "pip show nac-test 2>/dev/null || echo 'nac-test NOT INSTALLED'"
collect "057_nac_test_pyats_common" "pip show nac-test-pyats-common 2>/dev/null || echo 'nac-test-pyats-common NOT INSTALLED'"

###############################################################################
# SECTION 6: PYTHON IMPORTS TEST
###############################################################################
log ""
log "${YELLOW}>>> SECTION 6: Python Import Tests <<<${NC}"

collect "060_import_pyats" "python -c 'import pyats; print(f\"pyats: {pyats.__version__}\")' 2>&1"
collect "061_import_genie" "python -c 'import genie; print(f\"genie: {genie.__version__}\")' 2>&1"
collect "062_import_unicon" "python -c 'import unicon; print(f\"unicon: {unicon.__version__}\")' 2>&1"
collect "063_import_pyats_contrib" "python -c 'import pyats.contrib; print(\"pyats.contrib: OK\")' 2>&1 || echo 'FAIL: pyats.contrib import failed'"
collect "064_import_pyats_aetest" "python -c 'from pyats import aetest; print(\"pyats.aetest: OK\")' 2>&1"
collect "065_import_pyats_easypy" "python -c 'from pyats import easypy; print(\"pyats.easypy: OK\")' 2>&1"
collect "066_import_httpx" "python -c 'import httpx; print(f\"httpx: {httpx.__version__}\")' 2>&1"
collect "067_import_asyncio" "python -c 'import asyncio; print(\"asyncio: OK\")' 2>&1"
collect "068_import_multiprocessing" "python -c 'import multiprocessing; print(f\"multiprocessing start method: {multiprocessing.get_start_method()}\")' 2>&1"
collect "069_import_ssl" "python -c 'import ssl; print(f\"SSL version: {ssl.OPENSSL_VERSION}\")' 2>&1"

###############################################################################
# SECTION 7: NAC-TEST SPECIFIC IMPORTS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 7: NAC-Test Import Tests <<<${NC}"

collect "070_import_nac_test" "python -c 'import nac_test; print(\"nac_test: OK\")' 2>&1"
collect "071_import_nac_test_cli" "python -c 'from nac_test import cli; print(\"nac_test.cli: OK\")' 2>&1"
collect "072_import_nac_test_pyats_core" "python -c 'from nac_test import pyats_core; print(\"nac_test.pyats_core: OK\")' 2>&1"
collect "073_import_nac_test_pyats_common" "python -c 'import nac_test_pyats_common; print(\"nac_test_pyats_common: OK\")' 2>&1"
collect "074_import_sdwan_auth" "python -c 'from nac_test_pyats_common.sdwan_manager import SDWANManagerAuth; print(\"SDWANManagerAuth: OK\")' 2>&1"
collect "075_import_auth_cache" "python -c 'from nac_test.pyats_core.common.auth_cache import AuthCache; print(\"AuthCache: OK\")' 2>&1"

###############################################################################
# SECTION 8: SSL/TLS CONFIGURATION
###############################################################################
log ""
log "${YELLOW}>>> SECTION 8: SSL/TLS Configuration <<<${NC}"

collect "080_openssl_version" "openssl version -a 2>/dev/null || echo 'openssl not found'"
collect "081_ssl_cert_locations" "python -c '
import ssl
import certifi
print(f\"Default CA file: {ssl.get_default_verify_paths().cafile}\")
print(f\"Default CA path: {ssl.get_default_verify_paths().capath}\")
print(f\"Certifi CA: {certifi.where()}\")
print(f\"OpenSSL dir: {ssl.get_default_verify_paths().openssl_cafile_env}\")
'"
collect "082_ssl_context_test" "python -c '
import ssl
import socket
ctx = ssl.create_default_context()
print(f\"Protocol: {ctx.protocol}\")
print(f\"Verify mode: {ctx.verify_mode}\")
print(f\"Check hostname: {ctx.check_hostname}\")
print(f\"Options: {ctx.options}\")
'"

if $IS_MACOS; then
    collect "083_keychain_certs" "security find-certificate -a 2>/dev/null | head -50 || echo 'Cannot access keychain'"
else
    collect "083_ca_certificates" "
echo 'CA certificate locations:'
ls -la /etc/ssl/certs/ 2>/dev/null | head -20
echo ''
echo 'CA bundle:'
ls -la /etc/ssl/certs/ca-certificates.crt 2>/dev/null || ls -la /etc/pki/tls/certs/ca-bundle.crt 2>/dev/null || echo 'CA bundle not found in standard locations'"
fi

###############################################################################
# SECTION 9: NETWORK CONFIGURATION
###############################################################################
log ""
log "${YELLOW}>>> SECTION 9: Network Configuration <<<${NC}"

if $IS_MACOS; then
    collect "090_network_interfaces" "ifconfig -a 2>/dev/null | head -50"
    collect "091_dns_config" "scutil --dns 2>/dev/null | head -40"
    collect "092_network_services" "networksetup -listallnetworkservices 2>/dev/null"
    collect "093_proxy_settings" "networksetup -getwebproxy Wi-Fi 2>/dev/null; networksetup -getsecurewebproxy Wi-Fi 2>/dev/null"
    collect "094_routes" "netstat -rn 2>/dev/null | head -30"
else
    collect "090_network_interfaces" "ip addr 2>/dev/null || ifconfig -a 2>/dev/null | head -50"
    collect "091_dns_config" "cat /etc/resolv.conf 2>/dev/null"
    collect "092_network_manager" "
if command -v nmcli &>/dev/null; then
    nmcli general status 2>/dev/null
    nmcli connection show 2>/dev/null | head -20
else
    echo 'NetworkManager not available'
fi"
    collect "093_proxy_settings" "
echo 'HTTP_PROXY:' \$HTTP_PROXY
echo 'HTTPS_PROXY:' \$HTTPS_PROXY
echo 'NO_PROXY:' \$NO_PROXY
echo ''
echo '/etc/environment proxy settings:'
grep -i proxy /etc/environment 2>/dev/null || echo 'No proxy in /etc/environment'"
    collect "094_routes" "ip route 2>/dev/null || netstat -rn 2>/dev/null | head -30"
    collect "095_ss_listening" "ss -tlnp 2>/dev/null | head -30 || netstat -tlnp 2>/dev/null | head -30"
fi

###############################################################################
# SECTION 10: CONNECTIVITY TESTS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 10: Connectivity Tests <<<${NC}"

collect "100_ping_localhost" "ping -c 2 127.0.0.1 2>&1"
collect "101_dns_resolution" "
echo 'Resolving common hosts:'
host google.com 2>/dev/null || nslookup google.com 2>/dev/null || echo 'DNS resolution failed'
"
collect "102_curl_test" "curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://google.com 2>&1 || echo 'curl failed'"

if [ "$SDWAN_URL" != "https://YOUR-SDWAN-MANAGER-IP-OR-HOSTNAME" ]; then
    collect "103_sdwan_connectivity" "
echo 'Testing connectivity to SD-WAN Manager...'
curl -sk -o /dev/null -w 'HTTP Status: %{http_code}\nTime: %{time_total}s\n' --max-time 30 '$SDWAN_URL' 2>&1 || echo 'Cannot reach SD-WAN Manager'
"
else
    collect "103_sdwan_connectivity" "echo 'SDWAN_URL not configured - skipping connectivity test'"
fi

###############################################################################
# SECTION 11: PROCESS AND MEMORY
###############################################################################
log ""
log "${YELLOW}>>> SECTION 11: Process and Memory <<<${NC}"

collect "110_python_processes" "ps aux | grep -i python | grep -v grep"
collect "111_memory_usage" "
if $IS_MACOS; then
    vm_stat
    echo ''
    top -l 1 -n 10 -o MEM 2>/dev/null | head -20
else
    free -h
    echo ''
    cat /proc/meminfo | head -30
fi"
collect "112_top_processes" "
if $IS_MACOS; then
    top -l 1 -n 20 -o cpu 2>/dev/null | tail -25
else
    top -b -n 1 | head -30
fi"

if $IS_LINUX; then
    collect "113_oom_killer" "
echo 'OOM killer settings:'
cat /proc/sys/vm/overcommit_memory 2>/dev/null
cat /proc/sys/vm/overcommit_ratio 2>/dev/null
echo ''
echo 'Recent OOM kills:'
dmesg 2>/dev/null | grep -i 'out of memory' | tail -10 || journalctl -k 2>/dev/null | grep -i 'out of memory' | tail -10 || echo 'Cannot check OOM history'"
fi

###############################################################################
# SECTION 12: ENVIRONMENT VARIABLES
###############################################################################
log ""
log "${YELLOW}>>> SECTION 12: Environment Variables <<<${NC}"

collect "120_all_env_vars" "
env | grep -v -iE 'PASSWORD|PASSWD|SECRET|TOKEN|KEY|CREDENTIAL|AUTH|API.?KEY|USER' | sort
echo ''
echo '(Sensitive variables filtered out - PASSWORD, PASSWD, SECRET, TOKEN, KEY, CREDENTIAL, AUTH, APIKEY, USER)'
"
collect "121_python_env" "env | grep -i python"
collect "122_path" "echo \$PATH | tr ':' '\n'"
collect "123_library_path" "
echo 'LD_LIBRARY_PATH:' \$LD_LIBRARY_PATH
echo 'DYLD_LIBRARY_PATH:' \$DYLD_LIBRARY_PATH
echo 'LIBRARY_PATH:' \$LIBRARY_PATH
"

###############################################################################
# SECTION 13: MULTIPROCESSING DIAGNOSTICS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 13: Multiprocessing Diagnostics <<<${NC}"

collect "130_mp_start_method" "python -c '
import multiprocessing
print(f\"Default start method: {multiprocessing.get_start_method()}\")
print(f\"Available methods: {multiprocessing.get_all_start_methods()}\")
'"

collect "131_mp_context_test" "python -c '
import multiprocessing
import sys

for method in multiprocessing.get_all_start_methods():
    try:
        ctx = multiprocessing.get_context(method)
        print(f\"{method}: Available\")
    except Exception as e:
        print(f\"{method}: {e}\")
'"

collect "132_fork_test" "python -c '
import os
import sys

print(f\"PID: {os.getpid()}\")
print(f\"Platform: {sys.platform}\")

# Test if fork works
if hasattr(os, \"fork\"):
    pid = os.fork()
    if pid == 0:
        print(\"Child process created successfully\")
        os._exit(0)
    else:
        os.waitpid(pid, 0)
        print(\"Fork test passed\")
else:
    print(\"Fork not available on this platform\")
' 2>&1"

###############################################################################
# SECTION 14: PYATS SPECIFIC DIAGNOSTICS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 14: PyATS Diagnostics <<<${NC}"

collect "140_pyats_config" "
if [ -f ~/.pyats/pyats.conf ]; then
    cat ~/.pyats/pyats.conf
else
    echo 'No ~/.pyats/pyats.conf found'
fi"

collect "141_pyats_plugins" "python -c '
try:
    from pyats import configuration
    print(\"PyATS configuration loaded\")
    from pyats.easypy import plugins
    print(\"PyATS plugins available\")
except Exception as e:
    print(f\"Error: {e}\")
' 2>&1"

collect "142_pyats_testbed_schema" "python -c '
try:
    from pyats.topology import loader
    print(\"Testbed loader available\")
except Exception as e:
    print(f\"Error: {e}\")
' 2>&1"

collect "143_pyats_log_config" "python -c '
import logging
from pyats import log
print(f\"PyATS log level: {logging.getLevelName(logging.getLogger().level)}\")
print(f\"Root handlers: {logging.getLogger().handlers}\")
' 2>&1"

###############################################################################
# SECTION 15: DATA AND TEST FILES
###############################################################################
log ""
log "${YELLOW}>>> SECTION 15: Data and Test Files <<<${NC}"

collect "150_data_dir_check" "
echo 'Data directory: $DATA_DIR'
if [ -d '$DATA_DIR' ]; then
    echo 'Contents:'
    ls -la '$DATA_DIR' 2>/dev/null | head -30
    echo ''
    echo 'YAML files:'
    find '$DATA_DIR' -name '*.yaml' -o -name '*.yml' 2>/dev/null | head -20
else
    echo 'DATA DIRECTORY NOT FOUND'
fi"

collect "151_tests_dir_check" "
echo 'Tests directory: $TESTS_DIR'
if [ -d '$TESTS_DIR' ]; then
    echo 'Contents:'
    ls -la '$TESTS_DIR' 2>/dev/null | head -30
    echo ''
    echo 'Test files:'
    find '$TESTS_DIR' -name 'verify_*.py' -o -name 'test_*.py' 2>/dev/null | head -30
else
    echo 'TESTS DIRECTORY NOT FOUND'
fi"

collect "152_cwd_contents" "
echo 'Current working directory:'
pwd
echo ''
ls -la
"

###############################################################################
# SECTION 16: GIT INFORMATION
###############################################################################
log ""
log "${YELLOW}>>> SECTION 16: Git Information <<<${NC}"

collect "160_git_status" "git status 2>/dev/null || echo 'Not a git repository'"
collect "161_git_branch" "git branch -v 2>/dev/null || echo 'Not a git repository'"
collect "162_git_remote" "git remote -v 2>/dev/null || echo 'Not a git repository'"
collect "163_git_log" "git log --oneline -10 2>/dev/null || echo 'Not a git repository'"

###############################################################################
# SECTION 17: LOGGING CONFIGURATION
###############################################################################
log ""
log "${YELLOW}>>> SECTION 17: Logging Configuration <<<${NC}"

collect "170_python_logging" "python -c '
import logging
import sys

root = logging.getLogger()
print(f\"Root logger level: {logging.getLevelName(root.level)}\")
print(f\"Root handlers: {root.handlers}\")
print(f\"Effective level: {logging.getLevelName(root.getEffectiveLevel())}\")
print(f\"Manager disable level: {logging.root.manager.disable}\")

# Check for common loggers
for name in [\"pyats\", \"genie\", \"unicon\", \"nac_test\", \"httpx\", \"asyncio\"]:
    logger = logging.getLogger(name)
    print(f\"{name}: level={logging.getLevelName(logger.level)}, handlers={len(logger.handlers)}, propagate={logger.propagate}\")
'"

###############################################################################
# SECTION 18: CRASH REPORT LOCATIONS (Platform-Specific)
###############################################################################
log ""
log "${YELLOW}>>> SECTION 18: Crash Report Locations <<<${NC}"

if $IS_MACOS; then
    collect "180_crash_locations" "
echo 'macOS Crash Report Directories:'
echo ''
echo '~/Library/Logs/DiagnosticReports/:'
ls -la ~/Library/Logs/DiagnosticReports/ 2>/dev/null | tail -20 || echo 'Not accessible'
echo ''
echo '/Library/Logs/DiagnosticReports/:'
ls -la /Library/Logs/DiagnosticReports/ 2>/dev/null | tail -20 || echo 'Not accessible'
echo ''
echo 'Python-related crash reports:'
ls -la ~/Library/Logs/DiagnosticReports/*[Pp]ython* 2>/dev/null | tail -20 || echo 'No Python crash reports'
"
else
    collect "180_crash_locations" "
echo 'Linux Crash/Core Dump Locations:'
echo ''
echo '/var/crash/:'
ls -la /var/crash/ 2>/dev/null | tail -20 || echo 'Not accessible'
echo ''
echo '/var/log/:'
ls -la /var/log/*.log 2>/dev/null | tail -20 || echo 'Not accessible'
echo ''
echo 'Core dump settings:'
cat /proc/sys/kernel/core_pattern 2>/dev/null || echo 'Cannot read core_pattern'
echo ''
echo 'Coredumpctl (systemd):'
if command -v coredumpctl &>/dev/null; then
    coredumpctl list --no-pager 2>/dev/null | tail -20
else
    echo 'coredumpctl not available'
fi
"
fi

###############################################################################
# SECTION 19: SYSTEM LOGS (Platform-Specific)
###############################################################################
log ""
log "${YELLOW}>>> SECTION 19: System Logs <<<${NC}"

if $IS_MACOS; then
    collect "190_system_log" "log show --predicate 'process contains \"python\"' --last 10m 2>/dev/null | tail -100 || echo 'Cannot access system logs'"
    collect "191_console_errors" "log show --predicate 'eventType == \"logEvent\" AND messageType == \"error\"' --last 10m 2>/dev/null | tail -50 || echo 'Cannot access console logs'"
else
    collect "190_system_log" "
echo 'journalctl (last 10 minutes):'
journalctl --since '10 minutes ago' --no-pager 2>/dev/null | grep -i python | tail -100 || echo 'journalctl not available or no python entries'
echo ''
echo 'syslog:'
tail -100 /var/log/syslog 2>/dev/null | grep -i python || echo 'Cannot read syslog'"
    collect "191_dmesg" "dmesg 2>/dev/null | tail -50 || echo 'Cannot access dmesg'"
    collect "192_auth_log" "tail -50 /var/log/auth.log 2>/dev/null || tail -50 /var/log/secure 2>/dev/null || echo 'Cannot read auth log'"
fi

###############################################################################
# SECTION 20: ASYNC AND THREADING
###############################################################################
log ""
log "${YELLOW}>>> SECTION 20: Async and Threading <<<${NC}"

collect "200_asyncio_test" "python -c '
import asyncio
import sys

async def test():
    print(f\"Event loop: {asyncio.get_event_loop()}\")
    print(f\"Running loop: {asyncio.get_running_loop()}\")
    return \"OK\"

print(f\"Python version: {sys.version}\")
print(f\"asyncio debug: {asyncio.get_event_loop_policy()}\")
result = asyncio.run(test())
print(f\"Async test: {result}\")
' 2>&1"

collect "201_threading_test" "python -c '
import threading
import sys

print(f\"Active threads: {threading.active_count()}\")
print(f\"Current thread: {threading.current_thread()}\")
print(f\"Main thread: {threading.main_thread()}\")
print(f\"Stack size: {threading.stack_size()}\")

# Test thread creation
def worker():
    pass

t = threading.Thread(target=worker)
t.start()
t.join()
print(\"Thread test: OK\")
' 2>&1"

###############################################################################
# SECTION 21: HTTPX AND HTTP CLIENTS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 21: HTTP Client Tests <<<${NC}"

collect "210_httpx_test" "python -c '
import httpx
import asyncio

print(f\"httpx version: {httpx.__version__}\")

# Test sync client
try:
    with httpx.Client(verify=False, timeout=10) as client:
        print(\"Sync client: OK\")
except Exception as e:
    print(f\"Sync client error: {e}\")

# Test async client
async def test_async():
    async with httpx.AsyncClient(verify=False, timeout=10) as client:
        return \"OK\"

try:
    result = asyncio.run(test_async())
    print(f\"Async client: {result}\")
except Exception as e:
    print(f\"Async client error: {e}\")
' 2>&1"

###############################################################################
# SECTION 22: SIGNAL HANDLING
###############################################################################
log ""
log "${YELLOW}>>> SECTION 22: Signal Handling <<<${NC}"

collect "220_signal_handlers" "python -c '
import signal
import sys

print(\"Current signal handlers:\")
for name in dir(signal):
    if name.startswith(\"SIG\") and not name.startswith(\"SIG_\"):
        try:
            signum = getattr(signal, name)
            if isinstance(signum, signal.Signals):
                handler = signal.getsignal(signum)
                print(f\"  {name}: {handler}\")
        except Exception:
            pass
'"

###############################################################################
# SECTION 23: PTH FILES CHECK
###############################################################################
log ""
log "${YELLOW}>>> SECTION 23: PTH Files Check <<<${NC}"

collect "230_pth_files" "
echo 'Checking for .pth files that might affect imports:'
echo ''
find \"\$VIRTUAL_ENV/lib\" -name '*.pth' -exec echo '=== {} ===' \\; -exec cat {} \\; 2>/dev/null || echo 'Cannot scan pth files'
"

###############################################################################
# SECTION 24: NAC-TEST SPECIFIC DIAGNOSTICS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 24: NAC-Test Specific Diagnostics <<<${NC}"

collect "240_nac_test_help" "nac-test --help 2>&1 || echo 'nac-test command not found'"

collect "241_nac_test_version_check" "
echo '=== NAC-Test Version and Entry Points ==='
python -c '
import pkg_resources
try:
    dist = pkg_resources.get_distribution(\"nac-test\")
    print(f\"nac-test version: {dist.version}\")
    print(f\"Location: {dist.location}\")
    print(\"\\nEntry points:\")
    for ep in dist.get_entry_map().get(\"console_scripts\", {}).values():
        print(f\"  {ep.name}: {ep}\")
except Exception as e:
    print(f\"Error: {e}\")
' 2>&1
"

collect "242_auth_cache_check" "
echo '=== AuthCache Diagnostics ==='
python << 'PYEOF'
import os
import tempfile
import glob

# Check for auth cache files
cache_patterns = [
    '/tmp/nac_auth_cache*',
    '/tmp/nac_test_auth*',
    os.path.expanduser('~/.nac_test_cache*'),
    os.path.join(tempfile.gettempdir(), 'nac_*'),
]

print('Looking for auth cache files:')
found = False
for pattern in cache_patterns:
    files = glob.glob(pattern)
    for f in files:
        found = True
        try:
            stat = os.stat(f)
            print(f'  {f}')
            print(f'    Size: {stat.st_size} bytes')
            print(f'    Mode: {oct(stat.st_mode)}')
            print(f'    Modified: {stat.st_mtime}')
        except Exception as e:
            print(f'  {f}: {e}')

if not found:
    print('  No auth cache files found (this is normal for fresh runs)')

# Check for lock files
print('\\nLooking for stale lock files:')
lock_patterns = [
    '/tmp/*.lock',
    '/tmp/nac_*.lock',
    os.path.join(tempfile.gettempdir(), '*.lock'),
]
lock_found = False
for pattern in lock_patterns:
    files = glob.glob(pattern)
    for f in files:
        if 'nac' in f.lower() or 'auth' in f.lower():
            lock_found = True
            print(f'  POTENTIAL STALE LOCK: {f}')

if not lock_found:
    print('  No NAC-related lock files found')
PYEOF
"

collect "243_temp_file_orphans" "
echo '=== Orphaned Temporary Files ==='
echo 'Looking for orphaned PyATS/NAC temp files...'
echo ''
echo '/tmp/tmp*job*.py (PyATS job files):'
ls -la /tmp/tmp*job*.py 2>/dev/null | head -10 || echo '  None found'
echo ''
echo '/tmp/tmp*testbed*.yaml (testbed files):'
ls -la /tmp/tmp*testbed*.yaml 2>/dev/null | head -10 || echo '  None found'
echo ''
echo '/tmp/tmp*config*.yaml (config files):'
ls -la /tmp/tmp*config*.yaml 2>/dev/null | head -10 || echo '  None found'
echo ''
echo '/tmp/tmp*auth*.py (auth scripts):'
ls -la /tmp/tmp*auth*.py 2>/dev/null | head -10 || echo '  None found'
echo ''
echo 'Total temp files from current user:'
ls /tmp/tmp* 2>/dev/null | wc -l | xargs echo '  Count:'
"

collect "244_output_dir_permissions" "
echo '=== Output Directory Permissions ==='
echo \"Checking: $OUTPUT_DIR\"
if [ -d '$OUTPUT_DIR' ]; then
    ls -la '$OUTPUT_DIR'
    echo ''
    echo 'Write test:'
    if touch '$OUTPUT_DIR/.write_test' 2>/dev/null; then
        echo '  Write access: OK'
        rm -f '$OUTPUT_DIR/.write_test'
    else
        echo '  Write access: FAILED'
    fi
else
    echo 'Directory does not exist yet (will be created by nac-test)'
    parent=\$(dirname '$OUTPUT_DIR')
    echo \"Parent directory: \$parent\"
    ls -la \"\$parent\" 2>/dev/null | head -5
fi
"

collect "245_data_model_validation" "
echo '=== Data Model Validation ==='
if [ -d '$DATA_DIR' ]; then
    echo 'Testing YAML parsing of data files...'
    python << PYEOF
import os
import yaml
import sys

data_dir = '$DATA_DIR'
errors = []
success = 0

for root, dirs, files in os.walk(data_dir):
    for f in files:
        if f.endswith(('.yaml', '.yml')):
            path = os.path.join(root, f)
            try:
                with open(path) as fh:
                    yaml.safe_load(fh)
                success += 1
            except Exception as e:
                errors.append((path, str(e)))

print(f'Successfully parsed: {success} files')
if errors:
    print(f'\\nFailed to parse: {len(errors)} files')
    for path, err in errors[:5]:
        print(f'  {path}: {err[:100]}')
else:
    print('No YAML parsing errors')
PYEOF
else
    echo 'DATA_DIR not found: $DATA_DIR'
fi
"

collect "246_test_file_validation" "
echo '=== Test File Validation ==='
if [ -d '$TESTS_DIR' ]; then
    echo 'Checking test file syntax...'
    python << PYEOF
import os
import py_compile
import sys

tests_dir = '$TESTS_DIR'
errors = []
success = 0

for root, dirs, files in os.walk(tests_dir):
    for f in files:
        if f.endswith('.py') and (f.startswith('verify_') or f.startswith('test_')):
            path = os.path.join(root, f)
            try:
                py_compile.compile(path, doraise=True)
                success += 1
            except py_compile.PyCompileError as e:
                errors.append((path, str(e)))

print(f'Syntax OK: {success} test files')
if errors:
    print(f'\\nSyntax errors: {len(errors)} files')
    for path, err in errors[:5]:
        print(f'  {path}')
        print(f'    {err[:200]}')
else:
    print('No syntax errors in test files')
PYEOF
else
    echo 'TESTS_DIR not found: $TESTS_DIR'
fi
"

collect "247_controller_auth_test" "
echo '=== Controller Authentication Test ==='
python << 'PYEOF'
import os
import sys

# Determine controller type based on environment
sdwan_url = os.environ.get('SDWAN_URL', '')
aci_url = os.environ.get('ACI_URL', os.environ.get('APIC_URL', ''))
cc_url = os.environ.get('CC_URL', '')

print('Configured controllers:')
if sdwan_url and 'YOUR' not in sdwan_url:
    print(f'  SD-WAN Manager: {sdwan_url}')
if aci_url:
    print(f'  APIC: {aci_url}')
if cc_url:
    print(f'  Catalyst Center: {cc_url}')

# Test SD-WAN auth if configured
if sdwan_url and 'YOUR' not in sdwan_url:
    print('\\nTesting SD-WAN Manager authentication...')
    try:
        from nac_test_pyats_common.sdwan_manager import SDWANManagerAuth
        auth = SDWANManagerAuth.get_auth()
        print(f'  SUCCESS: Got auth with keys: {list(auth.keys())}')
    except Exception as e:
        print(f'  FAILED: {e}')

# Test APIC auth if configured
if aci_url:
    print('\\nTesting APIC authentication...')
    try:
        from nac_test_pyats_common.apic import APICAuth
        token = APICAuth.get_token()
        print(f'  SUCCESS: Got token (length: {len(token) if token else 0})')
    except Exception as e:
        print(f'  FAILED: {e}')

# Test Catalyst Center auth if configured
if cc_url:
    print('\\nTesting Catalyst Center authentication...')
    try:
        from nac_test_pyats_common.catalyst_center import CatalystCenterAuth
        token = CatalystCenterAuth.get_token()
        print(f'  SUCCESS: Got token (length: {len(token) if token else 0})')
    except Exception as e:
        print(f'  FAILED: {e}')

if not any([sdwan_url and 'YOUR' not in sdwan_url, aci_url, cc_url]):
    print('No controllers configured for authentication test')
PYEOF
"

collect "248_connection_broker_check" "
echo '=== Connection Broker Diagnostics ==='
python << 'PYEOF'
import os
import sys

try:
    from nac_test.pyats_core.broker.connection_broker import ConnectionBroker
    print('ConnectionBroker import: OK')

    # Check if there's a singleton instance
    print(f'ConnectionBroker class available')

    # Check broker configuration
    print('\\nBroker configuration:')
    print(f'  NAC_SSH_CONCURRENCY: {os.environ.get(\"NAC_SSH_CONCURRENCY\", \"not set\")}')
    print(f'  NAC_API_CONCURRENCY: {os.environ.get(\"NAC_API_CONCURRENCY\", \"not set\")}')

except ImportError as e:
    print(f'ConnectionBroker import failed: {e}')
except Exception as e:
    print(f'Error checking ConnectionBroker: {e}')
PYEOF
"

collect "249_pyats_job_generation_test" "
echo '=== PyATS Job Generation Test ==='
python << 'PYEOF'
import tempfile
import os

try:
    from nac_test.pyats_core.job_generator import JobGenerator
    print('JobGenerator import: OK')

    # Test minimal job generation
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        job_content = '''
from pyats.easypy import run
def main(runtime):
    pass
'''
        f.write(job_content)
        temp_job = f.name

    # Verify it's valid Python
    import py_compile
    py_compile.compile(temp_job, doraise=True)
    print('Job file generation: OK')
    os.unlink(temp_job)

except ImportError as e:
    print(f'JobGenerator import failed: {e}')
except Exception as e:
    print(f'Job generation test failed: {e}')
PYEOF
"

###############################################################################
# SECTION 25: PRE-EXECUTION BASELINE
###############################################################################
log ""
log "${YELLOW}>>> SECTION 25: Pre-Execution Baseline <<<${NC}"

# Record EXACT timestamp before running nac-test - this is critical for filtering
CRASH_BASELINE=$(date +%s)
CRASH_BASELINE_HUMAN=$(date)

log "  Recording baseline timestamp: $CRASH_BASELINE_HUMAN"
log "  (Unix timestamp: $CRASH_BASELINE)"

# Create directories for both pre-existing and new crash reports
mkdir -p "$DIAG_DIR/crash_reports_PRE_EXISTING"
mkdir -p "$DIAG_DIR/crash_reports_NEW_DURING_RUN"

# COPY all pre-existing crash reports BEFORE running nac-test
# This gives us a complete "before" snapshot for comparison
PRE_EXISTING_COUNT=0
if $IS_MACOS; then
    if [ -d ~/Library/Logs/DiagnosticReports ]; then
        log "  Copying pre-existing Python crash reports (macOS)..."
        find ~/Library/Logs/DiagnosticReports -type f -name '*[Pp]ython*' 2>/dev/null | while read f; do
            cp "$f" "$DIAG_DIR/crash_reports_PRE_EXISTING/" 2>/dev/null
        done
        PRE_EXISTING_COUNT=$(ls "$DIAG_DIR/crash_reports_PRE_EXISTING/" 2>/dev/null | wc -l | tr -d ' ')
        log "  Copied $PRE_EXISTING_COUNT pre-existing crash report(s)"
    fi
else
    # Linux: Check /var/crash and coredumps
    log "  Checking for pre-existing crash reports (Linux)..."
    if [ -d /var/crash ]; then
        find /var/crash -type f -mtime -7 2>/dev/null | while read f; do
            cp "$f" "$DIAG_DIR/crash_reports_PRE_EXISTING/" 2>/dev/null
        done
    fi
    # Also check coredumpctl if available
    if command -v coredumpctl &>/dev/null; then
        coredumpctl list --no-pager 2>/dev/null > "$DIAG_DIR/crash_reports_PRE_EXISTING/coredumpctl_list.txt"
    fi
    PRE_EXISTING_COUNT=$(ls "$DIAG_DIR/crash_reports_PRE_EXISTING/" 2>/dev/null | wc -l | tr -d ' ')
    log "  Found $PRE_EXISTING_COUNT pre-existing crash item(s)"
fi

collect "250_pre_crash_reports" "
echo '=== BASELINE TIMESTAMP ==='
echo 'Unix timestamp: $CRASH_BASELINE'
echo 'Human readable: $CRASH_BASELINE_HUMAN'
echo ''
echo 'Any crash reports created AFTER this timestamp are from THIS diagnostic run.'
echo 'Crash reports created BEFORE this timestamp are PRE-EXISTING.'
echo ''
echo '=== PRE-EXISTING CRASH REPORTS ==='
echo 'These have been COPIED to: crash_reports_PRE_EXISTING/'
echo 'Total: $PRE_EXISTING_COUNT'
"

# Record system log baseline
if $IS_MACOS; then
    collect "251_pre_system_log" "log show --predicate 'process contains \"python\"' --last 1m 2>/dev/null | tail -20 || echo 'No recent python logs'"
else
    collect "251_pre_system_log" "journalctl --since '1 minute ago' 2>/dev/null | grep -i python | tail -20 || echo 'No recent python logs'"
fi

# Count existing Python processes
collect "252_pre_python_processes" "ps aux | grep -i python | grep -v grep"

###############################################################################
# SECTION 26: ACTUAL NAC-TEST EXECUTION WITH CRASH MONITORING
###############################################################################
log ""
log "${YELLOW}>>> SECTION 26: ACTUAL NAC-TEST EXECUTION <<<${NC}"
log ""
log "${RED}This is the actual nac-test run - may take several minutes${NC}"
log ""

NAC_TEST_LOG="$DIAG_DIR/260_nac_test_execution.txt"

{
    echo "=== NAC-TEST EXECUTION ==="
    echo "Timestamp: $(date)"
    echo "Working directory: $(pwd)"
    echo "OS: $OS_PRETTY_NAME"
    echo ""
    echo "Environment Variables (Debug):"
    echo "  SDWAN_URL=$SDWAN_URL"
    echo "  SDWAN_USERNAME=$SDWAN_USERNAME"
    echo "  DATA_DIR=$DATA_DIR"
    echo "  TESTS_DIR=$TESTS_DIR"
    echo "  OUTPUT_DIR=$OUTPUT_DIR"
    echo ""
    echo "  NAC_TEST_DEBUG=$NAC_TEST_DEBUG"
    echo "  NAC_API_CONCURRENCY=$NAC_API_CONCURRENCY"
    echo "  NAC_SSH_CONCURRENCY=$NAC_SSH_CONCURRENCY"
    echo "  PYTHONFAULTHANDLER=$PYTHONFAULTHANDLER"
    echo "  PYTHONDEVMODE=$PYTHONDEVMODE"
    if $IS_MACOS; then
        echo "  OBJC_DISABLE_INITIALIZE_FORK_SAFETY=$OBJC_DISABLE_INITIALIZE_FORK_SAFETY"
    fi
    echo ""
    echo "Command: nac-test -d $DATA_DIR -t $TESTS_DIR -o $OUTPUT_DIR --pyats"
    echo ""
    echo "=========================================="
    echo "NAC-TEST OUTPUT BEGINS:"
    echo "=========================================="
} > "$NAC_TEST_LOG"

# Record start time
NAC_TEST_START=$(date +%s)

# Run nac-test and capture ALL output
log "  Starting nac-test..."
nac-test -d "$DATA_DIR" -t "$TESTS_DIR" -o "$OUTPUT_DIR" --pyats 2>&1 | tee -a "$NAC_TEST_LOG" | tee "$DIAG_DIR/260_nac_test_raw_output.txt"
NAC_TEST_EXIT=$?

# Record end time
NAC_TEST_END=$(date +%s)
NAC_TEST_DURATION=$((NAC_TEST_END - NAC_TEST_START))

{
    echo ""
    echo "=========================================="
    echo "NAC-TEST OUTPUT ENDS"
    echo "=========================================="
    echo ""
    echo "Exit code: $NAC_TEST_EXIT"
    echo "Duration: ${NAC_TEST_DURATION}s"
    echo "End timestamp: $(date)"
} >> "$NAC_TEST_LOG"

log ""
log "nac-test completed with exit code: $NAC_TEST_EXIT (${NAC_TEST_DURATION}s)"

###############################################################################
# SECTION 27: POST-EXECUTION CRASH DETECTION
###############################################################################
log ""
log "${YELLOW}>>> SECTION 27: Post-Execution Crash Detection <<<${NC}"

# Check for NEW crash reports created during execution
NEW_CRASH_COUNT=0

if $IS_MACOS; then
    collect "270_post_crash_reports" "
echo '=========================================='
echo 'CRASH REPORT ANALYSIS (macOS)'
echo '=========================================='
echo ''
echo 'Baseline timestamp (nac-test started): $CRASH_BASELINE_HUMAN'
echo 'Unix timestamp: $CRASH_BASELINE'
echo ''
echo 'IMPORTANT: Only crash reports created AFTER the baseline timestamp'
echo 'are from THIS diagnostic run. Earlier ones are pre-existing.'
echo ''
echo '=== NEW CRASH REPORTS (During This Run) ==='
new_count=0
find ~/Library/Logs/DiagnosticReports -type f -name '*[Pp]ython*' 2>/dev/null | while read f; do
    file_time=\$(stat -f %m \"\$f\" 2>/dev/null || echo 0)
    if [ \"\$file_time\" -ge \"$CRASH_BASELINE\" ]; then
        new_count=\$((new_count + 1))
        echo ''
        echo \">>> NEW CRASH #\$new_count: \$(basename \$f)\"
        echo \"    Created: \$(stat -f '%Sm' \"\$f\" 2>/dev/null)\"
        echo \"    Size: \$(stat -f '%z' \"\$f\" 2>/dev/null) bytes\"
        echo ''
        echo '--- First 100 lines ---'
        head -100 \"\$f\"
        echo '--- End of preview ---'
    fi
done
echo ''
echo '=========================================='
total_python=\$(ls ~/Library/Logs/DiagnosticReports/*[Pp]ython* 2>/dev/null | wc -l | tr -d ' ')
echo \"Total Python crash reports on system: \$total_python\"
echo \"Baseline timestamp: $CRASH_BASELINE\"
echo ''
echo 'If you see NEW crashes above, they occurred during nac-test execution.'
echo 'If no NEW crashes, the ERROR status may be from a silent failure.'
"
    # Copy ONLY new crash reports into clearly-named directory
    if [ -d ~/Library/Logs/DiagnosticReports ]; then
        log "  Checking for crash reports created after timestamp $CRASH_BASELINE..."
        find ~/Library/Logs/DiagnosticReports -type f -name '*[Pp]ython*' 2>/dev/null | while read f; do
            file_time=$(stat -f %m "$f" 2>/dev/null || echo 0)
            if [ "$file_time" -ge "$CRASH_BASELINE" ]; then
                cp "$f" "$DIAG_DIR/crash_reports_NEW_DURING_RUN/" 2>/dev/null
                log "  ${RED}NEW CRASH DETECTED:${NC} $(basename $f)"
            fi
        done
    fi
else
    # Linux crash detection
    collect "270_post_crash_reports" "
echo '=========================================='
echo 'CRASH REPORT ANALYSIS (Linux)'
echo '=========================================='
echo ''
echo 'Baseline timestamp (nac-test started): $CRASH_BASELINE_HUMAN'
echo 'Unix timestamp: $CRASH_BASELINE'
echo ''
echo '=== Checking /var/crash ==='
if [ -d /var/crash ]; then
    find /var/crash -type f -newermt '@$CRASH_BASELINE' 2>/dev/null | while read f; do
        echo \"NEW: \$f\"
    done
else
    echo '/var/crash not found'
fi
echo ''
echo '=== Checking coredumpctl ==='
if command -v coredumpctl &>/dev/null; then
    coredumpctl list --since '@$CRASH_BASELINE' --no-pager 2>/dev/null || echo 'No new coredumps'
else
    echo 'coredumpctl not available'
fi
echo ''
echo '=== Checking dmesg for crashes ==='
dmesg 2>/dev/null | grep -i -E 'segfault|killed|oom|python' | tail -20 || echo 'No crash messages in dmesg'
echo ''
echo '=== Checking journalctl for crashes ==='
journalctl --since '@$CRASH_BASELINE' 2>/dev/null | grep -i -E 'segfault|killed|core dump|python.*error' | tail -20 || echo 'No crash messages in journalctl'
"
    # Copy new crash reports on Linux
    if [ -d /var/crash ]; then
        log "  Checking /var/crash for new crash reports..."
        find /var/crash -type f -newermt "@$CRASH_BASELINE" 2>/dev/null | while read f; do
            cp "$f" "$DIAG_DIR/crash_reports_NEW_DURING_RUN/" 2>/dev/null
            log "  ${RED}NEW CRASH DETECTED:${NC} $(basename $f)"
        done
    fi
    # Also capture coredumpctl info if available
    if command -v coredumpctl &>/dev/null; then
        coredumpctl list --since "@$CRASH_BASELINE" --no-pager 2>/dev/null > "$DIAG_DIR/crash_reports_NEW_DURING_RUN/coredumpctl_new.txt"
    fi
fi

# Count new crashes
NEW_CRASH_ACTUAL=$(ls "$DIAG_DIR/crash_reports_NEW_DURING_RUN/" 2>/dev/null | wc -l | tr -d ' ')
if [ "$NEW_CRASH_ACTUAL" -gt 0 ]; then
    log "  ${RED}FOUND $NEW_CRASH_ACTUAL NEW CRASH REPORT(S) DURING EXECUTION${NC}"
else
    log "  ${GREEN}No new crash reports detected during execution${NC}"
fi

# Check system logs for errors during execution
if $IS_MACOS; then
    collect "271_execution_system_logs" "
echo 'System log entries during nac-test execution:'
echo '(Looking for errors, crashes, python-related messages)'
log show --predicate 'process contains \"python\" OR eventMessage contains \"crash\" OR eventMessage contains \"segfault\" OR eventMessage contains \"SIGKILL\" OR eventMessage contains \"SIGABRT\"' --start \"\$(date -r $NAC_TEST_START '+%Y-%m-%d %H:%M:%S')\" --end \"\$(date -r $NAC_TEST_END '+%Y-%m-%d %H:%M:%S')\" 2>/dev/null | tail -200 || echo 'Cannot access system logs'
"
else
    collect "271_execution_system_logs" "
echo 'System log entries during nac-test execution:'
journalctl --since '@$NAC_TEST_START' --until '@$NAC_TEST_END' 2>/dev/null | grep -i -E 'python|error|crash|killed|segfault' | tail -200 || echo 'Cannot access journalctl'
"
fi

# Check for any zombie or orphaned Python processes
collect "272_post_python_processes" "
echo 'Python processes after nac-test execution:'
ps aux | grep -i python | grep -v grep
echo ''
echo 'Zombie processes:'
ps aux | grep -E '^[^ ]+ +[0-9]+ +[0-9.]+ +[0-9.]+ +[0-9]+ +[0-9]+ +[^ ]+ +Z'
"

# Check core dump settings
collect "273_core_dump_check" "
echo 'Core dump configuration:'
ulimit -c
echo ''
if \$IS_MACOS; then
    echo 'Core dump directory:'
    sysctl kern.corefile 2>/dev/null || echo 'Cannot get kern.corefile'
else
    echo 'Core pattern:'
    cat /proc/sys/kernel/core_pattern 2>/dev/null || echo 'Cannot read core_pattern'
fi
echo ''
echo 'Looking for core dumps:'
find /cores -name 'core.*' -mmin -60 2>/dev/null | head -10 || echo 'No recent core dumps in /cores'
find . -name 'core.*' -mmin -60 2>/dev/null | head -10 || echo 'No recent core dumps in current directory'
"

###############################################################################
# SECTION 28: COLLECT NAC-TEST RESULTS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 28: Collect nac-test Results <<<${NC}"

collect "280_output_dir_structure" "
echo 'Output directory structure:'
if [ -d '$OUTPUT_DIR' ]; then
    ls -laR '$OUTPUT_DIR' 2>/dev/null | head -100
else
    echo 'Output directory not found'
fi"

collect "281_output_dir_tree" "
if command -v tree &>/dev/null; then
    tree '$OUTPUT_DIR' 2>/dev/null | head -100
else
    find '$OUTPUT_DIR' -type f 2>/dev/null | head -50
fi"

# Copy relevant result files
if [ -d "$OUTPUT_DIR" ]; then
    mkdir -p "$DIAG_DIR/nac_test_results"

    # Copy JSON results
    find "$OUTPUT_DIR" -name "*.json" -exec cp {} "$DIAG_DIR/nac_test_results/" \; 2>/dev/null

    # Copy report files
    find "$OUTPUT_DIR" -name "*.report" -exec cp {} "$DIAG_DIR/nac_test_results/" \; 2>/dev/null

    # Copy any log files
    find "$OUTPUT_DIR" -name "*.log" -exec cp {} "$DIAG_DIR/nac_test_results/" \; 2>/dev/null

    # Copy HTML reports (just the summary ones)
    find "$OUTPUT_DIR" -name "*summary*.html" -exec cp {} "$DIAG_DIR/nac_test_results/" \; 2>/dev/null

    log "  Copied results to diagnostic archive"
fi

collect "282_html_reports" "
echo 'HTML reports generated:'
find '$OUTPUT_DIR' -name '*.html' 2>/dev/null
"

###############################################################################
# SECTION 29: PYATS ARCHIVES
###############################################################################
log ""
log "${YELLOW}>>> SECTION 29: PyATS Archives <<<${NC}"

collect "290_pyats_archives" "
echo 'Recent PyATS archives:'
find . -name '*.zip' -mmin -60 2>/dev/null | head -20
echo ''
echo '⚠️  WARNING: PyATS archives (.zip files) contain raw execution logs that'
echo '   MAY INCLUDE CREDENTIALS if verbose/debug logging was enabled.'
echo '   These archives are included for diagnostic completeness, but please'
echo '   review them before sharing if you have concerns about credential exposure.'
"

# Copy recent archives
ARCHIVE_COUNT=0
for archive in $(find . -name '*.zip' -mmin -60 2>/dev/null | head -5); do
    cp "$archive" "$DIAG_DIR/" 2>/dev/null && ARCHIVE_COUNT=$((ARCHIVE_COUNT + 1))
done
log "  Copied $ARCHIVE_COUNT recent PyATS archives"
if [ "$ARCHIVE_COUNT" -gt 0 ]; then
    log "  ${YELLOW}⚠️  WARNING: Archives may contain logs with credentials - review before sharing${NC}"
fi

###############################################################################
# SECTION 30: ADDITIONAL CRASH ANALYSIS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 30: Additional Crash Analysis <<<${NC}"

if $IS_MACOS; then
    collect "300_all_crash_reports" "
echo '=== All Python Crash Reports (Last 7 Days) ==='
find ~/Library/Logs/DiagnosticReports -name '*[Pp]ython*' -mtime -7 2>/dev/null | while read f; do
    echo ''
    echo \"=== \$(basename \$f) ===\"
    echo \"Created: \$(stat -f '%Sm' \"\$f\" 2>/dev/null)\"
    head -50 \"\$f\"
    echo '...[truncated]...'
done
"
else
    collect "300_all_crash_reports" "
echo '=== Linux Crash Analysis ==='
echo ''
echo '=== /var/crash contents ==='
ls -la /var/crash/ 2>/dev/null || echo 'Cannot access /var/crash'
echo ''
echo '=== Recent coredumps ==='
if command -v coredumpctl &>/dev/null; then
    coredumpctl list --no-pager 2>/dev/null | tail -20
else
    echo 'coredumpctl not available'
fi
echo ''
echo '=== apport crashes ==='
ls -la /var/crash/*.crash 2>/dev/null | tail -10 || echo 'No apport crash files'
"
fi

###############################################################################
# SECTION 31: SYSTEM LOGS SUMMARY
###############################################################################
log ""
log "${YELLOW}>>> SECTION 31: System Logs Summary <<<${NC}"

if $IS_MACOS; then
    collect "310_system_log_errors" "
echo '=== System Log Errors (Last Hour) ==='
log show --predicate 'eventType == \"logEvent\" AND messageType == \"error\"' --last 1h 2>/dev/null | grep -i python | tail -100 || echo 'Cannot access system logs'
"
else
    collect "310_system_log_errors" "
echo '=== journalctl Errors (Last Hour) ==='
journalctl --since '1 hour ago' --priority err 2>/dev/null | grep -i python | tail -100 || echo 'Cannot access journalctl'
echo ''
echo '=== syslog errors ==='
grep -i error /var/log/syslog 2>/dev/null | grep -i python | tail -50 || echo 'Cannot access syslog'
"
fi

###############################################################################
# SECTION 32: MEMORY ANALYSIS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 32: Memory Analysis <<<${NC}"

collect "320_memory_snapshot" "
echo '=== Memory Snapshot After Test ==='
if \$IS_MACOS; then
    vm_stat
    echo ''
    echo 'Memory pressure:'
    memory_pressure 2>/dev/null || echo 'memory_pressure command not available'
else
    free -h
    echo ''
    cat /proc/meminfo | head -30
    echo ''
    echo 'Memory-hungry processes:'
    ps aux --sort=-%mem | head -15
fi
"

###############################################################################
# SECTION 33: SILENT FAILURE DETECTION
###############################################################################
log ""
log "${YELLOW}>>> SECTION 33: Silent Failure Detection <<<${NC}"

# Test 1: Multiprocessing with SSL (with timeout to prevent hanging)
collect "330_multiprocessing_with_ssl" "
echo '=== Testing Multiprocessing with SSL (Common macOS Issue) ==='
timeout 30 python << 'PYEOF' || echo 'TEST TIMED OUT (30s) - may indicate multiprocessing/SSL issue'
import multiprocessing
import ssl
import sys
import os
import signal

def worker():
    try:
        # This combination can cause silent crashes on macOS
        ctx = ssl.create_default_context()
        return \"OK\"
    except Exception as e:
        return f\"ERROR: {e}\"

if __name__ == \"__main__\":
    print(f\"Start method: {multiprocessing.get_start_method()}\")
    print(f\"Platform: {sys.platform}\")

    # Force spawn method (safest for macOS)
    try:
        ctx = multiprocessing.get_context('spawn')
        pool = ctx.Pool(2)
        # Use apply_async with timeout instead of map to avoid hanging
        results = []
        for i in range(4):
            r = pool.apply_async(worker)
            try:
                results.append(r.get(timeout=10))
            except multiprocessing.TimeoutError:
                results.append('TIMEOUT')
        pool.close()
        pool.terminate()
        print(f\"Results: {results}\")
        if all(r == 'OK' for r in results):
            print(\"TEST PASSED: Multiprocessing with SSL works\")
        else:
            print(\"TEST PARTIAL: Some workers failed or timed out\")
    except Exception as e:
        print(f\"TEST FAILED: {e}\")
PYEOF
"

# Test 2: PyATS subprocess test
collect "331_pyats_subprocess_test" "
echo '=== Testing PyATS in Subprocess ==='
python << 'PYEOF'
import subprocess
import sys

code = '''
import sys
try:
    from pyats import aetest
    from pyats.topology import loader
    print(\"PyATS imports OK\")
    sys.exit(0)
except Exception as e:
    print(f\"ERROR: {e}\")
    sys.exit(1)
'''

result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30)
print(f\"stdout: {result.stdout}\")
print(f\"stderr: {result.stderr}\")
print(f\"returncode: {result.returncode}\")
if result.returncode == 0:
    print(\"TEST PASSED: PyATS works in subprocess\")
else:
    print(\"TEST FAILED: PyATS subprocess returned non-zero exit code\")
PYEOF
"

# Test 3: Async HTTP test
collect "332_async_http_test" "
echo '=== Testing Async HTTP Client ==='
python << 'PYEOF'
import asyncio
import httpx

async def test():
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            # Don't actually make a request, just test client creation
            print(\"AsyncClient created successfully\")
            return \"OK\"
    except Exception as e:
        return f\"ERROR: {e}\"

result = asyncio.run(test())
print(f\"Result: {result}\")
if \"OK\" in result:
    print(\"TEST PASSED: Async HTTP client works\")
else:
    print(f\"TEST FAILED: {result}\")
PYEOF
"

# Test 4: Signal handling
collect "333_signal_handling_test" "
echo '=== Testing Signal Handling ==='
python << 'PYEOF'
import signal
import sys

def handler(signum, frame):
    print(f\"Caught signal {signum}\")

# Check current handlers
print(\"Current SIGCHLD handler:\", signal.getsignal(signal.SIGCHLD))
print(\"Current SIGTERM handler:\", signal.getsignal(signal.SIGTERM))

# Test setting handler
try:
    old_handler = signal.signal(signal.SIGCHLD, handler)
    signal.signal(signal.SIGCHLD, old_handler)
    print(\"TEST PASSED: Signal handling works\")
except Exception as e:
    print(f\"TEST FAILED: {e}\")
PYEOF
"

# Test 5: stderr capture test
collect "334_stderr_capture_test" "
echo '=== Testing stderr Capture ==='
python << 'PYEOF'
import sys
import io

# Test that stderr is properly set up
print(f\"stderr: {sys.stderr}\")
print(f\"stderr encoding: {sys.stderr.encoding}\")
print(f\"stderr isatty: {sys.stderr.isatty()}\")

# Write to stderr
sys.stderr.write(\"Test stderr write\\n\")
sys.stderr.flush()

print(\"TEST PASSED: stderr capture works\")
PYEOF
"

# Test 6: SD-WAN auth test (if URL is configured)
if [ "$SDWAN_URL" != "https://YOUR-SDWAN-MANAGER-IP-OR-HOSTNAME" ]; then
collect "335_sdwan_auth_test" "
echo '=== Testing SD-WAN Authentication ==='
python << 'PYEOF'
import os
import sys

try:
    from nac_test_pyats_common.sdwan_manager import SDWANManagerAuth

    url = os.environ.get('SDWAN_URL')
    username = os.environ.get('SDWAN_USERNAME')
    password = os.environ.get('SDWAN_PASSWORD')

    print(f\"Testing auth to: {url}\")
    auth = SDWANManagerAuth.get_auth()
    print(f\"Auth result keys: {list(auth.keys())}\")
    print(\"TEST PASSED: SD-WAN authentication works\")
except Exception as e:
    print(f\"TEST FAILED: {e}\")
    import traceback
    traceback.print_exc()
PYEOF
"
else
    collect "335_sdwan_auth_test" "echo 'SDWAN_URL not configured - skipping auth test'"
fi

# Test 7: Check for atexit handlers
collect "336_atexit_handlers" "
echo '=== Checking atexit Handlers ==='
python << 'PYEOF'
import atexit
import sys

# Get registered handlers
handlers = atexit._ncallbacks() if hasattr(atexit, '_ncallbacks') else 'unknown'
print(f\"Number of atexit handlers: {handlers}\")

# Check if coverage is registered (can cause issues)
if 'coverage' in sys.modules:
    print(\"WARNING: coverage module is loaded - may affect exit\")

print(\"atexit check complete\")
PYEOF
"

# Test 8: Exception hook
collect "337_exception_hook_test" "
echo '=== Exception Hook Test ==='
python << 'PYEOF'
import sys

print(f\"sys.excepthook: {sys.excepthook}\")
print(f\"Default excepthook: {sys.__excepthook__}\")

if sys.excepthook != sys.__excepthook__:
    print(\"WARNING: Exception hook has been modified!\")
    print(\"This could suppress error messages.\")
else:
    print(\"Exception hook: DEFAULT (not modified)\")
PYEOF
"

# Test 9: PyATS Easypy test
collect "338_pyats_easypy_test" "
echo '=== PyATS Easypy Test ==='
python << 'PYEOF'
import subprocess
import sys
import tempfile
import os

# Create a minimal job file
job_content = '''
import os
from pyats.easypy import run

def main(runtime):
    pass
'''

# Create a minimal test
test_content = '''
from pyats import aetest

class SimpleTest(aetest.Testcase):
    @aetest.test
    def test_pass(self):
        pass
'''

with tempfile.TemporaryDirectory() as tmpdir:
    job_file = os.path.join(tmpdir, 'test_job.py')
    test_file = os.path.join(tmpdir, 'test_script.py')

    with open(job_file, 'w') as f:
        f.write(job_content)
    with open(test_file, 'w') as f:
        f.write(test_content)

    # Try to run pyats
    cmd = [sys.executable, '-m', 'pyats.easypy', job_file, '--no-mail']
    print(f\"Running: {' '.join(cmd)}\")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=tmpdir)
    print(f\"Exit code: {result.returncode}\")
    if result.stdout:
        print(f\"stdout (last 500 chars): {result.stdout[-500:]}\")
    if result.stderr:
        print(f\"stderr (last 500 chars): {result.stderr[-500:]}\")

    if result.returncode == 0:
        print(\"EASYPY TEST: PASSED\")
    else:
        print(\"EASYPY TEST: FAILED (non-zero exit)\")
PYEOF
"

###############################################################################
# SECTION 34: PLATFORM-SPECIFIC ADDITIONAL CHECKS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 34: Platform-Specific Checks <<<${NC}"

if $IS_MACOS; then
    collect "340_macos_python_framework" "
echo '=== macOS Python Framework Check ==='
echo 'Python framework location:'
python -c 'import sys; print(sys.prefix)'
echo ''
echo 'Linked libraries:'
otool -L \$(which python) 2>/dev/null | head -20 || echo 'Cannot run otool'
"
    collect "341_macos_sandbox" "
echo '=== macOS Sandbox Check ==='
sandbox-exec -n no-network echo 'Sandbox works' 2>/dev/null || echo 'Cannot test sandbox'
"
else
    collect "340_linux_python_libs" "
echo '=== Linux Python Library Dependencies ==='
ldd \$(which python3) 2>/dev/null | head -30 || echo 'Cannot run ldd'
echo ''
echo 'Python shared libraries:'
find /usr -name 'libpython*' 2>/dev/null | head -10
"
    collect "341_linux_namespaces" "
echo '=== Linux Namespace/Container Check ==='
echo 'Running in container?'
if [ -f /.dockerenv ]; then
    echo 'Docker container detected'
elif [ -f /run/.containerenv ]; then
    echo 'Podman container detected'
elif grep -q 'docker\|lxc\|kubepods' /proc/1/cgroup 2>/dev/null; then
    echo 'Container environment detected via cgroup'
else
    echo 'Not running in a container'
fi
echo ''
echo 'Namespace info:'
ls -la /proc/self/ns/ 2>/dev/null
"
    collect "342_linux_systemd" "
echo '=== Systemd Status ==='
if command -v systemctl &>/dev/null; then
    systemctl --user status 2>/dev/null | head -20 || echo 'Cannot get user systemd status'
else
    echo 'systemd not available'
fi
"
fi

###############################################################################
# SECTION 35: NAC-TEST POST-EXECUTION ANALYSIS
###############################################################################
log ""
log "${YELLOW}>>> SECTION 35: NAC-Test Post-Execution Analysis <<<${NC}"

collect "350_pyats_results_analysis" "
echo '=== PyATS Results Analysis ==='
if [ -d '$OUTPUT_DIR/pyats_results' ]; then
    echo 'Looking for results.json files...'
    find '$OUTPUT_DIR' -name 'results.json' 2>/dev/null | while read f; do
        echo ''
        echo \"=== \$f ===\"
        python << PYEOF
import json
try:
    with open('\$f') as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        for key in ['passed', 'failed', 'errored', 'skipped', 'blocked']:
            if key in data:
                print(f'  {key}: {data[key]}')
        if 'testcases' in data:
            print(f'  Total testcases: {len(data[\"testcases\"])}')
            for tc in data.get('testcases', []):
                if tc.get('result') in ['failed', 'errored', 'blocked']:
                    print(f'    ISSUE: {tc.get(\"name\", \"unknown\")} - {tc.get(\"result\")}')
except Exception as e:
    print(f'  Error parsing: {e}')
PYEOF
    done
else
    echo 'No pyats_results directory found'
fi
"

collect "351_error_pattern_analysis" "
echo '=== Error Pattern Analysis ==='
echo 'Scanning nac-test output for common error patterns...'
echo ''
if [ -f '$DIAG_DIR/260_nac_test_raw_output.txt' ]; then
    echo '--- Authentication Errors ---'
    grep -i -E 'auth.*fail|401|403|unauthorized|login.*fail|token.*fail' '$DIAG_DIR/260_nac_test_raw_output.txt' 2>/dev/null | head -5 || echo 'None found'
    echo ''
    echo '--- Connection Errors ---'
    grep -i -E 'connection.*fail|timeout|refused|unreachable|cannot connect|failed to connect' '$DIAG_DIR/260_nac_test_raw_output.txt' 2>/dev/null | head -5 || echo 'None found'
    echo ''
    echo '--- Import/Module Errors ---'
    grep -i -E 'importerror|modulenotfound|no module named' '$DIAG_DIR/260_nac_test_raw_output.txt' 2>/dev/null | head -5 || echo 'None found'
    echo ''
    echo '--- PyATS/Unicon Errors ---'
    grep -i -E 'statemachineerror|connectionerror|timeouterror|spawnerror' '$DIAG_DIR/260_nac_test_raw_output.txt' 2>/dev/null | head -5 || echo 'None found'
else
    echo 'No nac-test output file found'
fi
"

collect "352_leaked_resources_check" "
echo '=== Leaked Resources Check ==='
echo 'Open file descriptors by Python processes:'
lsof -c python 2>/dev/null | grep -E 'REG|FIFO|PIPE|sock' | wc -l | xargs echo '  Count:'
echo ''
echo 'Network connections by Python:'
if \$IS_MACOS; then
    lsof -c python 2>/dev/null | grep -E 'TCP|UDP' | head -10 || echo '  None found'
else
    ss -p 2>/dev/null | grep python | head -10 || echo '  Cannot check'
fi
echo ''
echo 'Temp files created during this session:'
find /tmp -user \$(whoami) -mmin -30 \\( -name '*nac*' -o -name '*pyats*' -o -name '*tmp*job*' \\) 2>/dev/null | head -10 || echo '  None found'
"

collect "353_html_report_check" "
echo '=== HTML Report Verification ==='
if [ -d '$OUTPUT_DIR/pyats_results' ]; then
    echo 'HTML reports generated:'
    find '$OUTPUT_DIR' -name '*.html' 2>/dev/null | wc -l | xargs echo '  Total:'
    echo ''
    echo 'Summary reports:'
    find '$OUTPUT_DIR' -name '*summary*.html' 2>/dev/null | head -5
else
    echo 'No HTML reports directory found'
fi
"

collect "354_archive_integrity" "
echo '=== Archive Integrity Check ==='
find '$OUTPUT_DIR' -name '*.zip' 2>/dev/null | head -5 | while read archive; do
    echo \"Archive: \$(basename \$archive)\"
    if unzip -t \"\$archive\" > /dev/null 2>&1; then
        echo '  Integrity: OK'
    else
        echo '  Integrity: CORRUPTED'
    fi
done
"

###############################################################################
# DONE - CREATE SUMMARY AND ZIP
###############################################################################
log ""
log "${GREEN}=== Collection Complete ===${NC}"

# Count files
FILE_COUNT=$(find "$DIAG_DIR" -type f | wc -l)

# Create summary file
{
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║           NAC-TEST DIAGNOSTIC SUMMARY v4.1                       ║"
    echo "║              Cross-Platform Edition                              ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Collection timestamp: $(date)"
    echo "Script version: 4.1"
    echo ""
    echo "PLATFORM:"
    echo "  OS Type: $OS_TYPE"
    echo "  OS Name: $OS_PRETTY_NAME"
    if $IS_LINUX; then
        echo "  Distribution: $OS_RELEASE"
    fi
    echo ""
    echo "SYSTEM:"
    echo "  Hostname: $(hostname)"
    echo "  User: $(whoami)"
    if $IS_MACOS; then
        echo "  macOS: $(sw_vers -productVersion 2>/dev/null || echo 'Unknown')"
        echo "  Architecture: $(arch)"
        echo "  CPU: $(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo 'N/A')"
    else
        echo "  Kernel: $(uname -r)"
        echo "  Architecture: $(uname -m)"
        echo "  CPU: $(grep 'model name' /proc/cpuinfo 2>/dev/null | head -1 | cut -d: -f2 | xargs || echo 'N/A')"
    fi
    echo ""
    echo "PYTHON:"
    echo "  Version: $(python --version 2>&1)"
    echo "  Executable: $(which python)"
    echo "  VIRTUAL_ENV: $VIRTUAL_ENV"
    echo ""
    echo "CONFIGURATION:"
    echo "  SDWAN_URL: $SDWAN_URL"
    echo "  DATA_DIR: $DATA_DIR"
    echo "  TESTS_DIR: $TESTS_DIR"
    echo ""
    echo "FILES COLLECTED: $FILE_COUNT"
    echo ""
    echo "CRASH REPORTS:"
    PRE_COUNT=$(ls "$DIAG_DIR/crash_reports_PRE_EXISTING/" 2>/dev/null | wc -l | tr -d ' ')
    NEW_COUNT=$(ls "$DIAG_DIR/crash_reports_NEW_DURING_RUN/" 2>/dev/null | wc -l | tr -d ' ')
    echo "  Pre-existing (before nac-test): $PRE_COUNT"
    echo "  New (during nac-test run):      $NEW_COUNT"
    if [ "$NEW_COUNT" -gt 0 ]; then
        echo "  >>> CRASHES OCCURRED DURING EXECUTION <<<"
        echo "  Files in: crash_reports_NEW_DURING_RUN/"
    fi
    echo "  Baseline timestamp: $CRASH_BASELINE_HUMAN"
    echo ""
    echo "NAC-TEST EXECUTION:"
    echo "  Exit code: $NAC_TEST_EXIT"
    echo "  Duration: ${NAC_TEST_DURATION}s"
    echo ""
    echo "══════════════════════════════════════════════════════════════════"
    echo "                    POTENTIAL ISSUES DETECTED"
    echo "══════════════════════════════════════════════════════════════════"
    echo ""

    # Check for common issues
    if grep -l "pyats.contrib" "$DIAG_DIR"/*.txt 2>/dev/null | xargs grep -l "MISSING\|ImportError" 2>/dev/null; then
        echo "⚠️  CRITICAL: pyats.contrib may be missing!"
        echo "   Fix: pip install pyats.contrib"
        echo ""
    fi

    # Look for FAIL markers
    echo "Files with potential issues:"
    for f in "$DIAG_DIR"/*.txt; do
        if grep -q -E "FAIL|FAILED|ERROR|Exception|Traceback|COMMAND FAILED|PYTHON FAILED" "$f" 2>/dev/null; then
            echo ""
            echo ">>> $(basename "$f"):"
            grep -E "FAIL|FAILED|ERROR|Exception|Traceback|COMMAND FAILED|PYTHON FAILED" "$f" | head -5
        fi
    done

    echo ""
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

# Final credential masking pass on all files (using comprehensive masking function)
log "  Performing final credential masking..."
find "$DIAG_DIR" -name "*.txt" -type f 2>/dev/null | while read f; do
    mask_credentials_in_file "$f"
done

# Also mask any JSON files that were copied
find "$DIAG_DIR" -name "*.json" -type f 2>/dev/null | while read f; do
    mask_credentials_in_file "$f"
done

# Mask log files that were copied
find "$DIAG_DIR" -name "*.log" -type f 2>/dev/null | while read f; do
    mask_credentials_in_file "$f"
done

# Create the zip
ZIP_NAME="${DIAG_DIR}.zip"
log ""
log "Creating archive: $ZIP_NAME"
zip -r "$ZIP_NAME" "$DIAG_DIR" > /dev/null

log ""
log "╔══════════════════════════════════════════════════════════════════╗"
log "║              DIAGNOSTIC COLLECTION COMPLETE                       ║"
log "╚══════════════════════════════════════════════════════════════════╝"
log ""
log "Archive: ${GREEN}$ZIP_NAME${NC}"
log "Size: $(ls -lh "$ZIP_NAME" | awk '{print $5}')"
log "Files: $FILE_COUNT"
log ""
log "Platform: ${CYAN}$OS_PRETTY_NAME${NC}"
log ""

# Report on crash reports
PRE_COUNT=$(ls "$DIAG_DIR/crash_reports_PRE_EXISTING/" 2>/dev/null | wc -l | tr -d ' ')
NEW_COUNT=$(ls "$DIAG_DIR/crash_reports_NEW_DURING_RUN/" 2>/dev/null | wc -l | tr -d ' ')
log "Crash Reports:"
log "  - Pre-existing (before run): ${PRE_COUNT} files in crash_reports_PRE_EXISTING/"
log "  - New (during run):          ${NEW_COUNT} files in crash_reports_NEW_DURING_RUN/"
if [ "$NEW_COUNT" -gt 0 ]; then
    log "  ${RED}>>> NEW CRASHES DETECTED DURING EXECUTION <<<${NC}"
fi
log ""
log "${YELLOW}Please send the file '$ZIP_NAME' for analysis.${NC}"
log "${YELLOW}NOTE: Credentials have been masked in all text, JSON, and log files.${NC}"
log ""
log "${RED}⚠️  IMPORTANT: PyATS archive files (.zip) contain raw execution logs${NC}"
log "${RED}   that MAY INCLUDE CREDENTIALS if debug logging was enabled.${NC}"
log "${RED}   Please review archive contents before sharing if concerned.${NC}"
log ""
