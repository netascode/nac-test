*** Test Cases ***
Verify Log Level
    [Documentation]    Verifies log level set to the value in env var EXPECTED_ROBOT_LOG_LEVEL (set by fixture)
    ${active_loglevel}=    Set Log Level    INFO
    Should Be Equal    ${active_loglevel}    %{EXPECTED_ROBOT_LOG_LEVEL}
    Reset Log Level
