*** Settings ***
Documentation   Test dict method calls (.items, .get, .keys, .values) on mappings without collision keys

*** Test Cases ***
{% for key, value in root.settings.items() %}
Test setting {{ key }}
    Log    {{ key }} = {{ value }}
{% endfor %}

Test get method with default
    Should Be Equal    {{ root.settings.get('hostname', 'unknown') }}    router1    msg=get_existing

Test get method missing key with default
    Should Be Equal    {{ root.settings.get('nonexistent', 'fallback_value') }}    fallback_value    msg=get_missing

Test keys method
    {% set setting_names = root.settings.keys() | list | sort %}
    Should Be Equal    {{ setting_names | join(',') }}    description,hostname,vlan_id    msg=keys_method

Test values method
    Should Be Equal    {{ root.settings.values() | list | length }}    3    msg=values_count
