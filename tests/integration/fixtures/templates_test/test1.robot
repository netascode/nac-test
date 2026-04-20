*** Settings ***
Documentation   Test1

*** Test Cases ***
{% for child in root.children | default([]) %}

Test {{ child.name }}
    Should Be Equal   {{ child.param }}   value
    Log    tag={{ child.tag }}
    Log    items={{ child.items }}
    Log    keys={{ child.keys }}
{% endfor %}
