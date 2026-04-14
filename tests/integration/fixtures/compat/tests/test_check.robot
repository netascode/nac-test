*** Settings ***
Documentation   Compat shim check

*** Test Cases ***
{% for child in root.children | default([]) %}

Check {{ child.name }}
    Should Be Equal   {{ child.param }}   value
{% endfor %}
