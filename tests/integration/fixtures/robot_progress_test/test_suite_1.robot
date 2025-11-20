*** Settings ***
Documentation   Test Suite 1 - For testing parallel execution

*** Test Cases ***
Suite 1 Test Case 1 - Pass
    [Documentation]    First test in suite 1
    Log    Suite 1 Test 1 is executing
    Should Be Equal    1    1
    Sleep    0.1s

Suite 1 Test Case 2 - Pass
    [Documentation]    Second test in suite 1
    Log    Suite 1 Test 2 is executing
    Should Be Equal    hello    hello
    Sleep    0.1s

Suite 1 Test Case 3 - Fail
    [Documentation]    Test that should fail
    [Tags]    expected_fail
    Log    Suite 1 Test 3 is executing
    Should Be Equal    1    2

Suite 1 Test Case 4 - Pass
    [Documentation]    Fourth test in suite 1
    Log    Suite 1 Test 4 is executing
    Should Not Be Equal    1    2
    Sleep    0.1s
