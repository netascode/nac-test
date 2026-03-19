# Unicon Disconnect Delay Analysis

**Date:** February 9, 2026  
**Issue:** 10-second delay after device.disconnect() in PyATS/Unicon  
**Solution:** Configure `POST_DISCONNECT_WAIT_SEC` setting

---

## Summary

When disconnecting from devices using PyATS/Unicon, there is a **10-second delay** after the connection is closed. This is controlled by the `POST_DISCONNECT_WAIT_SEC` setting, which can be overridden to reduce or eliminate the delay when using a connection broker that manages connection reuse.

---

## Root Cause

### The Delay

**File:** `unicon/src/unicon/eal/backend/pty_backend.py`

```python
def close(self):
    """Close the spawn session"""
    # ... termination logic ...
    
    time.sleep(self.settings.GRACEFUL_DISCONNECT_WAIT_SEC)  # 1 second (subprocess termination)
    # ... kill subprocess ...
    
    self.fd = None
    time.sleep(self.settings.POST_DISCONNECT_WAIT_SEC)      # 10 seconds (cooldown)
    self.log.debug("spawn session '{}' has been closed.".format(self.spawn_command))
```

### Default Settings

**File:** `unicon/src/unicon/settings.py`

```python
class Settings(BaseSettings):
    # Amount of time to wait after terminating the spawned subprocess
    # before doing a forcible kill.
    GRACEFUL_DISCONNECT_WAIT_SEC = 1
    
    # The amount of time to wait after the spawn session is killed before
    # disconnection is deemed to be complete.  This avoids "Connection Refused"
    # errors should the user be doing back-to-back disconnect followed by connect.
    POST_DISCONNECT_WAIT_SEC = 10
```

### Purpose (from documentation)

> **POST_DISCONNECT_WAIT_SEC**: The amount of time to wait after the spawn session is killed before disconnection is deemed to be complete. This avoids "Connection Refused" errors should the user be doing back-to-back disconnect followed by connect.

---

## Solution

### Setting Values

There are TWO delay settings involved in disconnect:

| Setting | Default | Purpose | Recommendation |
|---------|---------|---------|----------------|
| `GRACEFUL_DISCONNECT_WAIT_SEC` | 1 second | Wait for subprocess to terminate gracefully before forceful kill | Keep at 1s (subprocess cleanup) |
| `POST_DISCONNECT_WAIT_SEC` | 10 seconds | Cooldown period after disconnect to avoid connection errors | **Set to 0 when using connection broker** |

### When to Reduce the Delay

**Use `POST_DISCONNECT_WAIT_SEC = 0` when:**
- Using a connection broker that manages connection reuse
- Tests don't do back-to-back disconnect → reconnect to the same device
- Connection pooling handles the cooldown period

**Keep default (10 seconds) when:**
- Doing rapid disconnect → reconnect cycles without a broker
- Need to avoid "Connection Refused" errors from the device
- Standard PyATS usage without connection management

---

## Implementation Options

### Option 1: Global Setting (affects all devices)

```python
import unicon.settings

# At the start of your test/job
unicon.settings.Settings.POST_DISCONNECT_WAIT_SEC = 0
```

### Option 2: Per-Device Setting (recommended)

```python
# In testbed YAML
devices:
  device-name:
    connections:
      cli:
        settings:
          POST_DISCONNECT_WAIT_SEC: 0
          # GRACEFUL_DISCONNECT_WAIT_SEC: 1  # Optional, usually keep default
```

### Option 3: At Connection Time

```python
# When connecting
device.connect(settings={'POST_DISCONNECT_WAIT_SEC': 0})
```

### Option 4: Modify Settings Object

```python
# After connection
device.cli.spawn.settings.POST_DISCONNECT_WAIT_SEC = 0
```

---

## NAC-Test Integration

### Current Situation

nac-test uses a **ConnectionBroker** that:
- Manages SSH connections via Unix socket
- Pools connections for reuse across tests
- Handles cooldown internally
- Never does back-to-back disconnect → reconnect

**Therefore:** The 10-second delay is unnecessary overhead.

### Recommended Implementation

**Approach 1: Set in Generated Testbed** (Preferred)

Modify the testbed generation in nac-test to include the setting:

**File:** `nac_test/pyats_core/execution/device_executor.py` (or wherever testbed is generated)

```python
# In generated testbed YAML
devices:
  {device-name}:
    connections:
      cli:
        protocol: unicon
        class: unicon.Unicon
        settings:
          POST_DISCONNECT_WAIT_SEC: 0  # Connection broker handles cooldown
```

**Approach 2: Set in ConnectionBroker**

When the broker initializes connections:

**File:** `nac_test/pyats_core/ssh/connection_broker.py`

```python
async def _initialize_device_connection(self, device_name: str):
    """Initialize connection for a device"""
    device = self.testbed.devices[device_name]
    
    # Reduce disconnect delay - broker handles cooldown
    device.cli.spawn.settings.POST_DISCONNECT_WAIT_SEC = 0
    
    await device.connect(log_stdout=False)
```

**Approach 3: Set in Test Base Class**

In the test base classes:

**File:** `nac_test_pyats_common/iosxe_test_base.py` (or similar)

```python
class IOSXETestBase(aetest.Testcase):
    @aetest.setup
    def setup(self):
        # ... existing setup ...
        
        # Reduce disconnect delay when using connection broker
        if hasattr(self.device, 'cli') and hasattr(self.device.cli, 'spawn'):
            self.device.cli.spawn.settings.POST_DISCONNECT_WAIT_SEC = 0
```

---

## Impact Analysis

### Current Performance (with 10s delay)

```
4 devices × 11 tests per device = 44 test executions
If each test disconnects: 44 × 10s = 440 seconds (7m 20s) wasted on cooldown
```

**Note:** ConnectionBroker likely keeps connections alive, so the actual number of disconnects may be lower. Need to verify when disconnect is actually called.

### Expected Performance (with 0s delay)

```
Zero cooldown overhead = immediate disconnect
Savings: Up to 7m 20s per test run (if 44 disconnects occur)
```

### Real-World Impact

The actual impact depends on:
1. **When does disconnect occur?**
   - After each test? (high impact)
   - Only at job end? (low impact)
   - On connection errors? (medium impact)

2. **Does ConnectionBroker keep connections alive?**
   - If yes: Few disconnects, lower impact
   - If no: Many disconnects, higher impact

**Action Required:** Instrument the code to log when `disconnect()` is called and measure actual time saved.

---

## Testing & Verification

### Test Plan

1. **Measure current disconnect count:**
   ```python
   # Add logging to connection broker or base class
   logger.info("DISCONNECT: device=%s, timestamp=%s", device.name, time.time())
   ```

2. **Run test with default (10s) delay:**
   ```bash
   time nac-test -d data -t tests -o results --pyats
   ```

3. **Run test with 0s delay:**
   ```bash
   # After implementing the setting
   time nac-test -d data -t tests -o results --pyats
   ```

4. **Compare results:**
   - Total runtime difference
   - Number of disconnects logged
   - Calculate actual time saved

### Verification

✅ **Tests still pass** (functionality unchanged)  
✅ **No connection errors** (no "Connection Refused")  
✅ **Faster execution** (measured reduction in runtime)

---

## Risks & Mitigation

### Potential Risks

1. **"Connection Refused" errors** if tests do back-to-back disconnect → reconnect
   - **Mitigation:** ConnectionBroker keeps connections alive, so reconnects use existing connections

2. **Device-side connection limits** if connections aren't properly closed
   - **Mitigation:** ConnectionBroker manages connection lifecycle

3. **Race conditions** if connection state isn't fully settled
   - **Mitigation:** Test thoroughly; revert to 1-2 seconds if issues arise

### Rollback Plan

If issues occur, can easily:
1. Set `POST_DISCONNECT_WAIT_SEC = 1` (minimal delay)
2. Revert to default `POST_DISCONNECT_WAIT_SEC = 10`
3. Make it configurable via CLI flag: `--disconnect-wait-sec 0`

---

## Related Settings

### Other Unicon Settings That May Affect Performance

| Setting | Default | Purpose | Recommendation |
|---------|---------|---------|----------------|
| `CONNECTION_TIMEOUT` | 60s | Timeout for establishing connection | Keep default |
| `EXEC_TIMEOUT` | 60s | Timeout for command execution | Keep default |
| `EXPECT_TIMEOUT` | 10s | Timeout for expect pattern matching | Keep default |
| `GRACEFUL_DISCONNECT_WAIT_SEC` | 1s | Wait for subprocess termination | Keep default |
| `POST_DISCONNECT_WAIT_SEC` | 10s | Cooldown after disconnect | **Set to 0** |

---

## References

### Source Files

1. **Settings Definition:**
   - `unicon/src/unicon/settings.py` (lines 12-18)

2. **Disconnect Implementation:**
   - `unicon/src/unicon/eal/backend/pty_backend.py` (close method)
   - `unicon/src/unicon/eal/backend/telnet_backend.py` (telnet variant)

3. **Connection Provider:**
   - `unicon/src/unicon/bases/routers/connection_provider.py` (disconnect methods)

### Documentation

- Unicon Settings: https://pubhub.devnetcloud.com/media/unicon/docs/user_guide/services/settings.html
- PyATS Testbed: https://pubhub.devnetcloud.com/media/pyats/docs/topology/schema.html#settings

---

## Next Steps

1. ✅ **Document the setting** (this file)
2. ⏳ **Measure current disconnect frequency** in nac-test
3. ⏳ **Implement setting in testbed generation** or ConnectionBroker
4. ⏳ **Test with 0s delay** and verify no errors
5. ⏳ **Measure performance improvement**
6. ⏳ **Update issue #519** with findings if significant impact

---

**Status:** Analysis complete - ready for implementation  
**Recommendation:** Set `POST_DISCONNECT_WAIT_SEC = 0` in ConnectionBroker or testbed generation  
**Expected Impact:** Up to 7m 20s faster per test run (depends on disconnect frequency)
