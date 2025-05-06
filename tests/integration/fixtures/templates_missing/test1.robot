*** Settings ***
Documentation   Test1

*** Test Cases ***
*** Test Cases ***
Test {{ root.missing }}
    Should Be Equal   {{ root.missing }}   fail
