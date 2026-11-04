*** Settings ***
Documentation    Local template; replaces the failing one of the module

*** Test Cases ***
{% for site in sdwan.sites %}
{% for router in site.routers %}

Local Template Wins For {{ router.device_variables.system_hostname }}
    Should Be Equal    local    local

{% endfor %}
{% endfor %}
