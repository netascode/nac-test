*** Settings ***
Documentation     Verify Fabric Sites Configuration
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   fabric_sites   site_specific

*** Test Cases ***

{% for fabric_site in catalyst_center.fabric.fabric_sites | default([]) %}
Verify Fabric Site {{ fabric_site.name }}
    Log To Console   Validating fabric site {{ fabric_site.name }}

    # Check if this site should be skipped based on MANAGED_SITES
    ${should_skip}=   Should Skip Site Validation   {{ fabric_site.name }}
    Pass Execution If   ${should_skip}   Fabric site {{ fabric_site.name }} not managed by this deployment state - skipping validation

    # Validate that the site exists in the Sites API response
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='{{ fabric_site.name }}')]
    Run Keyword If   not ${site_data}   Fail   Site {{ fabric_site.name }} not found in Catalyst Center - deployment issue

    # Extract site information
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    Log To Console   Site ID for {{ fabric_site.name }}: ${site_id}

    # Validate that the fabric site exists in the Fabric Sites API response
    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found in Fabric Sites API response.

    # Extract fabric information
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id
    Log To Console   Fabric site ID: ${fabric_id}

    # Validate fabric site attributes
    {% if fabric_site.authentication_template is defined and fabric_site.authentication_template.name is defined %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${fabric_entry}   $.authenticationProfileName   {{ fabric_site.authentication_template.name | default(defaults.catalyst_center.fabric.fabric_sites.authentication_template.name) }}
    {% endif %}

    {% if fabric_site.pub_sub_enabled is defined %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${fabric_entry}   $.isPubSubEnabled   {{ fabric_site.pub_sub_enabled | default(defaults.catalyst_center.fabric.fabric_sites.pub_sub_enabled) }}
    {% endif %}

    Log To Console   Fabric site {{ fabric_site.name }} validation completed

{% endfor %}
