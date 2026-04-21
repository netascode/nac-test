*** Settings ***
Documentation   Test1

*** Test Cases ***
{% for child in root.children | default([]) %}

Test {{ child.name }}
    Should Be Equal   {{ child.param }}   value
    Should Be Equal   {{ child.tag | default(defaults.tag) }}   {% if child.name == 'abc' %}100{% else %}fallback{% endif %}
    Should Be Equal   {{ child.items }}   foo
    Should Be Equal   {{ child.keys }}   bar
{% endfor %}
