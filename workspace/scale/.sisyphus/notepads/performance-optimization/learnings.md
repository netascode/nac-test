# Performance Optimization Learnings - February 7, 2026

## Key Findings: Subprocess Spawning
- The primary bottleneck in D2D test execution is the sequential spawning of PyATS subprocesses.
- Each device spawns one PyATS job subprocess, but inside that job, 11 separate `pyats.easypy.run()` calls are made.
- Each `run()` call adds approximately 11 seconds of overhead due to subprocess creation.
- Total overhead per device: 11 tests * 11s = 121 seconds.

## PyATS Framework Limitations
- Research into PyATS source code (`tasks.py:182`) confirms that `Task` inherits from `multiprocessing.Process`.
- The `run()` function always instantiates a `Task` and calls `task.start()`, which forks a new subprocess.
- There is no built-in mechanism in PyATS to batch multiple testscripts into a single subprocess.

## Optimization Strategy Decisions
- **Decision:** Consolidate test files and use parallel workers.
- **Rationale:** Merging test files reduces the number of `run()` calls, eliminating the majority of the 121s overhead. Adding `runtime.max_workers` allows parallel execution within the remaining subprocesses.
- **Target:** Reducing per-device execution from ~120s to ~20s to meet the 30-second total runtime target.

## PyATS Source Evidence (tasks.py)
```python
# tasks.py:182-191
class Task(multiprocessing.Process):
    '''Each task runs in its own forked subprocess'''
    
# tasks.py:153-179  
def run(*args, **kwargs):
    task = Task(*args, **kwargs)  # Creates multiprocessing.Process
    task.start()                  # Forks subprocess - NO WAY TO AVOID THIS
    task.wait()
    return task.result
```
