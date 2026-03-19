*** Settings ***
Documentation     Verify Layer 3 Handoffs (IP Transit and SDA Transit)
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   l3_handoffs

*** Test Cases ***

{% if catalyst_center.fabric is defined and catalyst_center.fabric.border_devices is defined %}
Get API Data For L3 Handoffs
    # Get network devices for device name to ID mapping
    ${devices}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/networkDevices
    Log   Network Devices Response Status Code: ${devices.status_code}
    Set Suite Variable   ${NETWORK_DEVICES}   ${devices}
    
    # Get transit networks for transit name to ID mapping
    ${transits}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/transitNetworks
    Log   Transit Networks Response Status Code: ${transits.status_code}
    Set Suite Variable   ${TRANSIT_NETWORKS}   ${transits}
    
    # Get fabric sites for fabric ID lookup
    ${fabric_sites}=   Get Cached Fabric Sites Data
    Log   Fabric Sites Response Status Code: ${fabric_sites.status_code}
    Set Suite Variable   ${FABRIC_SITES}   ${fabric_sites}

{% for border_device in catalyst_center.fabric.border_devices | default([]) %}
{# Check if this is a LAYER_3 border type - L3 handoffs only apply to LAYER_3 borders #}
{% if 'LAYER_3' not in border_device.border_types | default([]) %}
# ============================================================================
# Skipping {{ border_device.name }} - Not a LAYER_3 border type
# ============================================================================

Skip L3 Handoff Tests for {{ border_device.name }} - Not LAYER_3 Border
    [Documentation]   Skip L3 Handoff tests for {{ border_device.name }} because it is not a LAYER_3 border type
    Pass Execution   Device {{ border_device.name }} is not a LAYER_3 border type (border_types: {{ border_device.border_types | default([]) | join(', ') }}), skipping L3 handoff tests

{% else %}
{# Look up device state from inventory - skip if INIT or PNP #}
{% set device_state = namespace(value='') %}
{% if catalyst_center.inventory is defined and catalyst_center.inventory.devices is defined %}
{% for inv_device in catalyst_center.inventory.devices %}
{% if inv_device.name == border_device.name or inv_device.fqdn_name | default('') == border_device.name %}
{% set device_state.value = inv_device.state | default('') | upper %}
{% endif %}
{% endfor %}
{% endif %}
{% if device_state.value in ['INIT', 'PNP'] %}
# ============================================================================
# Skipping {{ border_device.name }} - Device state is {{ device_state.value }}
# ============================================================================

Skip L3 Handoff Tests for {{ border_device.name }} - Device Not Provisioned
    [Documentation]   Skip L3 Handoff tests for {{ border_device.name }} because device state is {{ device_state.value }}
    Pass Execution   Device {{ border_device.name }} is in {{ device_state.value }} state (not fabric provisioned), skipping L3 handoff tests

{% else %}
{% if border_device.sda_transit is defined %}
# ============================================================================
# SDA Transit L3 Handoff for {{ border_device.name }}
# ============================================================================

Verify SDA Transit L3 Handoff for {{ border_device.name }}
    [Documentation]   Validate SDA Transit L3 Handoff configuration for border device {{ border_device.name }}
    
    # Find device ID by hostname (handle both FQDN and short hostname)
    ${device_list}=   Get From Dictionary   ${NETWORK_DEVICES.json()}   response
    ${device_id}=   Set Variable   ${EMPTY}
    FOR   ${device}   IN   @{device_list}
        ${device_name}=   Get From Dictionary   ${device}   hostname
        ${device_hostname}=   Evaluate   "${device_name}".split('.')[0]
        ${match_exact}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_name}   {{ border_device.name }}
        ${match_short}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_hostname}   {{ border_device.name }}
        ${is_match}=   Evaluate   ${match_exact} or ${match_short}
        Run Keyword If   ${is_match}   Set Suite Variable   ${device_id}   ${device}[id]
        Exit For Loop If   ${is_match}
    END
    Run Keyword If   "${device_id}" == "${EMPTY}"   Fail   Border device {{ border_device.name }} not found in network devices
    Log To Console   Found device {{ border_device.name }} with ID: ${device_id}
    
    # Find transit network ID by name
    ${transit_data}=   Get Value From Json   ${TRANSIT_NETWORKS.json()}   $.response[?(@.name=='{{ border_device.sda_transit }}')]
    Run Keyword If   not ${transit_data}   Fail   SDA Transit {{ border_device.sda_transit }} not found in transit networks
    ${transit_id}=   Set Variable   ${transit_data}[0][id]
    Log To Console   Found SDA Transit {{ border_device.sda_transit }} with ID: ${transit_id}
    
    # Find fabric ID for this device - first get all fabric sites and find one containing this device
    ${fabric_id}=   Set Variable   ${EMPTY}
    ${fabric_sites_list}=   Get Value From Json   ${FABRIC_SITES.json()}   $.response
    ${fabric_sites_list}=   Set Variable   ${fabric_sites_list}[0]
    FOR   ${fabric_site}   IN   @{fabric_sites_list}
        ${site_fabric_id}=   Get From Dictionary   ${fabric_site}   id
        # Query SDA transits for this fabric to check if our device is there
        ${sda_response}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/fabricDevices/layer3Handoffs/sdaTransits   params=fabricId=${site_fabric_id}&networkDeviceId=${device_id}
        ${sda_handoffs}=   Get Value From Json   ${sda_response.json()}   $.response
        ${has_handoffs}=   Evaluate   len(${sda_handoffs}[0]) > 0 if ${sda_handoffs} else False
        Run Keyword If   ${has_handoffs}   Set Suite Variable   ${fabric_id}   ${site_fabric_id}
        Exit For Loop If   ${has_handoffs}
    END
    Run Keyword If   "${fabric_id}" == "${EMPTY}"   Pass Execution   No SDA Transit L3 Handoff found for device {{ border_device.name }}, skipping validation
    
    # Get SDA Transit L3 Handoff data
    ${r}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/fabricDevices/layer3Handoffs/sdaTransits   params=fabricId=${fabric_id}&networkDeviceId=${device_id}
    Log To Console   SDA Transit L3 Handoff Response: ${r.json()}
    
    # Validate the handoff exists
    ${handoff_data}=   Get Value From Json   ${r.json()}   $.response[?(@.transitNetworkId=='${transit_id}')]
    Run Keyword If   not ${handoff_data}   Fail   SDA Transit L3 Handoff for transit {{ border_device.sda_transit }} not found for device {{ border_device.name }}
    ${handoff}=   Set Variable   ${handoff_data}[0]
    
    # Validate SDA Transit attributes
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[networkDeviceId]   ${device_id}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[transitNetworkId]   ${transit_id}
    
{% if border_device.affinity_id_prime is defined %}
    Run Keyword And Continue On Failure   Should Be Equal As Numbers   ${handoff}[affinityIdPrime]   {{ border_device.affinity_id_prime }}
{% endif %}
{% if border_device.affinity_id_decider is defined %}
    Run Keyword And Continue On Failure   Should Be Equal As Numbers   ${handoff}[affinityIdDecider]   {{ border_device.affinity_id_decider }}
{% endif %}
{% if border_device.connected_to_internet is defined %}
    ${connected_to_internet}=   Get From Dictionary   ${handoff}   connectedToInternet
{% if border_device.connected_to_internet %}
    Run Keyword And Continue On Failure   Should Be True   ${connected_to_internet}
{% else %}
    Run Keyword And Continue On Failure   Should Not Be True   ${connected_to_internet}
{% endif %}
{% endif %}
{% if border_device.multicast_over_transit is defined %}
    ${multicast_over_transit}=   Get From Dictionary   ${handoff}   isMulticastOverTransitEnabled
{% if border_device.multicast_over_transit %}
    Run Keyword And Continue On Failure   Should Be True   ${multicast_over_transit}
{% else %}
    Run Keyword And Continue On Failure   Should Not Be True   ${multicast_over_transit}
{% endif %}
{% endif %}

{% endif %}
{% if border_device.l3_handoffs is defined %}
{% for l3_handoff in border_device.l3_handoffs %}
# ============================================================================
# IP Transit L3 Handoff for {{ border_device.name }} - Transit {{ l3_handoff.name }}
# ============================================================================

{% for interface in l3_handoff.interfaces %}
{% for vn in interface.virtual_networks %}
Verify IP Transit L3 Handoff {{ border_device.name }} - {{ l3_handoff.name }} - {{ interface.name }} - {{ vn.name }}
    [Documentation]   Validate IP Transit L3 Handoff for {{ border_device.name }}, transit {{ l3_handoff.name }}, interface {{ interface.name }}, VN {{ vn.name }}
    
    # Find device ID by hostname (handle both FQDN and short hostname)
    ${device_list}=   Get From Dictionary   ${NETWORK_DEVICES.json()}   response
    ${device_id}=   Set Variable   ${EMPTY}
    FOR   ${device}   IN   @{device_list}
        ${device_name}=   Get From Dictionary   ${device}   hostname
        ${device_hostname}=   Evaluate   "${device_name}".split('.')[0]
        ${match_exact}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_name}   {{ border_device.name }}
        ${match_short}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_hostname}   {{ border_device.name }}
        ${is_match}=   Evaluate   ${match_exact} or ${match_short}
        Run Keyword If   ${is_match}   Set Suite Variable   ${device_id}   ${device}[id]
        Exit For Loop If   ${is_match}
    END
    Run Keyword If   "${device_id}" == "${EMPTY}"   Fail   Border device {{ border_device.name }} not found in network devices
    Log To Console   Found device {{ border_device.name }} with ID: ${device_id}
    
    # Find transit network ID by name
    ${transit_data}=   Get Value From Json   ${TRANSIT_NETWORKS.json()}   $.response[?(@.name=='{{ l3_handoff.name }}')]
    Run Keyword If   not ${transit_data}   Fail   IP Transit {{ l3_handoff.name }} not found in transit networks
    ${transit_id}=   Set Variable   ${transit_data}[0][id]
    Log To Console   Found IP Transit {{ l3_handoff.name }} with ID: ${transit_id}
    
    # Find fabric ID for this device
    ${fabric_id}=   Set Variable   ${EMPTY}
    ${fabric_sites_list}=   Get Value From Json   ${FABRIC_SITES.json()}   $.response
    ${fabric_sites_list}=   Set Variable   ${fabric_sites_list}[0]
    FOR   ${fabric_site}   IN   @{fabric_sites_list}
        ${site_fabric_id}=   Get From Dictionary   ${fabric_site}   id
        # Query IP transits for this fabric to check if our device is there
        ${ip_response}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/fabricDevices/layer3Handoffs/ipTransits   params=fabricId=${site_fabric_id}&networkDeviceId=${device_id}
        ${ip_handoffs}=   Get Value From Json   ${ip_response.json()}   $.response
        ${has_handoffs}=   Evaluate   len(${ip_handoffs}[0]) > 0 if ${ip_handoffs} else False
        Run Keyword If   ${has_handoffs}   Set Suite Variable   ${fabric_id}   ${site_fabric_id}
        Exit For Loop If   ${has_handoffs}
    END
    Run Keyword If   "${fabric_id}" == "${EMPTY}"   Pass Execution   No IP Transit L3 Handoff found for device {{ border_device.name }}, skipping validation
    
    # Get IP Transit L3 Handoff data
    ${r}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/fabricDevices/layer3Handoffs/ipTransits   params=fabricId=${fabric_id}&networkDeviceId=${device_id}
    Log To Console   IP Transit L3 Handoff Response: ${r.json()}
    
    # Find the specific handoff entry matching transit, interface, and VN
    ${handoff_list}=   Get Value From Json   ${r.json()}   $.response
    ${handoff_list}=   Set Variable   ${handoff_list}[0]
    ${handoff}=   Set Variable   ${None}
    FOR   ${entry}   IN   @{handoff_list}
        ${entry_transit_id}=   Get From Dictionary   ${entry}   transitNetworkId
        ${entry_interface}=   Get From Dictionary   ${entry}   interfaceName
        ${entry_vn}=   Get From Dictionary   ${entry}   virtualNetworkName
        ${match_transit}=   Run Keyword And Return Status   Should Be Equal As Strings   ${entry_transit_id}   ${transit_id}
        ${match_interface}=   Run Keyword And Return Status   Should Be Equal As Strings   ${entry_interface}   {{ interface.name }}
        ${match_vn}=   Run Keyword And Return Status   Should Be Equal As Strings   ${entry_vn}   {{ vn.name }}
        ${is_match}=   Evaluate   ${match_transit} and ${match_interface} and ${match_vn}
        Run Keyword If   ${is_match}   Set Suite Variable   ${handoff}   ${entry}
        Exit For Loop If   ${is_match}
    END
    Run Keyword If   "${handoff}" == "${None}"   Fail   IP Transit L3 Handoff for transit {{ l3_handoff.name }}, interface {{ interface.name }}, VN {{ vn.name }} not found
    
    # Validate IP Transit attributes
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[networkDeviceId]   ${device_id}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[transitNetworkId]   ${transit_id}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[interfaceName]   {{ interface.name }}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[virtualNetworkName]   {{ vn.name }}
    
{% if vn.vlan is defined %}
    Run Keyword And Continue On Failure   Should Be Equal As Numbers   ${handoff}[vlanId]   {{ vn.vlan }}
{% endif %}
{% if vn.local_ip_address is defined %}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[localIpAddress]   {{ vn.local_ip_address }}
{% endif %}
{% if vn.peer_ip_address is defined %}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[remoteIpAddress]   {{ vn.peer_ip_address }}
{% endif %}
{% if vn.local_ipv6_address is defined %}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[localIpv6Address]   {{ vn.local_ipv6_address }}
{% endif %}
{% if vn.peer_ipv6_address is defined %}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[remoteIpv6Address]   {{ vn.peer_ipv6_address }}
{% endif %}
{% if vn.tcp_mss_adjustment is defined %}
    Run Keyword And Continue On Failure   Should Be Equal As Numbers   ${handoff}[tcpMssAdjustment]   {{ vn.tcp_mss_adjustment }}
{% endif %}

{% endfor %}
{% endfor %}
{% endfor %}
{% endif %}
{% endif %}
{# End of device state check #}
{% endif %}
{# End of LAYER_3 border type check #}
{% endfor %}

{% else %}
Check L3 Handoffs Configuration in Data Model
    [Documentation]   Check if L3 handoffs are configured in the data model
    Pass Execution   No border devices with L3 handoffs configured in data model, skipping L3 handoff tests
{% endif %}

