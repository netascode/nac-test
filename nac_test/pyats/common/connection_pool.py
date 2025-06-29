# -*- coding: utf-8 -*-

"""Generic connection pooling for HTTP connections."""

import threading
import httpx
from typing import Dict, Optional


class ConnectionPool:
    """Shared connection pool for all API tests in a process
    
    Generic pool that can be used by any architecture for HTTP connections
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'limits'):
            self.limits = httpx.Limits(
                max_connections=200,
                max_keepalive_connections=50,
                keepalive_expiry=300
            )
    
    def get_client(self, 
                  headers: Optional[Dict[str, str]] = None,
                  timeout: Optional[httpx.Timeout] = None,
                  verify: bool = True) -> httpx.AsyncClient:
        """Get an async HTTP client with custom headers and timeout
        
        Args:
            headers: Optional headers dict (architecture-specific)
            timeout: Optional timeout settings
            verify: SSL verification flag
        
        Returns:
            Configured httpx.AsyncClient instance
        """
        if timeout is None:
            timeout = httpx.Timeout(30.0)
            
        return httpx.AsyncClient(
            limits=self.limits,
            headers=headers or {},
            timeout=timeout,
            verify=verify
        ) 