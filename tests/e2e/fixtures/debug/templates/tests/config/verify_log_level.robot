*** Test Cases ***
Verify Log Level
    [Documentation]    Verifies log level set to the value in env var EXPECTED_ROBOT_LOG_LEVEL (set by fixture)
    ${previous_level}=    Set Log Level    INFO
    Should Be Equal    ${previous_level}    %{EXPECTED_ROBOT_LOG_LEVEL}
    Reset Log Level
