*** Settings ***
Documentation    Bundle template importing a resource of the module by relative path
Resource    ../resources/common.resource

*** Test Cases ***
{% for site in sdwan.sites %}
{% for router in site.routers %}

Bundle Filter And Module Resource For {{ router.device_variables.system_hostname }}
    Layer Keyword From Module    {{ router.device_variables.system_hostname | layer_marker }}

{% endfor %}
{% endfor %}
