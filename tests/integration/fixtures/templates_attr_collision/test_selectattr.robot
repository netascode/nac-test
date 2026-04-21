*** Settings ***
Documentation   Test selectattr/rejectattr/map(attribute=) with collision keys like 'tag'

*** Test Cases ***
Test selectattr with tag key
    {% set trunk_ports = root.fabric.spine.interfaces | selectattr('tag', 'equalto', 'trunk') | list %}
    Should Be Equal    {{ trunk_ports | length }}    1    msg=selectattr_count
    Should Be Equal    {{ trunk_ports[0].name }}    Ethernet1/1    msg=selectattr_name

Test rejectattr with tag key
    {% set non_trunk = root.fabric.spine.interfaces | rejectattr('tag', 'equalto', 'trunk') | list %}
    Should Be Equal    {{ non_trunk | length }}    1    msg=rejectattr_count
    Should Be Equal    {{ non_trunk[0].name }}    Ethernet1/2    msg=rejectattr_name

Test map attribute extraction with collision key
    {% set all_tags = root.fabric.spine.interfaces | map(attribute='tag') | list %}
    Should Be Equal    {{ all_tags | join(',') }}    trunk,access    msg=map_tags
