# Unicon POST_DISCONNECT_WAIT_SEC Setting Not Applied

## Summary

Setting `POST_DISCONNECT_WAIT_SEC: 0` in testbed connection settings does not eliminate the 10-second disconnect delay in Unicon. The delay still occurs despite the configuration.

## Evidence

Timestamps show 11-second intervals between disconnects (10s delay + 1s operation):

```
2026-02-09 16:30:02,934 - INFO - Disconnected from device: sd-dc-c8kv-01
2026-02-09 16:30:13,954 - INFO - Disconnected from device: sd-dc-c8kv-03  (+11s)
2026-02-09 16:30:24,978 - INFO - Disconnected from device: sd-dc-c8kv-02  (+11s)
2026-02-09 16:30:36,000 - INFO - Disconnected from device: sd-dc-c8kv-04  (+11s)
```

## Configuration Attempted

**File:** `nac_test/pyats_core/execution/device/testbed_generator.py`

```python
connection_args = {
    "protocol": "ssh",
    "ip": device["host"],
    "port": device.get("port", 22),
    "arguments": {...},
    "settings": {
        "POST_DISCONNECT_WAIT_SEC": 0,  # Not working
    },
}
```

## Impact

- 44 seconds wasted on 4 device disconnects (4 × 11s)
- Scales linearly with device count
- Minor impact compared to Task().run() optimization, but worth fixing

## Next Steps

1. Investigate correct way to override Unicon settings in testbed YAML
2. Try alternative approaches (global settings, runtime override)
3. Consider if ConnectionBroker disconnect needs explicit setting override

## References

- Unicon settings: `unicon/src/unicon/settings.py`
- Analysis: `.sisyphus/drafts/unicon-disconnect-delay-analysis.md`
