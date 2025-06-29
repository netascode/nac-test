# -*- coding: utf-8 -*-

"""Main PyATS orchestration logic for nac-test."""

import multiprocessing as mp
from pathlib import Path
import psutil
import os
from typing import List
import logging
import subprocess
import tempfile
import textwrap

from .constants import *
from .progress_reporter import ProgressReporter
from nac_test.data_merger import DataMerger

logger = logging.getLogger(__name__)

class PyATSOrchestrator:
    """Orchestrates PyATS test execution with dynamic resource management."""
    
    def __init__(self, data_paths: List[Path], test_dir: Path, output_dir: Path, 
                 merged_data_filename: str):
        """Initialize the PyATS orchestrator.
        
        Args:
            data_paths: List of paths to data model YAML files
            test_dir: Directory containing PyATS test files
            output_dir: Directory for test output
            merged_data_filename: Name of the merged data model file
        """
        self.data_paths = data_paths
        self.test_dir = Path(test_dir)
        self.output_dir = Path(output_dir)
        self.merged_data_filename = merged_data_filename
        self.max_workers = self._calculate_workers()
        self.progress_reporter = ProgressReporter()
        
    def _calculate_workers(self) -> int:
        """Calculate optimal worker count based on CPU and memory"""
        # CPU-based calculation
        cpu_workers = mp.cpu_count() * DEFAULT_CPU_MULTIPLIER
        
        # Memory-based calculation
        available_memory = psutil.virtual_memory().available
        # Convert from bytes to GB
        memory_workers = int(available_memory / (MEMORY_PER_WORKER_GB * 1024 * 1024 * 1024))
        
        # Consider system load
        load_avg = os.getloadavg()[0]  # 1-minute load average
        if load_avg > mp.cpu_count():
            cpu_workers = max(1, int(cpu_workers * 0.5))  # Reduce if system is loaded
        
        # Use the more conservative limit
        actual_workers = max(1, min(cpu_workers, memory_workers, MAX_WORKERS_HARD_LIMIT))
        
        # Allow override via environment variable
        return int(os.environ.get('PYATS_MAX_WORKERS', actual_workers))
    
    def discover_pyats_tests(self) -> List[Path]:
        """Find all .py test files when --pyats flag is set
        
        Searches for Python test files in the standard test directories:
        - */test/config/
        - */test/operational/
        - */test/health/
        
        This mirrors the Robot Framework test structure while excluding
        utility directories like pyats_common and jinja_filters.
        """
        test_files = []
        
        # Use rglob for recursive search - finds .py files at any depth
        for test_path in self.test_dir.rglob("*.py"):
            # Skip non-test files
            if '__pycache__' in str(test_path):
                continue
            if test_path.name.startswith('_'):
                continue
            if test_path.name == '__init__.py':
                continue
            
            # Convert to string for efficient path checking
            path_str = str(test_path)
            
            # Only include files in the standard test directories
            if ('/test/config/' in path_str or 
                '/test/operational/' in path_str or 
                '/test/health/' in path_str):
                
                # Exclude utility directories
                if ('pyats_common' not in path_str and 
                    'jinja_filters' not in path_str):
                    test_files.append(test_path)
        
        return sorted(test_files)
    
    def _generate_job_file_content(self, test_files: List[Path]) -> str:
        """Generate the content for a PyATS job file"""
        # Convert test file paths to strings for the job file
        test_files_str = ',\n        '.join([f'"{str(tf)}"' for tf in test_files])
        
        job_content = textwrap.dedent(f'''
        """Auto-generated PyATS job file by nac-test"""
        
        import os
        from pathlib import Path
        
        # Test files to execute
        TEST_FILES = [
            {test_files_str}
        ]
        
        def main(runtime):
            """Main job file entry point"""
            # Set max workers
            runtime.max_workers = {self.max_workers}
            
            # Note: runtime.directory is read-only and set by --archive-dir
            # The output directory is: {str(self.output_dir)}
            
            # Run all test files
            for idx, test_file in enumerate(TEST_FILES):
                runtime.tasks.run(
                    testscript=test_file,
                    taskid=f"test_{{idx}}",
                    max_runtime={DEFAULT_TEST_TIMEOUT}
                )
        ''')
        
        return job_content
        
    def run_tests(self) -> None:
        """Main entry point from nac-test CLI"""
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Merge data files and write to output directory for tests to access
        merged_data = DataMerger.merge_data_files(self.data_paths)
        DataMerger.write_merged_data_model(merged_data, self.output_dir, self.merged_data_filename)
        
        # Discover test files
        test_files = self.discover_pyats_tests()
        
        if not test_files:
            print("No PyATS test files (*.py) found in test directory")
            return
        
        print(f"Discovered {len(test_files)} PyATS test files")
        print(f"Running with {self.max_workers} parallel workers")
        
        # Generate job file content
        job_content = self._generate_job_file_content(test_files)
        
        # Create temporary job file
        with tempfile.NamedTemporaryFile(mode='w', suffix='_job.py', delete=False) as f:
            f.write(job_content)
            job_file = f.name
        
        try:
            # Build PyATS command
            cmd = [
                'pyats', 'run', 'job', job_file,
                '--archive-dir', str(self.output_dir),
                '--no-mail'  # Disable email notifications
            ]
            
            # Set up environment to suppress warnings and set PYTHONPATH
            env = os.environ.copy()
            env['PYTHONWARNINGS'] = 'ignore::UserWarning'
            
            # Add the test directory to PYTHONPATH so imports work
            # This allows "from pyats_common.<architecture>_base_test import <ARCHITECTURE>TestBase" to work
            test_parent_dir = str(self.test_dir)
            if 'PYTHONPATH' in env:
                env['PYTHONPATH'] = f"{test_parent_dir}{os.pathsep}{env['PYTHONPATH']}"
            else:
                env['PYTHONPATH'] = test_parent_dir
            
            # Run PyATS as subprocess
            print(f"Executing PyATS with command: {' '.join(cmd)}")
            result = subprocess.run(cmd, env=env, cwd=str(self.output_dir))
            
            if result.returncode != 0:
                logger.error(f"PyATS execution failed with return code: {result.returncode}")
            else:
                print("PyATS execution completed successfully")
                
        finally:
            # Clean up temporary job file
            os.unlink(job_file) 