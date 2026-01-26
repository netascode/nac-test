*** Test Cases ***
{% for site in sdwan.sites %}
{% for router in site.routers %}

Robot Test {{ router.device_variables.system_hostname}}
    Log    Device Name is {{ router.device_variables.system_hostname}}
    Should Be Equal    1    1

{% endfor %}
{% endfor %}
