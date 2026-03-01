*** Test Cases ***
Verify Debug Log Level Is Active
    ${previous_level}=    Set Log Level    INFO
    Should Be Equal    ${previous_level}    %{EXPECTED_ROBOT_LOG_LEVEL}
    Reset Log Level
