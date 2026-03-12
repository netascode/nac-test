*** Settings ***
Documentation    Robot Framework test that always fails

*** Test Cases ***
{% for site in sdwan.sites %}
{% for router in site.routers %}

Robot Test {{ router.device_variables.system_hostname }} Fails
    [Documentation]    Test for device {{ router.device_variables.system_hostname }} - always fails
    Log    Testing device: {{ router.device_variables.system_hostname }}
    Fail    Intentional failure for testing failure scenarios

{% endfor %}
{% endfor %}
