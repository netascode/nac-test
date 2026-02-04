*** Settings ***
Library    String

*** Test Cases ***
{% for site in sdwan.sites %}
{% for router in site.routers %}

Robot Framework Test {{ router.device_variables.system_hostname }}
    [Documentation]    Test controlled by SHOULD_FAIL variable
    ...                SHOULD_FAIL=false → test passes (default)
    ...                SHOULD_FAIL=true → test fails
    ${should_fail}=    Get Variable Value    ${SHOULD_FAIL}    false
    Log    SHOULD_FAIL variable is: ${should_fail}
    Log    Testing device: {{ router.device_variables.system_hostname }}
    Run Keyword If    '${should_fail}' == 'true'
    ...    Fail    Intentional failure: SHOULD_FAIL variable is set to true
    ...    ELSE
    ...    Log    Test passes: SHOULD_FAIL variable is false or not set

{% endfor %}
{% endfor %}
