{# iterate_list_chunked root.children name child_name children 5 #}
*** Settings ***
Documentation   Test1

*** Test Cases ***
{% for child in root.children | default([]) %}
{% if child.name == child_name %}

Test {{ child.name }}
    Should Be Equal   {{ child.param }}   value

{% for nested_child in child.children | default([]) %}

Test {{ child.name }} Child {{ nested_child.name }}
    Should Be Equal   {{ nested_child.param }}   value
{% endfor %}

{% endif %}
{% endfor %}
