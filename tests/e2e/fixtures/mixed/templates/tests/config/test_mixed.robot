*** Test Cases ***
Robot Test That Passes
    [Documentation]    This test always passes
    Log    This test is designed to pass
    Should Be Equal    1    1    msg=Test passes

Robot Test That Fails
    [Documentation]    This test always fails
    Log    This test is designed to fail
    Fail    Intentional failure for mixed results testing
