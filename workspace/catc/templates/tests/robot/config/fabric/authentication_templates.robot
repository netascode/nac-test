*** Settings ***
Documentation     Verify Authentication Templates Configuration
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   authentication_templates   site_specific

*** Test Cases ***

Get Fabric Zones
    ${z}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/fabricZones
    Log   Response Status Code (Fabric Zones): ${z.status_code}
    Set Suite Variable   ${z}

Get Authentication Profiles
    ${a}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/authenticationProfiles
    Log   Response Status Code (Authentication Profiles): ${a.status_code}
    Set Suite Variable   ${a}

{% for fabric_site in catalyst_center.fabric.fabric_sites | default([]) %}
{% if fabric_site.authentication_template is defined %}
Verify Authentication Template for Fabric Site {{ fabric_site.name }}
    Log To Console   Validating authentication template data model values for fabric site {{ fabric_site.name }}

    # Check if this site should be skipped based on MANAGED_SITES
    ${should_skip}=   Should Skip Site Validation   {{ fabric_site.name }}
    Pass Execution If   ${should_skip}   Fabric site {{ fabric_site.name }} not managed by this deployment state - skipping validation

    # Step 1: Get fabric site ID
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='{{ fabric_site.name }}')]
    Run Keyword If   not ${site_data}   Fail   Site {{ fabric_site.name }} not found in Catalyst Center - deployment issue
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    
    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found.
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id

    # Step 2: Check authentication template configuration
    ${template_name}=   Set Variable   {{ fabric_site.authentication_template.name | default(defaults.catalyst_center.fabric.fabric_sites.authentication_template.name) }}
    
    # Handle "No Authentication" case - test passes without validation
    IF   '${template_name}' == 'No Authentication'
        Log To Console   No authentication template configured for fabric site {{ fabric_site.name }} - test passed
        Log To Console   Authentication template validation completed for fabric site {{ fabric_site.name }}
    ELSE
        # Step 3: Find authentication profile by name and fabric ID
        ${profiles_by_name}=   Get Value From Json   ${a.json()}   $.response[?(@.authenticationProfileName=='${template_name}')]
        Run Keyword If   not ${profiles_by_name}   Fail   Authentication profile ${template_name} not found for fabric site {{ fabric_site.name }}
        
        # Try to find profile with matching fabric ID
        ${profile_entry}=   Set Variable   ${EMPTY}
        ${profile_found}=   Set Variable   ${False}
        FOR   ${profile}   IN   @{profiles_by_name}
            ${has_fabric_id}=   Run Keyword And Return Status   Dictionary Should Contain Key   ${profile}   fabricId
            Continue For Loop If   not ${has_fabric_id}
            ${actual_fabric_id}=   Get From Dictionary   ${profile}   fabricId
            IF   '${actual_fabric_id}' == '${fabric_id}'
                ${profile_entry}=   Set Variable   ${profile}
                ${profile_found}=   Set Variable   ${True}
                Exit For Loop
            END
        END
        
        # Fallback: Use first profile with matching name if no fabric-specific match
        IF   not ${profile_found}
            ${profile_entry}=   Set Variable   ${profiles_by_name}[0]
        END
        Log To Console   Found authentication profile: ${template_name}

        # Step 4: Validate basic profile attributes
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.authenticationProfileName   ${template_name}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.dot1xToMabFallbackTimeout   {{ fabric_site.authentication_template.dot1x_to_mab_fallback_timeout | default(defaults.catalyst_center.authentication_templates.dot1x_to_mab_fallback_timeout) }}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.wakeOnLan   {{ fabric_site.authentication_template.wake_on_lan | default(defaults.catalyst_center.authentication_templates.wake_on_lan) }}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.numberOfHosts   {{ fabric_site.authentication_template.number_of_hosts | default(defaults.catalyst_center.authentication_templates.number_of_hosts) }}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.authenticationOrder   {{ fabric_site.authentication_template.authentication_order | default(defaults.catalyst_center.authentication_templates.authentication_order) }}

        Run Keyword If   '${template_name}' == 'Closed Authentication'   Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.isBpduGuardEnabled   {{ fabric_site.authentication_template.bpdu_guard | default(defaults.catalyst_center.authentication_templates.bpdu_guard) }}

        # Step 5: Validate Pre-Auth ACL configuration
        {% if fabric_site.authentication_template.pre_auth_acl is defined %}
        ${preauth_exists}=   Run Keyword And Return Status   Dictionary Should Contain Key   ${profile_entry}   preAuthAcl
        Run Keyword If   not ${preauth_exists}   Fail   Pre-Auth ACL configuration missing in API response
        ${preauth_acl}=   Get From Dictionary   ${profile_entry}   preAuthAcl

        {% if fabric_site.authentication_template.pre_auth_acl.enabled is defined %}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${preauth_acl}   $.enabled   {{ fabric_site.authentication_template.pre_auth_acl.enabled }}
        {% endif %}

        {% if fabric_site.authentication_template.pre_auth_acl.implicit_action is defined %}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${preauth_acl}   $.implicitAction   {{ fabric_site.authentication_template.pre_auth_acl.implicit_action }}
        {% endif %}

        {% if fabric_site.authentication_template.pre_auth_acl.description is defined %}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${preauth_acl}   $.description   {{ fabric_site.authentication_template.pre_auth_acl.description }}
        {% endif %}

        # Step 6: Validate Access Contracts
        {% if fabric_site.authentication_template.pre_auth_acl.access_contracts is defined %}
        ${contracts_exist}=   Run Keyword And Return Status   Dictionary Should Contain Key   ${preauth_acl}   accessContracts
        Run Keyword If   not ${contracts_exist}   Fail   Access contracts missing in API response
        ${api_contracts}=   Get From Dictionary   ${preauth_acl}   accessContracts

        {% for contract in fabric_site.authentication_template.pre_auth_acl.access_contracts %}
        # Find matching contract in API response
        ${contract_found}=   Set Variable   ${False}
        FOR   ${api_contract}   IN   @{api_contracts}
            ${api_action}=   Get From Dictionary   ${api_contract}   action
            ${api_protocol}=   Get From Dictionary   ${api_contract}   protocol
            ${api_port}=   Get From Dictionary   ${api_contract}   port
            
            ${matches}=   Evaluate   '${api_action}' == '{{ contract.action }}' and '${api_protocol}' == '{{ contract.protocol }}' and '${api_port}' == '{{ contract.port }}'
            IF   ${matches}
                ${contract_found}=   Set Variable   ${True}
                Exit For Loop
            END
        END
        
        Run Keyword And Continue On Failure   Should Be True   ${contract_found}   Access contract ({{ contract.action }}, {{ contract.protocol }}, {{ contract.port }}) not found in API response
        {% endfor %}
        {% endif %}
        {% endif %}

        Log To Console   Authentication template data model validation completed for fabric site {{ fabric_site.name }}
    END

{% endif %}

{% if fabric_site.fabric_zones is defined %}
{% for fabric_zone in fabric_site.fabric_zones %}
{% if fabric_zone.authentication_template is defined %}
Verify Authentication Template for Fabric Zone {{ fabric_zone.name }}
    Log To Console   Validating authentication template data model values for fabric zone {{ fabric_zone.name }}

    # Step 1: Get zone site ID
    ${s}=   Get Cached Sites Data
    ${zone_site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='{{ fabric_zone.name }}')]
    Run Keyword If   not ${zone_site_data}   Fail   Site {{ fabric_zone.name }} not found in Sites API response.
    ${zone_site_entry}=   Set Variable   ${zone_site_data}[0]
    ${zone_site_id}=   Get From Dictionary   ${zone_site_entry}   id
    
    ${zone_data}=   Get Value From Json   ${z.json()}   $.response[?(@.siteId=='${zone_site_id}')]
    Run Keyword If   not ${zone_data}   Fail   Fabric zone for site {{ fabric_zone.name }} not found.
    ${zone_entry}=   Set Variable   ${zone_data}[0]

    # Step 2: Check authentication template configuration
    ${zone_template_name}=   Set Variable   {{ fabric_zone.authentication_template.name | default(defaults.catalyst_center.fabric.fabric_sites.authentication_template.name) }}
    
    # Handle "No Authentication" case - test passes without validation
    IF   '${zone_template_name}' == 'No Authentication'
        Log To Console   No authentication template configured for fabric zone {{ fabric_zone.name }} - test passed
        Log To Console   Authentication template validation completed for fabric zone {{ fabric_zone.name }}
    ELSE
        # Step 3: Find authentication profile by name (zones may not have specific fabricId)
        ${zone_profiles_by_name}=   Get Value From Json   ${a.json()}   $.response[?(@.authenticationProfileName=='${zone_template_name}')]
        Run Keyword If   not ${zone_profiles_by_name}   Fail   Authentication profile ${zone_template_name} not found for fabric zone {{ fabric_zone.name }}
        
        ${zone_profile_entry}=   Set Variable   ${zone_profiles_by_name}[0]
        Log To Console   Found authentication profile for zone: ${zone_template_name}

        # Step 4: Validate basic zone authentication template
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${zone_profile_entry}   $.authenticationProfileName   ${zone_template_name}

        Log To Console   Authentication template data model validation completed for fabric zone {{ fabric_zone.name }}
    END

{% endif %}
{% endfor %}
{% endif %}
{% endfor %} 