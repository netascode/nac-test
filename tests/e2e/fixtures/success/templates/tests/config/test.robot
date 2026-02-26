*** Settings ***
Documentation    Robot Framework test that always passes

*** Test Cases ***
{% for site in sdwan.sites %}
{% for router in site.routers %}

Robot Test {{ router.device_variables.system_hostname }} Passes
    [Documentation]    Test for device {{ router.device_variables.system_hostname }} - always passes
    Log    Testing device: {{ router.device_variables.system_hostname }}
    Should Be Equal    1    1    msg=Test passes as expected

{% endfor %}
{% endfor %}
