*** Settings ***
Documentation     Verify Fabric Zones Configuration
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   fabric_zones

*** Test Cases ***

Get Fabric Zones
    ${z}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/fabricZones
    Log   Response Status Code (Fabric Zones): ${z.status_code}
    Set Suite Variable   ${z}

{% for fabric_site in catalyst_center.fabric.fabric_sites | default([]) %}
{% if fabric_site.fabric_zones is defined %}
{% for fabric_zone in fabric_site.fabric_zones %}
Verify Fabric Zone {{ fabric_zone.name }}
    Log To Console   Validating fabric zone {{ fabric_zone.name }}

    # Step 1: Resolve zone site name to site ID
    ${s}=   Get Cached Sites Data
    ${zone_site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='{{ fabric_zone.name }}')]
    Run Keyword If   not ${zone_site_data}   Fail   Site {{ fabric_zone.name }} not found in Sites API response.
    
    ${zone_site_entry}=   Set Variable   ${zone_site_data}[0]
    ${zone_site_id}=   Get From Dictionary   ${zone_site_entry}   id
    Log To Console   Zone site ID for {{ fabric_zone.name }}: ${zone_site_id}

    # Step 2: Find fabric zone by site ID
    ${zone_data}=   Get Value From Json   ${z.json()}   $.response[?(@.siteId=='${zone_site_id}')]
    Run Keyword If   not ${zone_data}   Fail   Fabric zone for site {{ fabric_zone.name }} not found in Fabric Zones API response.
    
    ${zone_entry}=   Set Variable   ${zone_data}[0]
    ${zone_id}=   Get From Dictionary   ${zone_entry}   id
    Log To Console   Fabric zone ID: ${zone_id}

    # Step 3: Validate authentication template
    {% if fabric_zone.authentication_template is defined and fabric_zone.authentication_template.name is defined %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${zone_entry}   $.authenticationProfileName   {{ fabric_zone.authentication_template.name | default(defaults.catalyst_center.fabric.fabric_sites.authentication_template.name) }}
    {% endif %}

    Log To Console   Fabric zone {{ fabric_zone.name }} validation completed

{% endfor %}
{% endif %}
{% endfor %} 