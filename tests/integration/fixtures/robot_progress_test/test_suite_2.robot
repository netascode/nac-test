*** Settings ***
Documentation   Test Suite 2 - For testing parallel execution

*** Test Cases ***
Suite 2 Test Case 1 - Pass
    [Documentation]    First test in suite 2
    Log    Suite 2 Test 1 is executing
    Should Be Equal    2    2
    Sleep    0.1s

Suite 2 Test Case 2 - Pass
    [Documentation]    Second test in suite 2
    Log    Suite 2 Test 2 is executing
    Should Be Equal    world    world
    Sleep    0.1s

Suite 2 Test Case 3 - Pass
    [Documentation]    Third test in suite 2
    Log    Suite 2 Test 3 is executing
    Should Be True    1 < 2
    Sleep    0.1s

Suite 2 Test Case 4 - Pass
    [Documentation]    Fourth test in suite 2
    Log    Suite 2 Test 4 is executing
    Should Not Be Equal    a    b
    Sleep    0.1s
