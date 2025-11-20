*** Settings ***
Documentation   Test for validating NAC_PROGRESS event emission through pabot

*** Test Cases ***
Test Case 1 - Pass
    [Documentation]    Simple passing test
    Log    Test 1 is executing
    Should Be Equal    1    1

Test Case 2 - Pass
    [Documentation]    Another passing test
    Log    Test 2 is executing
    Should Be Equal    hello    hello

Test Case 3 - Fail
    [Documentation]    Test that should fail
    [Tags]    expected_fail
    Log    Test 3 is executing
    Should Be Equal    1    2

Test Case 4 - Pass
    [Documentation]    Final passing test
    Log    Test 4 is executing
    Should Not Be Equal    1    2
