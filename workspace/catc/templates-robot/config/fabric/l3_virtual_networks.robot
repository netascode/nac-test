*** Settings ***
Documentation     Verify L3 Virtual Networks Association for Fabric Sites and Fabric Zones
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   l3_virtual_networks

*** Test Cases ***

Get Fabric Zones
    ${z}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/fabricZones
    Log   Response Status Code (Fabric Zones): ${z.status_code}
    Set Suite Variable   ${z}

Get L3 Virtual Networks
    ${l}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/layer3VirtualNetworks
    Log   Response Status Code (L3 Virtual Networks): ${l.status_code}
    Set Suite Variable   ${l}

{% for fabric_site in catalyst_center.fabric.fabric_sites | default([]) %}
{% if fabric_site.l3_virtual_networks is defined %}
Verify L3 Virtual Networks for Fabric Site {{ fabric_site.name }}
    Log To Console   Validating L3 virtual networks for fabric site {{ fabric_site.name }}

    # Step 1: Get fabric site ID
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='{{ fabric_site.name }}')]
    ${site_count}=   Get Length   ${site_data}
    Run Keyword If   ${site_count} == 0   Log To Console   Skipping site association check - Site {{ fabric_site.name }} not deployed yet (GLOBAL state)
    Pass Execution If   ${site_count} == 0   Site {{ fabric_site.name }} not deployed - skipping validation

    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id

    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found in Fabric Sites API response.
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id
    Log To Console   Fabric site ID: ${fabric_id}

    # Step 2: Validate L3 Virtual Networks association
{% for l3_network in fabric_site.l3_virtual_networks %}
    ${network_data}=   Get Value From Json   ${l.json()}   $.response[?(@.virtualNetworkName=='{{ l3_network }}')]
    Run Keyword If   not ${network_data}   Fail   L3 Virtual Network {{ l3_network }} not found in L3 Virtual Networks API response.
    ${network_entry}=   Set Variable   ${network_data}[0]

    # Validate that the fabricId is associated with the L3 Virtual Network
    ${fabric_ids}=   Get From Dictionary   ${network_entry}   fabricIds
    Run Keyword And Continue On Failure   List Should Contain Value   ${fabric_ids}   ${fabric_id}   L3 Virtual Network {{ l3_network }} not associated with fabric site {{ fabric_site.name }}
    Log To Console   L3 Virtual Network {{ l3_network }} associated with fabric site {{ fabric_site.name }}
{% endfor %}

    Log To Console   L3 virtual networks validation completed for fabric site {{ fabric_site.name }}

{% endif %}

{% if fabric_site.fabric_zones is defined %}
{% for fabric_zone in fabric_site.fabric_zones %}
{% if fabric_zone.l3_virtual_networks is defined %}
Verify L3 Virtual Networks for Fabric Zone {{ fabric_zone.name }}
    Log To Console   Validating L3 virtual networks for fabric zone {{ fabric_zone.name }}

    # Step 1: Get fabric zone ID
    ${s}=   Get Cached Sites Data
    ${zone_site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='{{ fabric_zone.name }}')]
    ${zone_site_count}=   Get Length   ${zone_site_data}
    Run Keyword If   ${zone_site_count} == 0   Log To Console   Skipping zone association check - Site {{ fabric_zone.name }} not deployed yet (GLOBAL state)
    Pass Execution If   ${zone_site_count} == 0   Site {{ fabric_zone.name }} not deployed - skipping validation

    ${zone_site_entry}=   Set Variable   ${zone_site_data}[0]
    ${zone_site_id}=   Get From Dictionary   ${zone_site_entry}   id

    ${zone_data}=   Get Value From Json   ${z.json()}   $.response[?(@.siteId=='${zone_site_id}')]
    Run Keyword If   not ${zone_data}   Fail   Fabric zone for site {{ fabric_zone.name }} not found in Fabric Zones API response.
    ${zone_entry}=   Set Variable   ${zone_data}[0]
    ${zone_id}=   Get From Dictionary   ${zone_entry}   id
    Log To Console   Fabric zone ID: ${zone_id}

    # Step 2: Validate L3 Virtual Networks association with zone
{% for l3_network in fabric_zone.l3_virtual_networks %}
    ${zone_network_data}=   Get Value From Json   ${l.json()}   $.response[?(@.virtualNetworkName=='{{ l3_network }}')]
    Run Keyword If   not ${zone_network_data}   Fail   L3 Virtual Network {{ l3_network }} not found in L3 Virtual Networks API response.
    ${zone_network_entry}=   Set Variable   ${zone_network_data}[0]

    # Validate that the zone fabricId is associated with the L3 Virtual Network
    ${zone_fabric_ids}=   Get From Dictionary   ${zone_network_entry}   fabricIds
    Run Keyword And Continue On Failure   List Should Contain Value   ${zone_fabric_ids}   ${zone_id}   L3 Virtual Network {{ l3_network }} not associated with fabric zone {{ fabric_zone.name }}
    Log To Console   L3 Virtual Network {{ l3_network }} associated with fabric zone {{ fabric_zone.name }}
{% endfor %}

    Log To Console   L3 virtual networks validation completed for fabric zone {{ fabric_zone.name }}

{% endif %}
{% endfor %}
{% endif %}
{% endfor %} 