#!/bin/bash
# NAC-Test Diagnostic Collection Script
# Run this from your nac-test virtual environment
# Usage: bash nac-test-diagnostic.sh

set -e

DIAG_DIR="nac-test-diagnostics-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$DIAG_DIR"

echo "=== NAC-Test Diagnostic Collection ==="
echo "Output directory: $DIAG_DIR"
echo ""

# Helper function to run command and save output
collect() {
    local name="$1"
    local cmd="$2"
    echo "Collecting: $name"
    echo "=== $name ===" > "$DIAG_DIR/${name}.txt"
    echo "Command: $cmd" >> "$DIAG_DIR/${name}.txt"
    echo "Timestamp: $(date)" >> "$DIAG_DIR/${name}.txt"
    echo "---" >> "$DIAG_DIR/${name}.txt"
    eval "$cmd" >> "$DIAG_DIR/${name}.txt" 2>&1 || echo "COMMAND FAILED WITH EXIT CODE: $?" >> "$DIAG_DIR/${name}.txt"
}

# Helper for Python commands
collect_py() {
    local name="$1"
    local code="$2"
    echo "Collecting: $name"
    echo "=== $name ===" > "$DIAG_DIR/${name}.txt"
    echo "Python code: $code" >> "$DIAG_DIR/${name}.txt"
    echo "Timestamp: $(date)" >> "$DIAG_DIR/${name}.txt"
    echo "---" >> "$DIAG_DIR/${name}.txt"
    python -c "$code" >> "$DIAG_DIR/${name}.txt" 2>&1 || echo "PYTHON FAILED WITH EXIT CODE: $?" >> "$DIAG_DIR/${name}.txt"
}

echo ""
echo ">>> SYSTEM INFORMATION <<<"
collect "01_macos_version" "sw_vers"
collect "02_uname" "uname -a"
collect "03_hostname" "hostname"
collect "04_cpu_arch" "arch"
collect "05_sysctl_cpu" "sysctl -n machdep.cpu.brand_string 2>/dev/null || echo 'N/A'"
collect "06_memory" "sysctl -n hw.memsize"
collect "07_disk_space" "df -h"
collect "08_ulimit" "ulimit -a"
collect "09_locale" "locale"
collect "10_timezone" "date +%Z"

echo ""
echo ">>> SHELL ENVIRONMENT <<<"
collect "11_shell" "echo \$SHELL"
collect "12_path" "echo \$PATH"
collect "13_env_all" "env | sort"
collect "14_env_python" "env | grep -i python || echo 'No PYTHON env vars'"
collect "15_env_sdwan" "env | grep -i sdwan || echo 'No SDWAN env vars'"
collect "16_env_nac" "env | grep -i nac || echo 'No NAC env vars'"
collect "17_env_pyats" "env | grep -i pyats || echo 'No PYATS env vars'"
collect "18_env_iosxe" "env | grep -i iosxe || echo 'No IOSXE env vars'"

echo ""
echo ">>> PYTHON ENVIRONMENT <<<"
collect "20_which_python" "which python"
collect "21_which_python3" "which python3"
collect "22_python_version" "python --version"
collect "23_python_full_version" "python -c 'import sys; print(sys.version)'"
collect "24_python_executable" "python -c 'import sys; print(sys.executable)'"
collect "25_python_prefix" "python -c 'import sys; print(sys.prefix)'"
collect "26_python_platform" "python -c 'import platform; print(platform.platform())'"
collect "27_python_machine" "python -c 'import platform; print(platform.machine())'"
collect "28_python_architecture" "python -c 'import platform; print(platform.architecture())'"
collect "29_python_implementation" "python -c 'import platform; print(platform.python_implementation())'"
collect "30_sys_path" "python -c 'import sys; print(chr(10).join(sys.path))'"

echo ""
echo ">>> VIRTUAL ENVIRONMENT <<<"
collect "31_virtual_env" "echo \$VIRTUAL_ENV"
collect "32_venv_check" "python -c 'import sys; print(\"In venv:\", sys.prefix != sys.base_prefix)'"
collect "33_which_uv" "which uv || echo 'uv not found'"
collect "34_uv_version" "uv --version 2>/dev/null || echo 'uv not available'"
collect "35_which_pip" "which pip"
collect "36_pip_version" "pip --version"

echo ""
echo ">>> INSTALLED PACKAGES <<<"
collect "40_pip_freeze" "pip freeze"
collect "41_uv_pip_freeze" "uv pip freeze 2>/dev/null || echo 'uv pip freeze failed'"
collect "42_pip_list_verbose" "pip list -v"
collect "43_pip_check" "pip check 2>&1 || echo 'pip check found issues'"

echo ""
echo ">>> NAC-TEST PACKAGE CHECKS <<<"
collect_py "50_nac_test_import" "import nac_test; print('nac_test location:', nac_test.__file__); print('nac_test version:', getattr(nac_test, '__version__', 'no version attr'))"
collect_py "51_nac_test_cli" "from nac_test.cli import app; print('CLI app loaded OK')"
collect_py "52_nac_test_pyats_common_import" "import nac_test_pyats_common; print('nac_test_pyats_common location:', nac_test_pyats_common.__file__)"
collect_py "53_sdwan_imports" "
from nac_test_pyats_common.sdwan import SDWANManagerAuth, SDWANManagerTestBase, SDWANTestBase
print('SDWANManagerAuth:', SDWANManagerAuth)
print('SDWANManagerTestBase:', SDWANManagerTestBase)
print('SDWANTestBase:', SDWANTestBase)
"
collect_py "54_base_classes" "
from nac_test.pyats_integration.base import NACTestBase, SSHTestBase
print('NACTestBase:', NACTestBase)
print('SSHTestBase:', SSHTestBase)
"
collect_py "55_auth_cache" "
from nac_test.pyats_integration.auth_cache import AuthCache
print('AuthCache:', AuthCache)
print('AuthCache location:', AuthCache.__module__)
"

echo ""
echo ">>> PYATS CHECKS <<<"
collect "60_which_pyats" "which pyats"
collect "61_pyats_version" "pyats version"
collect "62_pyats_version_check" "pyats version check 2>&1 || echo 'pyats version check failed'"
collect_py "63_pyats_import" "import pyats; print('pyats location:', pyats.__file__); print('pyats version:', pyats.__version__)"
collect_py "64_pyats_aetest" "import pyats.aetest; print('aetest location:', pyats.aetest.__file__)"
collect_py "65_pyats_easypy" "import pyats.easypy; print('easypy location:', pyats.easypy.__file__)"
collect_py "66_pyats_topology" "import pyats.topology; print('topology location:', pyats.topology.__file__)"
collect_py "67_pyats_contrib" "import pyats.contrib; print('contrib location:', pyats.contrib.__file__)"
collect_py "68_pyats_datastructures" "import pyats.datastructures; print('datastructures location:', pyats.datastructures.__file__)"
collect_py "69_pyats_results" "import pyats.results; print('results location:', pyats.results.__file__)"

echo ""
echo ">>> GENIE CHECKS <<<"
collect_py "70_genie_import" "import genie; print('genie location:', genie.__file__); print('genie version:', genie.__version__)"
collect_py "71_genie_libs_parser" "import genie.libs.parser; print('parser location:', genie.libs.parser.__file__)"
collect_py "72_genie_libs_ops" "import genie.libs.ops; print('ops location:', genie.libs.ops.__file__)"
collect_py "73_genie_libs_sdk" "import genie.libs.sdk; print('sdk location:', genie.libs.sdk.__file__)"

echo ""
echo ">>> UNICON CHECKS <<<"
collect_py "75_unicon_import" "import unicon; print('unicon location:', unicon.__file__); print('unicon version:', unicon.__version__)"
collect_py "76_unicon_plugins" "import unicon.plugins; print('plugins location:', unicon.plugins.__file__)"

echo ""
echo ">>> NETWORK/HTTP LIBRARIES <<<"
collect_py "80_requests" "import requests; print('requests version:', requests.__version__); print('requests location:', requests.__file__)"
collect_py "81_httpx" "import httpx; print('httpx version:', httpx.__version__); print('httpx location:', httpx.__file__)"
collect_py "82_aiohttp" "import aiohttp; print('aiohttp version:', aiohttp.__version__); print('aiohttp location:', aiohttp.__file__)"
collect_py "83_urllib3" "import urllib3; print('urllib3 version:', urllib3.__version__); print('urllib3 location:', urllib3.__file__)"
collect_py "84_certifi" "import certifi; print('certifi version:', certifi.__version__); print('certifi where:', certifi.where())"

echo ""
echo ">>> SSL/TLS CHECKS <<<"
collect_py "85_ssl_version" "import ssl; print('SSL version:', ssl.OPENSSL_VERSION); print('SSL version info:', ssl.OPENSSL_VERSION_INFO)"
collect_py "86_ssl_paths" "import ssl; ctx = ssl.create_default_context(); print('CA certs file:', ctx.cert_store_stats())"
collect_py "87_ssl_default_verify" "import ssl; print('Default verify mode:', ssl.create_default_context().verify_mode)"

echo ""
echo ">>> ASYNC LIBRARIES <<<"
collect_py "88_asyncio" "import asyncio; print('asyncio location:', asyncio.__file__)"
collect_py "89_asyncssh" "import asyncssh; print('asyncssh version:', asyncssh.__version__); print('asyncssh location:', asyncssh.__file__)"

echo ""
echo ">>> YAML/JSON LIBRARIES <<<"
collect_py "90_yaml" "import yaml; print('PyYAML version:', yaml.__version__); print('yaml location:', yaml.__file__)"
collect_py "91_ruamel" "import ruamel.yaml; print('ruamel.yaml location:', ruamel.yaml.__file__)"
collect_py "92_nac_yaml" "import nac_yaml; print('nac_yaml version:', getattr(nac_yaml, '__version__', 'N/A')); print('nac_yaml location:', nac_yaml.__file__)"

echo ""
echo ">>> PROCESS/MULTIPROCESSING CHECKS <<<"
collect_py "95_multiprocessing_method" "import multiprocessing; print('Start method:', multiprocessing.get_start_method())"
collect_py "96_multiprocessing_context" "import multiprocessing; print('Context:', multiprocessing.get_context())"
collect_py "97_cpu_count" "import os; print('CPU count:', os.cpu_count())"
collect_py "98_fork_check" "
import sys
import multiprocessing
print('Platform:', sys.platform)
print('Default start method:', multiprocessing.get_start_method())
print('Available methods:', multiprocessing.get_all_start_methods())
"

echo ""
echo ">>> NAC-TEST INTERNAL CHECKS <<<"
collect_py "100_entry_points" "
from importlib.metadata import entry_points
eps = entry_points()
if hasattr(eps, 'select'):
    console_scripts = eps.select(group='console_scripts')
else:
    console_scripts = eps.get('console_scripts', [])
for ep in console_scripts:
    if 'nac' in str(ep).lower():
        print(ep)
"
collect_py "101_nac_test_modules" "
import nac_test
import pkgutil
for importer, modname, ispkg in pkgutil.walk_packages(path=nac_test.__path__, prefix=nac_test.__name__+'.'):
    print(modname, '(package)' if ispkg else '')
"
collect_py "102_pyats_integration_modules" "
from nac_test import pyats_integration
import pkgutil
for importer, modname, ispkg in pkgutil.walk_packages(path=pyats_integration.__path__, prefix=pyats_integration.__name__+'.'):
    print(modname, '(package)' if ispkg else '')
"

echo ""
echo ">>> NAC-TEST CLI HELP <<<"
collect "105_nac_test_help" "nac-test --help"
collect "106_nac_test_version" "nac-test --version 2>&1 || echo 'no --version flag'"

echo ""
echo ">>> PYATS PLUGIN CONFIG <<<"
collect_py "110_plugin_config" "
import tempfile
import yaml
config = {
    'plugins': {
        'easypy': {
            'reporter': {
                'class': 'pyats.reporter.Reporter',
                'parameters': {}
            }
        }
    }
}
print(yaml.dump(config, default_flow_style=False))
"

echo ""
echo ">>> FILE SYSTEM CHECKS <<<"
collect "115_tmp_permissions" "ls -la /tmp | head -20"
collect "116_tmp_space" "df -h /tmp"
collect "117_home_dir" "ls -la ~"
collect "118_cwd" "pwd && ls -la"

echo ""
echo ">>> NAC-TEST SOURCE LOCATIONS <<<"
collect_py "120_nac_test_files" "
import nac_test
import os
base = os.path.dirname(nac_test.__file__)
for root, dirs, files in os.walk(base):
    level = root.replace(base, '').count(os.sep)
    indent = ' ' * 2 * level
    print(f'{indent}{os.path.basename(root)}/')
    subindent = ' ' * 2 * (level + 1)
    for file in files:
        if file.endswith('.py'):
            print(f'{subindent}{file}')
"
collect_py "121_nac_test_pyats_common_files" "
import nac_test_pyats_common
import os
base = os.path.dirname(nac_test_pyats_common.__file__)
for root, dirs, files in os.walk(base):
    level = root.replace(base, '').count(os.sep)
    indent = ' ' * 2 * level
    print(f'{indent}{os.path.basename(root)}/')
    subindent = ' ' * 2 * (level + 1)
    for file in files:
        if file.endswith('.py'):
            print(f'{subindent}{file}')
"

echo ""
echo ">>> GIT INFORMATION <<<"
collect "125_nac_test_git" "cd \$(python -c 'import nac_test; import os; print(os.path.dirname(nac_test.__file__))') && git rev-parse HEAD 2>/dev/null && git status --short 2>/dev/null && git log -3 --oneline 2>/dev/null || echo 'Not a git repo or git not available'"
collect "126_nac_test_pyats_common_git" "cd \$(python -c 'import nac_test_pyats_common; import os; print(os.path.dirname(nac_test_pyats_common.__file__))') && git rev-parse HEAD 2>/dev/null && git status --short 2>/dev/null && git log -3 --oneline 2>/dev/null || echo 'Not a git repo or git not available'"

echo ""
echo ">>> DEEP IMPORT TRACE <<<"
collect_py "130_import_trace_nac_test" "
import sys
import importlib

# Capture import errors
errors = []
modules_to_test = [
    'nac_test',
    'nac_test.cli',
    'nac_test.pyats_integration',
    'nac_test.pyats_integration.base',
    'nac_test.pyats_integration.auth_cache',
    'nac_test.pyats_integration.discovery',
    'nac_test.pyats_integration.runner',
    'nac_test.pyats_integration.job_generator',
    'nac_test.pyats_integration.html_report',
]

for mod in modules_to_test:
    try:
        m = importlib.import_module(mod)
        print(f'OK: {mod} -> {m.__file__}')
    except Exception as e:
        print(f'FAIL: {mod} -> {type(e).__name__}: {e}')
        errors.append((mod, e))

if errors:
    print()
    print('=== ERRORS DETAIL ===')
    import traceback
    for mod, e in errors:
        print(f'\\n--- {mod} ---')
        traceback.print_exception(type(e), e, e.__traceback__)
"

collect_py "131_import_trace_pyats_common" "
import sys
import importlib

modules_to_test = [
    'nac_test_pyats_common',
    'nac_test_pyats_common.sdwan',
    'nac_test_pyats_common.aci',
    'nac_test_pyats_common.catalyst_center',
]

for mod in modules_to_test:
    try:
        m = importlib.import_module(mod)
        print(f'OK: {mod} -> {m.__file__}')
    except Exception as e:
        print(f'FAIL: {mod} -> {type(e).__name__}: {e}')
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
"

echo ""
echo ">>> SDWAN TEST BASE INSPECTION <<<"
collect_py "135_sdwan_test_base_mro" "
from nac_test_pyats_common.sdwan import SDWANManagerTestBase, SDWANTestBase
print('SDWANManagerTestBase MRO:')
for cls in SDWANManagerTestBase.__mro__:
    print(f'  {cls}')
print()
print('SDWANTestBase MRO:')
for cls in SDWANTestBase.__mro__:
    print(f'  {cls}')
"

collect_py "136_sdwan_test_base_attrs" "
from nac_test_pyats_common.sdwan import SDWANManagerTestBase
import inspect
print('SDWANManagerTestBase attributes:')
for name, value in inspect.getmembers(SDWANManagerTestBase):
    if not name.startswith('_'):
        print(f'  {name}: {type(value).__name__}')
"

echo ""
echo ">>> RUNTIME TEST <<<"
collect_py "140_create_minimal_test" "
# Create a minimal test to check if PyATS can even run
import tempfile
import os

test_code = '''
from pyats import aetest

class MinimalTest(aetest.Testcase):
    @aetest.test
    def test_basic(self):
        assert True, 'Basic test should pass'

if __name__ == '__main__':
    aetest.main()
'''

with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write(test_code)
    print(f'Created minimal test at: {f.name}')
    print('Test code:')
    print(test_code)
"

echo ""
echo ">>> VERBOSE IMPORT WITH WARNINGS <<<"
collect "145_python_verbose_import" "python -v -c 'from nac_test_pyats_common.sdwan import SDWANManagerTestBase' 2>&1 | tail -100"

echo ""
echo ">>> CHECK FOR DUPLICATE PACKAGES <<<"
collect_py "150_check_duplicates" "
import sys
from collections import defaultdict

# Check for duplicate module paths
modules = defaultdict(list)
for name, mod in sys.modules.items():
    if hasattr(mod, '__file__') and mod.__file__:
        modules[name].append(mod.__file__)

print('Checking for nac/pyats related modules:')
for name in sorted(modules.keys()):
    if any(x in name.lower() for x in ['nac', 'pyats', 'genie', 'unicon']):
        paths = modules[name]
        print(f'{name}: {paths[0]}')
"

echo ""
echo ">>> EXCEPTION HOOK TEST <<<"
collect_py "155_exception_handling" "
import sys
import warnings

# Show all warnings
warnings.filterwarnings('always')

# Check exception hook
print('Exception hook:', sys.excepthook)
print('Default exception hook:', sys.__excepthook__)

# Check if they're the same
if sys.excepthook is sys.__excepthook__:
    print('Exception hook is DEFAULT')
else:
    print('Exception hook has been MODIFIED')
"

echo ""
echo ">>> SIGNAL HANDLERS <<<"
collect_py "160_signal_handlers" "
import signal

signals_to_check = ['SIGTERM', 'SIGINT', 'SIGHUP', 'SIGCHLD', 'SIGUSR1', 'SIGUSR2']
for sig_name in signals_to_check:
    try:
        sig = getattr(signal, sig_name)
        handler = signal.getsignal(sig)
        print(f'{sig_name}: {handler}')
    except Exception as e:
        print(f'{sig_name}: ERROR - {e}')
"

echo ""
echo ">>> ATEXIT HANDLERS <<<"
collect_py "165_atexit" "
import atexit
print('atexit module location:', atexit.__file__ if hasattr(atexit, '__file__') else 'builtin')
# Can't easily inspect registered handlers, but we can note the module is available
print('atexit available: True')
"

echo ""
echo ">>> PYATS REPORTER CHECK <<<"
collect_py "170_pyats_reporter" "
try:
    from pyats.reporter import Reporter
    print('Reporter class:', Reporter)
    print('Reporter file:', Reporter.__module__)
except ImportError as e:
    print('Reporter import failed:', e)

try:
    from pyats.reporter.server import ReporterServer
    print('ReporterServer class:', ReporterServer)
except ImportError as e:
    print('ReporterServer import failed:', e)
"

echo ""
echo ">>> PYATS EASYPY PLUGINS <<<"
collect_py "175_easypy_plugins" "
try:
    from pyats.easypy import plugins
    print('Plugins module:', plugins.__file__)
    import pkgutil
    for importer, modname, ispkg in pkgutil.walk_packages(path=plugins.__path__, prefix=plugins.__name__+'.'):
        print(f'  {modname}')
except Exception as e:
    print('Error:', e)
"

echo ""
echo ">>> LOGGING CONFIGURATION <<<"
collect_py "180_logging_config" "
import logging

print('Root logger level:', logging.root.level)
print('Root logger handlers:', logging.root.handlers)

# Check for nac/pyats loggers
for name in sorted(logging.Logger.manager.loggerDict.keys()):
    if any(x in name.lower() for x in ['nac', 'pyats', 'genie', 'unicon']):
        logger = logging.getLogger(name)
        print(f'{name}: level={logger.level}, handlers={logger.handlers}')
"

echo ""
echo ">>> TEMP FILE CREATION TEST <<<"
collect_py "185_temp_test" "
import tempfile
import os

# Test temp file creation
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write('# test')
    temp_path = f.name

print(f'Created temp file: {temp_path}')
print(f'Temp file exists: {os.path.exists(temp_path)}')
print(f'Temp file readable: {os.access(temp_path, os.R_OK)}')
print(f'Temp file writable: {os.access(temp_path, os.W_OK)}')
print(f'Temp dir: {tempfile.gettempdir()}')
print(f'Temp dir writable: {os.access(tempfile.gettempdir(), os.W_OK)}')

# Cleanup
os.unlink(temp_path)
print(f'Cleanup successful: {not os.path.exists(temp_path)}')
"

echo ""
echo ">>> SUBPROCESS TEST <<<"
collect_py "190_subprocess_test" "
import subprocess
import sys

result = subprocess.run(
    [sys.executable, '-c', 'print(\"subprocess works\")'],
    capture_output=True,
    text=True
)
print('Return code:', result.returncode)
print('Stdout:', result.stdout)
print('Stderr:', result.stderr)
"

echo ""
echo ">>> PYATS RUN COMMAND TEST <<<"
collect "195_pyats_run_help" "pyats run job --help 2>&1 | head -50"

echo ""
echo ">>> ENVIRONMENT VARIABLE EXPANSION <<<"
collect_py "200_env_expansion" "
import os

required_vars = [
    'SDWAN_URL',
    'SDWAN_USERNAME',
    'SDWAN_PASSWORD',
    'IOSXE_USERNAME',
    'IOSXE_PASSWORD',
]

print('Environment variable status:')
for var in required_vars:
    value = os.environ.get(var)
    if value:
        # Mask passwords
        if 'PASSWORD' in var:
            print(f'{var}: SET (length={len(value)})')
        else:
            print(f'{var}: {value}')
    else:
        print(f'{var}: NOT SET')
"

echo ""
echo ">>> NETWORK CONNECTIVITY TEST <<<"
collect_py "205_network_test" "
import socket
import os

sdwan_url = os.environ.get('SDWAN_URL', '')
if sdwan_url:
    # Parse host from URL
    from urllib.parse import urlparse
    parsed = urlparse(sdwan_url)
    host = parsed.hostname
    port = parsed.port or 443

    print(f'Testing connection to {host}:{port}')
    try:
        sock = socket.create_connection((host, port), timeout=10)
        print(f'Connection successful!')
        sock.close()
    except Exception as e:
        print(f'Connection failed: {e}')
else:
    print('SDWAN_URL not set, skipping network test')
"

echo ""
echo "=== Collection Complete ==="
echo ""

# Create summary file
echo "=== DIAGNOSTIC SUMMARY ===" > "$DIAG_DIR/000_SUMMARY.txt"
echo "Collection timestamp: $(date)" >> "$DIAG_DIR/000_SUMMARY.txt"
echo "Hostname: $(hostname)" >> "$DIAG_DIR/000_SUMMARY.txt"
echo "User: $(whoami)" >> "$DIAG_DIR/000_SUMMARY.txt"
echo "macOS: $(sw_vers -productVersion)" >> "$DIAG_DIR/000_SUMMARY.txt"
echo "Python: $(python --version 2>&1)" >> "$DIAG_DIR/000_SUMMARY.txt"
echo "Architecture: $(arch)" >> "$DIAG_DIR/000_SUMMARY.txt"
echo "" >> "$DIAG_DIR/000_SUMMARY.txt"
echo "Files collected:" >> "$DIAG_DIR/000_SUMMARY.txt"
ls -la "$DIAG_DIR"/*.txt | wc -l >> "$DIAG_DIR/000_SUMMARY.txt"

# Check for any FAIL markers
echo "" >> "$DIAG_DIR/000_SUMMARY.txt"
echo "=== POTENTIAL ISSUES DETECTED ===" >> "$DIAG_DIR/000_SUMMARY.txt"
grep -l "FAIL\|FAILED\|ERROR\|Exception\|Traceback" "$DIAG_DIR"/*.txt 2>/dev/null | while read f; do
    echo "Issues in: $(basename $f)" >> "$DIAG_DIR/000_SUMMARY.txt"
done

# Zip everything
ZIP_NAME="${DIAG_DIR}.zip"
echo "Creating archive: $ZIP_NAME"
zip -r "$ZIP_NAME" "$DIAG_DIR"

echo ""
echo "=== DONE ==="
echo "Diagnostic archive created: $ZIP_NAME"
echo "Please send this file for analysis."
echo ""
echo "File size: $(ls -lh "$ZIP_NAME" | awk '{print $5}')"
