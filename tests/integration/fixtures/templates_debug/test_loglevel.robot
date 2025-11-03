*** Test Cases ***
Test for DEBUG loglevel
    ${current_loglevel}=   Set Log Level   INFO
    Should Be Equal    ${current_loglevel}    DEBUG
    ...    msg=Log level is not set to DEBUG
