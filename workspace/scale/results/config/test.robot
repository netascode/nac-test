*** Settings ***
Documentation    Robot Framework test that always passes

*** Test Cases ***

Robot Test sd-dc-c8kv-01 Passes
    [Documentation]    Test for device sd-dc-c8kv-01 - always passes
    Log    Testing device: sd-dc-c8kv-01
    Should Be Equal    1    1    msg=Test passes as expected

#Failing Test
#    Fail    supposed to fail