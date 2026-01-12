"""Empty test file with no classes.

This fixture tests the edge case of a Python file that imports
modules but defines no test classes. The resolver should raise
NoRecognizedBaseError and fall back to directory detection.
"""

# Just imports, no test classes
