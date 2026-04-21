*** Settings ***
Documentation   Test collision key access via bracket notation and non-collision dot access

*** Test Cases ***
{% for child in root.children | default([]) %}

Test {{ child.name }}
    Should Be Equal   {{ child.param }}   value   msg=param_{{ child.name }}
    Should Be Equal   {{ child.tag | default(defaults.tag) }}   {% if child.name == 'abc' %}100{% else %}fallback{% endif %}   msg=tag_{{ child.name }}
    # 'items' and 'keys' collide with dict method names — dot access (child.items)
    # would resolve to the dict method, not the YAML key value. Use bracket notation.
    Should Be Equal   {{ child['items'] }}   foo   msg=items_key_{{ child.name }}
    Should Be Equal   {{ child['keys'] }}   bar   msg=keys_key_{{ child.name }}
{% endfor %}
