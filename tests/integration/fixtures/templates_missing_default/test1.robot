*** Settings ***
Documentation   Test1

*** Test Cases ***
Test 1
    Should Be Equal   {{ root.missing.abc | default("fail") }}   fail
