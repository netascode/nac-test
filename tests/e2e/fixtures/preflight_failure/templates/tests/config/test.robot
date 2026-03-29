*** Settings ***
Documentation    Robot Framework test for the pre-flight failure scenario. — Ü ö 日本語
...              Verifies that Robot tests still run when ACI pre-flight auth fails.

*** Test Cases ***
Robot Test Passes Despite Pre-Flight Failure
    [Documentation]    This test always passes. It verifies that Robot Framework
    ...                execution continues even after a controller auth pre-flight failure.
    Log    Pre-flight auth failure did not prevent Robot from running
    Should Be Equal    1    1    msg=Robot execution was not interrupted by pre-flight failure
