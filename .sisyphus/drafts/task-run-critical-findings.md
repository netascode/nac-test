# PyATS Task().run() Timeout Analysis - CRITICAL FINDINGS

**Date:** February 9, 2026  
**Source:** PyATS source code at `~/Documents/Test-Automation/pyats-repo/pkgs/easypy-pkg/src/pyats/easypy/tasks.py`

---

## CRITICAL DISCOVERY

**The `task.run()` method we're using in our code is NOT what we think it is.**

### What We Thought We Were Doing

```python
task = Task(testscript=test_file, taskid=test_name, max_runtime=21600, testbed=runtime.testbed)
task.run()  # We thought: "Run directly in-process, avoid subprocess overhead"
```

### What Actually Happens

`Task` inherits from `multiprocessing.Process`, so `task.run()` is the **multiprocessing.Process.run()** method:

**From PyATS source (tasks.py:182-191):**
```python
class Task(multiprocessing.Process):
    '''Task class

    Task class represents the actual task/testscript being executed through a
    child process. All tasks within easypy are encapsulated in its own forked
    process from easypy main program.

    Comes with all the necessary apis to allow users to control task runs from
    a jobfile, supporting both synchronous and asynchronous execution of tasks.
    '''
```

**The Task.run() method (lines 356-367):**
```python
def run(self):
    '''run task

    main entry point of all task processes. This api is run in the context
    of the forked child process. The following is performed here:

    1. configure environment/process for test harness execution
    2. attempt to run the test-harness with the provided arguments, catch
       any errors that may occur and report to parent using task messaging
       system
    3. wrap up.
    '''
```

**This is the SUBPROCESS ENTRY POINT**, not an in-process execution method!

---

## How PyATS Task Execution Actually Works

### Method 1: Using run() function (convenience wrapper)

**Source (tasks.py:547-577):**
```python
def run(*args, max_runtime = None, **kwargs):
    '''run api

    Shortcut function to start a Task(), wait for it to finish, and return
    the result to the caller. This api avoids the overhead of having to deal
    with the task objects, and provides a black-box method of creating tasks
    sequentially.

    Arguments
    ---------
        max_runtime (int): maximum time to wait for the task to run and
                           finish, before terminating it forcifully and
                           raising errors. If not provided, waits forever.
    '''
    task = Task(*args, **kwargs)
    task.start()              # Fork subprocess
    task.wait(max_runtime)    # Wait with timeout
    return task.result
```

**Flow:**
1. `Task()` - Create task object
2. `task.start()` - **Fork subprocess** (calls multiprocessing.Process.start())
3. `task.wait(max_runtime)` - Wait for subprocess with timeout

### Method 2: Using Task class directly

**Source (tasks.py:153-179):**
```python
def run(self, *args, max_runtime = None, **kwargs):
    '''run api (TaskManager method)

    Shortcut function to start a Task(), wait for it to finish, and return
    the result to the caller.
    '''
    task = Task(*args, **kwargs)
    task.start()              # Fork subprocess
    task.wait(max_runtime)    # Wait with timeout
    return task.result
```

**Same flow as Method 1.**

### Method 3: Manual control (what PyATS maintainer suggested)

```python
task = Task(testscript=..., max_runtime=...)
task.start()  # Fork subprocess
# Do other work...
task.wait()   # Wait for completion
```

---

## The Timeout Mechanism

**Source (tasks.py:486-509):**
```python
def wait(self, max_runtime = None):
    '''wait method

    Waits for this task to finish executing. If max_runtime is provided and
    exceeded, the task child process will be terminated (SIGTERM), and a
    TimeoutException will be raised to the caller.

    Arguments
    ---------
        max_runtime (int): maximum time to wait for the task to run and
                           finish, before terminating it forcifully and
                           raising errors. If not provided, waits forever.
    '''
    self.join(max_runtime)  # multiprocessing.Process.join() - blocks up to timeout

    if self.is_alive():     # Check if process still running after timeout
        # exceeded runtime, kill it
        self.terminate()    # Send SIGTERM to subprocess

        raise TimeoutError("Task '%s' has exceeded its max runtime of "
                           "'%s' seconds. It has been terminated "
                           "forcefully."
                           % (self.taskid, max_runtime))
```

**How it works:**
1. `self.join(max_runtime)` - Wait up to `max_runtime` seconds for subprocess
2. `self.is_alive()` - Check if subprocess still running
3. If yes: `self.terminate()` - Send SIGTERM to kill subprocess
4. Raise `TimeoutError` to caller

**This REQUIRES subprocess** - you can't send SIGTERM to yourself!

---

## What Our Code Is Actually Doing

**Our implementation (job_generator.py:73-79):**
```python
task = Task(
    testscript=test_file,
    taskid=test_name,
    max_runtime=21600,  # This parameter is IGNORED!
    testbed=runtime.testbed
)
task.run()  # Calls multiprocessing.Process.run() directly!
```

### THE PROBLEM

**We're calling `task.run()` directly**, which is the **subprocess entry point**.

**This is equivalent to:**
```python
# In multiprocessing.Process:
def start(self):
    # Fork subprocess
    pid = os.fork()
    if pid == 0:
        # Child process
        self.run()  # ← WE ARE CALLING THIS DIRECTLY IN PARENT PROCESS!
```

**We're executing the subprocess code IN THE PARENT PROCESS**, which:
1. ❌ **Bypasses the fork** - No subprocess is created
2. ❌ **Ignores max_runtime** - Never passed to wait()
3. ❌ **No timeout protection** - Code runs until completion or hangs forever
4. ✅ **Avoids subprocess overhead** - Runs in same process

---

## Why We Saw Performance Improvement

**We got 45.4% speedup because:**
- `task.run()` executes in-process (no fork overhead)
- But we lost all subprocess benefits:
  - Process isolation (crashes kill parent)
  - Timeout enforcement (hangs block forever)
  - Resource cleanup (zombie processes)

**We're essentially doing:**
```python
# Instead of this (safe but slow):
task.start()  # Fork subprocess
task.wait(max_runtime)  # Enforce timeout

# We're doing this (fast but dangerous):
task.run()  # Execute inline, no timeout, no isolation
```

---

## The PyATS Maintainer's Warning Makes Sense Now

> You can avoid the overhead of the process fork by calling the Task run API directly. **This breaks easypy if your script causes python to crash or calls sys.exit().**

**Translation:**
- "Avoid subprocess fork" = Call `task.run()` directly
- "Breaks easypy" = No isolation, crashes kill parent, no timeout
- "Not recommended" = For advanced users who understand the risks

---

## Correct Usage (With Subprocess)

**Option A: Use run() function (recommended):**
```python
from pyats.easypy import run

result = run(
    testscript=test_file,
    taskid=test_name,
    max_runtime=21600,  # This WORKS - passed to task.wait()
    testbed=runtime.testbed
)
```

**Option B: Use Task class manually:**
```python
from pyats.easypy import Task

task = Task(
    testscript=test_file,
    taskid=test_name,
    testbed=runtime.testbed
)
task.start()  # Fork subprocess
task.wait(21600)  # Pass timeout to wait(), not Task()
result = task.result
```

---

## What We Should Do

### Option 1: Revert to run() (safe, slower)

```python
# OLD: 2m 55s (subprocess overhead)
from pyats.easypy import run

for test_file in TEST_FILES:
    run(
        testscript=test_file,
        taskid=test_name,
        max_runtime=21600,  # Timeout WORKS
        testbed=runtime.testbed
    )
```

**Pros:** Timeout works, isolation works, safe
**Cons:** 45.4% slower (subprocess overhead)

---

### Option 2: Keep task.run() with wrapper timeout

```python
# NEW: 1m 35s (no subprocess, manual timeout)
import signal
from pyats.easypy import Task

def timeout_handler(signum, frame):
    raise TimeoutError("Test execution timed out")

for test_file in TEST_FILES:
    task = Task(testscript=test_file, taskid=test_name, testbed=runtime.testbed)
    
    # Set timeout using signal.alarm (UNIX only)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(21600)  # 6 hours
    
    try:
        task.run()  # Execute inline
    finally:
        signal.alarm(0)  # Cancel alarm
```

**Pros:** Fast (no subprocess), timeout works
**Cons:** 
- UNIX only (signal.alarm not on Windows)
- More complex error handling
- No process isolation (crash kills parent)

---

### Option 3: Use threading.Timer for cross-platform timeout

```python
import threading
from pyats.easypy import Task

for test_file in TEST_FILES:
    task = Task(testscript=test_file, taskid=test_name, testbed=runtime.testbed)
    
    # Create timeout thread
    timeout_event = threading.Event()
    
    def run_with_timeout():
        task.run()
        timeout_event.set()
    
    thread = threading.Thread(target=run_with_timeout)
    thread.daemon = True
    thread.start()
    
    # Wait with timeout
    if not timeout_event.wait(timeout=21600):
        # Timeout occurred - thread is still running
        # Cannot kill thread in Python, but can log and continue
        logger.error(f"Test {test_name} timed out after 6 hours")
        # Thread continues running in background (leaked)
```

**Pros:** Cross-platform, timeout detection
**Cons:**
- Cannot kill running thread in Python
- Leaked threads if timeout occurs
- Complex

---

### Option 4: Hybrid approach - subprocess for D2D only

```python
# Fast for API tests (no timeout risk)
for api_test in API_TESTS:
    task = Task(testscript=api_test, ...)
    task.run()  # Inline execution

# Safe for D2D tests (SSH can hang)
for d2d_test in D2D_TESTS:
    run(
        testscript=d2d_test,
        max_runtime=21600  # Timeout protection
    )
```

**Pros:** Balance speed and safety
**Cons:** Two execution paths, more complexity

---

## Recommendation

**Given the timeout risk**, we should:

1. **Measure timeout frequency** - How often do tests actually timeout?
2. **If rare:** Keep task.run() with signal.alarm timeout
3. **If common:** Revert to run() for safety

**For now:** Document the risk and monitor for hangs in production.

---

## References

- PyATS source: `~/Documents/Test-Automation/pyats-repo/pkgs/easypy-pkg/src/pyats/easypy/tasks.py`
- Task class: Line 182
- Task.run() method: Line 356 (subprocess entry point)
- Task.wait() method: Line 486 (timeout enforcement)
- run() function: Line 547 (recommended API)
