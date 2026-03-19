*** Settings ***
Documentation     Verify L2 Virtual Networks Configuration
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   l2_virtual_networks

*** Test Cases ***

Get L2 Virtual Networks
    ${r}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/layer2VirtualNetworks
    Log   Response Status Code (L2 Virtual Networks): ${r.status_code}
    Log To Console   L2 Virtual Networks API Response: ${r.json()}
    Set Suite Variable   ${r}

{% for fabric_site in catalyst_center.fabric.fabric_sites | default([]) %}
{% if fabric_site.l2_virtual_networks is defined %}
Verify L2 Virtual Networks for Fabric Site {{ fabric_site.name }}

    # Validate that the site exists in the Sites API response
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='{{ fabric_site.name }}')]
    ${site_count}=   Get Length   ${site_data}
    Log To Console   Site data: ${site_data}
    Run Keyword If   ${site_count} == 0   Log To Console   Skipping L2 VN association check - Site {{ fabric_site.name }} not deployed yet (GLOBAL state)
    Pass Execution If   ${site_count} == 0   Site {{ fabric_site.name }} not deployed - skipping validation

    # Extract site information
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    Log To Console   Site ID for {{ fabric_site.name }}: ${site_id}

    # Validate that the fabric site exists in the Fabric Sites API response
    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Log To Console   Fabric data: ${fabric_data}
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found in Fabric Sites API response.

    # Extract fabric information
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id
    Log To Console   Fabric ID for {{ fabric_site.name }}: ${fabric_id}

    # Validate L2 virtual networks exist for this fabric
    ${l2vn_data}=   Get Value From Json   ${r.json()}   $.response[?(@.fabricId=='${fabric_id}')]
    Run Keyword If   not ${l2vn_data}   Fail   No L2 virtual networks found for fabricId ${fabric_id} in L2 Virtual Networks API response.
    Log To Console   L2 Virtual Networks data for fabric ${fabric_id}: ${l2vn_data}

{% for l2_virtual_network in fabric_site.l2_virtual_networks %}
    # Validate individual L2 Virtual Network {{ l2_virtual_network.name }}
    ${l2vn_match}=   Get Value From Json   ${l2vn_data}   $[?(@.vlanName=='{{ l2_virtual_network.vlan_name }}')]
    Run Keyword If   not ${l2vn_match}   Fail   L2 Virtual Network with vlanName {{ l2_virtual_network.vlan_name }} not found in L2 Virtual Networks API response.
    ${l}=   Set Variable   ${l2vn_match}[0]
    Log To Console   Extracted L2 Virtual Network Entry: ${l}

    # Validate basic L2 Virtual Network attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${l}   $.vlanName   {{ l2_virtual_network.vlan_name | default(defaults.catalyst_center.fabric.fabric_sites.l2_virtual_networks.vlan_name) }}
{% if l2_virtual_network.vlan_id is defined %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${l}   $.vlanId   {{ l2_virtual_network.vlan_id }}
{% endif %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${l}   $.trafficType   {{ l2_virtual_network.traffic_type | default(defaults.catalyst_center.fabric.fabric_sites.l2_virtual_networks.traffic_type) }}

{% if l2_virtual_network.fabric_enabled_wireless is defined %}
    # Validate boolean attributes (direct boolean comparison)
    ${actual_fabric_wireless}=   Get From Dictionary   ${l}   isFabricEnabledWireless
    ${expected_fabric_wireless_str}=   Set Variable   {{ l2_virtual_network.fabric_enabled_wireless }}
    ${expected_fabric_wireless_bool}=   Evaluate   '${expected_fabric_wireless_str}'.lower() == 'true'
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_fabric_wireless}   ${expected_fabric_wireless_bool}
{% endif %}

{% if l2_virtual_network.associated_l3_virtual_network_name is defined %}
    # Validate associated L3 virtual network name
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${l}   $.associatedLayer3VirtualNetworkName   {{ l2_virtual_network.associated_l3_virtual_network_name }}
{% endif %}

    Log To Console   L2 Virtual Network {{ l2_virtual_network.name }} ({{ l2_virtual_network.vlan_name }}) validation completed for Fabric ID ${fabric_id}

{% endfor %}

{% endif %}
{% endfor %} 