# Draft: tac-quicksilver Fix for Issue #588

This is the proposed fix for the AI prompt templates in tac-quicksilver to prevent AI from generating tests with context mismatches that cause "orphaned commands" in HTML reports.

## Addition to `jobfile_prompt_builder.j2` (after line 440)

Insert the following new section before "## Header Exclusion Requirements":

```jinja2
### CRITICAL: Context Reuse in Loops

**⚠️ ANTI-PATTERN WARNING - Creating new `api_context` inside loops causes "orphaned commands"**

When your test executes multiple CLI commands in a loop (e.g., iterating over VRFs, interfaces, or neighbors), you **MUST** create ONE `api_context` BEFORE the loop and reuse it for ALL commands.

**Why this matters:** The HTML report links commands to results by matching `api_context`. If you create a new context inside the loop but store a different context in `context['api_context']`, the report cannot match commands to results — they appear as "orphaned commands".

{% if target_os in cli_based_os %}
✅ **CORRECT - One context, reused for all commands:**
```python
async def verify_item(self, semaphore, client, context):
    async with semaphore:
        try:
            # Step 1: Build ONE api_context BEFORE any loop
            api_context = self.build_api_context(
                self.TEST_CONFIG['resource_type'],
                context.get("primary_identifier", "Global Check"),
                check_type=context.get("check_type")
            )
            
            # Step 2: Reuse the SAME context for ALL commands
            vrfs_to_check = ["default", "mgmt", "prod"]
            all_parsed_outputs = {}
            
            for vrf in vrfs_to_check:
                command = f"show ip route vrf {vrf}"
                with self.test_context(api_context):  # SAME context every iteration
                    output = await self.execute_command(command)
                parsed = self.parse_output(command, output=output)
                all_parsed_outputs[vrf] = parsed
            
            # Step 3: Store the SAME api_context used for commands
            context['api_context'] = api_context  # Links to ALL commands above
            
            # ... validation logic ...
```

❌ **WRONG - Creating new context per iteration (causes orphaned commands!):**
```python
async def verify_item(self, semaphore, client, context):
    async with semaphore:
        try:
            # WRONG: Creating context outside loop for discovery
            api_context_discover = self.build_api_context(...)
            
            vrfs_to_check = ["default", "mgmt", "prod"]
            
            for vrf in vrfs_to_check:
                # WRONG: Creating NEW context inside loop
                api_context_vrf = self.build_api_context(
                    self.TEST_CONFIG['resource_type'],
                    f"VRF {vrf}",  # Different identifier per iteration
                    check_type=context.get("check_type")
                )
                with self.test_context(api_context_vrf):  # Different context each time!
                    output = await self.execute_command(f"show ip route vrf {vrf}")
            
            # WRONG: Storing a DIFFERENT context than used for commands
            context['api_context'] = api_context_discover  # MISMATCH! Commands are orphaned.
```

**The Rule:** Whatever `api_context` you pass to `self.test_context()` during command execution **MUST** be the same object you store in `context['api_context']`.
{% else %}
✅ **CORRECT - One context, passed to all API calls:**
```python
async def verify_item(self, semaphore, client, context):
    async with semaphore:
        try:
            # Build ONE api_context BEFORE any loop
            api_context = self.build_api_context(
                self.TEST_CONFIG['resource_type'],
                context.get("primary_identifier", "Global Check")
            )
            
            # Reuse the SAME context for ALL API calls
            endpoints_to_check = ["/api/endpoint1", "/api/endpoint2"]
            
            for endpoint in endpoints_to_check:
                response = await client.get(endpoint, test_context=api_context)  # SAME context
            
            # Store the SAME api_context used for API calls
            context['api_context'] = api_context
```

❌ **WRONG - Creating new context per iteration:**
```python
for endpoint in endpoints_to_check:
    api_context_endpoint = self.build_api_context(...)  # DON'T create new contexts in loops!
    response = await client.get(endpoint, test_context=api_context_endpoint)

context['api_context'] = some_other_context  # MISMATCH causes orphaned API calls
```
{% endif %}
```

## Files to Modify

| File | Change |
|------|--------|
| `src/tac_quicksilver/templates/nac-templates/jobfile_prompt_builder.j2` | Add new "CRITICAL: Context Reuse in Loops" subsection after line 440 |

## What This Fixes

1. **Explicit prohibition** of creating `api_context` inside loops
2. **Clear "before/after" examples** showing correct vs incorrect patterns
3. **Explanation of WHY** — links the anti-pattern directly to the "orphaned commands" symptom
4. **The golden rule**: Whatever context you use in `test_context()` MUST be the same one stored in `context['api_context']`
