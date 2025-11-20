*** Settings ***
Documentation   Test Suite 3 - For testing parallel execution

*** Test Cases ***
Suite 3 Test Case 1 - Pass
    [Documentation]    First test in suite 3
    Log    Suite 3 Test 1 is executing
    Should Be Equal    3    3
    Sleep    0.1s

Suite 3 Test Case 2 - Pass
    [Documentation]    Second test in suite 3
    Log    Suite 3 Test 2 is executing
    Should Contain    Robot Framework    Robot
    Sleep    0.1s

Suite 3 Test Case 3 - Pass
    [Documentation]    Third test in suite 3
    Log    Suite 3 Test 3 is executing
    Should Be True    ${True}
    Sleep    0.1s
