# -*- coding: utf-8 -*-

"""Generic base test class for all architectures."""

from pyats import aetest
import os
import yaml
from pathlib import Path
from typing import Any, Dict

from nac_test.pyats.common.connection_pool import ConnectionPool
from nac_test.pyats.common.retry_strategy import SmartRetry


class NACTestBase(aetest.Testcase):
    """Generic base class with common functionality for all architectures"""
    
    @aetest.setup
    def setup(self):
        """Common setup - load data model"""
        # Load merged data model created by nac-test
        self.data_model = self.load_data_model()
        
        # Get controller details from environment
        self.controller_type = os.environ.get('CONTROLLER_TYPE', 'ACI')
        self.controller_url = os.environ[f'{self.controller_type}_URL']
        self.username = os.environ[f'{self.controller_type}_USERNAME']
        self.password = os.environ[f'{self.controller_type}_PASSWORD']
        
        # Connection pool is shared within process
        self.pool = ConnectionPool()
        
    def load_data_model(self) -> Dict[str, Any]:
        """Load the merged data model YAML file
        
        Returns:
            Dictionary containing the merged data model
        """
        # Look for the file in the current directory (where tests are run)
        data_file = Path('merged_data_model_test_variables.yaml')
        
        if not data_file.exists():
            raise FileNotFoundError(
                f"Data model file not found: {data_file.absolute()}"
            )
            
        with open(data_file, 'r') as f:
            return yaml.safe_load(f)
            
    async def api_call_with_retry(self, func, *args, **kwargs):
        """Standard API call with retry logic
        
        Args:
            func: Async function to execute with retry
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from successful function execution
        """
        return await SmartRetry.execute(func, *args, **kwargs) 