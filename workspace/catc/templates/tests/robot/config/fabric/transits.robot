*** Settings ***
Documentation     Verify Transit Networks
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   transits

*** Test Cases ***

Get Transit Networks
    ${r}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/transitNetworks
    ${d}=   GET On Session   CatalystCenter_Session   /dna/data/api/v1/networkDevices
    Log   Response Status Code (Transit Networks): ${r.status_code}
    Log   Response Status Code (Network Devices): ${d.status_code}
    Log To Console   Transit Networks API Response: ${r.json()}
    Set Suite Variable   ${r}
    Set Suite Variable   ${d}

{% for transit in catalyst_center.fabric.transits | default([]) %}
Verify Transit {{ transit.name }}

    # Validate that the transit exists in the API response
    ${transit_data}=   Get Value From Json   ${r.json()}   $.response[?(@.name=='{{ transit.name }}')]
    Log To Console   Transit data: ${transit_data}
    Run Keyword If   not ${transit_data}   Fail   Transit {{ transit.name }} not found in Transit Networks API response.

    # Extract the matching transit
    ${t}=   Set Variable   ${transit_data}[0]
    Log To Console   Extracted Transit Entry: ${t}

    # Validate basic transit attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.name   {{ transit.name }}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.type   {{ transit.type | default(defaults.catalyst_center.fabric.transits.type) }}

{% if transit.type | default(defaults.catalyst_center.fabric.transits.type) == 'IP_BASED_TRANSIT' %}
    # Validate IP Transit Settings
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.ipTransitSettings.routingProtocolName   {{ transit.routing_protocol_name | default(defaults.catalyst_center.fabric.transits.routing_protocol_name) }}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.ipTransitSettings.autonomousSystemNumber   {{ transit.autonomous_system_number | default(defaults.catalyst_center.fabric.transits.autonomous_system_number) }}

{% elif transit.type | default(defaults.catalyst_center.fabric.transits.type) in ['SDA_LISP_PUB_SUB_TRANSIT', 'SDA_LISP_BGP_TRANSIT'] %}
    # Validate SDA Transit Settings
{% if transit.control_plane_devices is defined %}
    # Map device IDs to device names and validate
    ${device_ids_result}=   Get Value From Json   ${t}   $.sdaTransitSettings.controlPlaneNetworkDeviceIds
    ${device_ids}=   Set Variable   ${device_ids_result}[0]
    ${actual_device_names}=   Create List
    ${actual_device_hostnames}=   Create List
    FOR   ${device_id}   IN   @{device_ids}
        ${device_data}=   Get Value From Json   ${d.json()}   $.response[?(@.id=='${device_id}')]
        Run Keyword If   not ${device_data}   Fail   Device ID ${device_id} not found in network devices API response.
        ${device_entry}=   Set Variable   ${device_data}[0]
        ${device_name}=   Get From Dictionary   ${device_entry}   name
        Append To List   ${actual_device_names}   ${device_name}
        # Extract hostname by splitting on first dot
        ${hostname}=   Evaluate   "${device_name}".split('.')[0]
        Append To List   ${actual_device_hostnames}   ${hostname}
    END
    
    Log To Console   Control plane devices - Expected: {{ transit.control_plane_devices | join(', ') }}, Actual: ${actual_device_names}, Hostnames: ${actual_device_hostnames}
    
    # Validate each expected device name is present (check both FQDN and hostname)
{% for expected_device in transit.control_plane_devices %}
    # Handle both string and object formats for device references
    {% if expected_device is string %}
    # Simple string format - check against both full names and hostnames
    ${device_found_fqdn}=   Run Keyword And Return Status   List Should Contain Value   ${actual_device_names}   {{ expected_device }}
    ${device_found_hostname}=   Run Keyword And Return Status   List Should Contain Value   ${actual_device_hostnames}   {{ expected_device }}
    ${device_found}=   Evaluate   ${device_found_fqdn} or ${device_found_hostname}
    Run Keyword If   not ${device_found}   Fail   Device {{ expected_device }} not found in control plane devices list: ${actual_device_names} (hostnames: ${actual_device_hostnames})
    {% else %}
    # Object format with potential name/fqdn_name attributes
    ${expected_name}=   Set Variable   {{ expected_device.name | default(expected_device) }}
    ${device_found_by_name_fqdn}=   Run Keyword And Return Status   List Should Contain Value   ${actual_device_names}   ${expected_name}
    ${device_found_by_name_hostname}=   Run Keyword And Return Status   List Should Contain Value   ${actual_device_hostnames}   ${expected_name}
    ${device_found_by_name}=   Evaluate   ${device_found_by_name_fqdn} or ${device_found_by_name_hostname}
    
        {% if expected_device.fqdn_name is defined %}
    ${device_found_by_fqdn}=   Run Keyword And Return Status   List Should Contain Value   ${actual_device_names}   {{ expected_device.fqdn_name }}
    ${device_found}=   Evaluate   ${device_found_by_name} or ${device_found_by_fqdn}
    Run Keyword If   not ${device_found}   Fail   Device {{ expected_device.name | default(expected_device) }} or {{ expected_device.fqdn_name }} not found in control plane devices list: ${actual_device_names} (hostnames: ${actual_device_hostnames})
        {% else %}
    Run Keyword If   not ${device_found_by_name}   Fail   Device ${expected_name} not found in control plane devices list: ${actual_device_names} (hostnames: ${actual_device_hostnames})
        {% endif %}
    {% endif %}
{% endfor %}
{% endif %}

{% if transit.type | default(defaults.catalyst_center.fabric.transits.type) == 'SDA_LISP_PUB_SUB_TRANSIT' %}
    # Validate multicast over transit setting
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.sdaTransitSettings.isMulticastOverTransitEnabled   {{ transit.multicast_over_sda_transit | default(defaults.catalyst_center.fabric.transits.multicast_over_sda_transit) }}
{% endif %}

{% endif %}

{% endfor %}
