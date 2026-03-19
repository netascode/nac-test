*** Settings ***
Documentation     Verify Device Inventory in Catalyst Center
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   inventory   devices

*** Test Cases ***

Get Device Inventory
    ${r}=   Get Cached Network Devices Data
    Log     Response Status Code: ${r.status_code}
    Log To Console   API Response: ${r.json()}
    Set Suite Variable   ${r}

Get Device Tags
    ${tags_response}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/tags/networkDevices/membersAssociations
    Log   Response Status Code (Device Tags): ${tags_response.status_code}
    Log To Console   Device Tags API Response: ${tags_response.json()}
    Set Suite Variable   ${DEVICE_TAGS_RESPONSE}   ${tags_response}

{% for device in catalyst_center.inventory.devices | default([]) %}
Verify Device {{ device.name }}
    Run Keyword If   '{{ device.state | default('') }}' == 'PNP'   Pass Execution   Skipping further steps as device is in PNP process
    Run Keyword If   '{{ device.state | default('') }}' == 'INIT'   Pass Execution   Skipping further steps as device is in INIT state

    # Validate that the device exists in the API response
    ${device_data}=   Get Value From Json   ${r.json()}   $.response[?(@.name=='{{ device.name }}')]
    ${device_data}=   Run Keyword If   ${device_data} == []   Get Value From Json   ${r.json()}   $.response[?(@.name=='{{ device.fqdn_name }}')]   ELSE   Set Variable   ${device_data}

    Run Keyword If    not ${device_data}    Fail    Device {{ device.name }} or {{ device.fqdn_name }} not found in API response.

    # Extract the first matching device from the API response
    ${device_entry}=   Set Variable   ${device_data}[0]
    Log To Console   Extracted Device Entry: ${device_entry}

    # Validate device attributes
    ${name_matches}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_entry['name']}   {{ device.name }}
    Run Keyword If   not ${name_matches}   Should Be Equal As Strings   ${device_entry['name']}   {{ device.fqdn_name }}
    Should Be Equal As Strings   ${device_entry['managementIpAddress']}   {{ device.device_ip }}
    Should Be Equal As Strings   ${device_entry['platformId'].split(',')[0].strip()}    {{ device.pid }}

    Should Be Equal As Strings   ${device_entry['deviceRole']}   {{ device.device_role }}
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.id=='${device_entry['siteId']}')]
    ${site_entry}=   Set Variable   ${site_data}[0]
    Log To Console   Extracted stedata: ${site_entry}

    Should Be Equal As Strings   ${site_entry['nameHierarchy']}   {{ device.site }}

    # Validate device tags if defined in data model
    {% if device.tags is defined and device.tags | length > 0 %}
    ${device_id}=   Get From Dictionary   ${device_entry}   id
    ${device_tags_data}=   Get Value From Json   ${DEVICE_TAGS_RESPONSE.json()}   $.response[?(@.id=='${device_id}')]
    ${device_tags_count}=   Get Length   ${device_tags_data}
    Run Keyword If   ${device_tags_count} == 0   Fail   Expected tags {{ device.tags }} but device {{ device.name }} has no tags in API response
    
    ${api_tags}=   Set Variable   ${device_tags_data[0].get('tags', [])}
    ${expected_tags}=   Create List{% for tag in device.tags %}   {{ tag }}{% endfor %}

    FOR   ${expected_tag}   IN   @{expected_tags}
        ${tag_found}=   Set Variable   ${False}
        FOR   ${api_tag}   IN   @{api_tags}
            ${tag_name}=   Get From Dictionary   ${api_tag}   name
            ${match}=   Evaluate   '${tag_name}' == '${expected_tag}'
            IF   ${match}
                ${tag_found}=   Set Variable   ${True}
            END
        END
        Run Keyword If   not ${tag_found}   Fail   Tag '${expected_tag}' not found for device {{ device.name }}. API tags: ${api_tags}
    END
    {% endif %}
{% endfor %}
