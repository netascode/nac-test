*** Settings ***
Documentation     Verify Fabric Extranet Policies in Catalyst Center
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   extranet   site_specific

*** Test Cases ***

Get Extranet Policies
    ${r}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/extranetPolicies
    Log   Extranet Policies API Response: ${r.json()}
    Set Suite Variable   ${r}

Get Fabric Sites Data
    ${fabric_sites}=   Get Cached Fabric Sites Data
    Set Suite Variable   ${fabric_sites}

{% for extranet_policy in catalyst_center.fabric.extranet_policies | default([]) %}
Verify Extranet Policy {{ extranet_policy.name }}
    Log To Console   Validating extranet policy {{ extranet_policy.name }}

    # Check if any fabric sites in this policy are managed by this deployment state
    {% if extranet_policy.fabric_sites is defined and extranet_policy.fabric_sites | length > 0 %}
    ${has_managed_site}=   Set Variable   ${False}
    {% for fabric_site_name in extranet_policy.fabric_sites %}
    ${should_skip_site_check_{{ loop.index }}}=   Should Skip Site Validation   {{ fabric_site_name }}
    ${has_managed_site}=   Evaluate   ${has_managed_site} or not ${should_skip_site_check_{{ loop.index }}}
    {% endfor %}
    Pass Execution If   not ${has_managed_site}   Extranet policy {{ extranet_policy.name }} has no managed sites in this deployment state - skipping validation
    {% endif %}

    # Validate that the extranet policy exists in the API response
    ${policy_data}=   Get Value From Json   ${r.json()}   $.response[?(@.extranetPolicyName=='{{ extranet_policy.name }}')]
    Run Keyword If   not ${policy_data}   Fail   Extranet policy {{ extranet_policy.name }} not found in API response
    ${policy_entry}=   Set Variable   ${policy_data}[0]
    Log To Console   Extranet policy entry: ${policy_entry}
    
    # Validate basic extranet policy attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${policy_entry}   $.extranetPolicyName   {{ extranet_policy.name }}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${policy_entry}   $.providerVirtualNetworkName   {{ extranet_policy.provider_virtual_network }}
    
    # Validate subscriber virtual networks
    ${rec_subscriber_vns}=   Get Value From Json   ${policy_entry}   $.subscriberVirtualNetworkNames
    ${exp_subscriber_vns}=   Create List{% for vn in extranet_policy.subscriber_virtual_networks %}   {{ vn }}{% endfor %}

    Lists Should Be Equal   ${rec_subscriber_vns}[0]   ${exp_subscriber_vns}   ignore_order=True   msg=Subscriber virtual networks mismatch
    
    # Validate fabric sites
    {% if extranet_policy.fabric_sites is defined and extranet_policy.fabric_sites | length > 0 %}
    ${rec_fabric_ids}=   Get Value From Json   ${policy_entry}   $.fabricIds
    ${rec_fabric_ids_list}=   Set Variable   ${rec_fabric_ids}[0]
    Log To Console   Fabric IDs in policy: ${rec_fabric_ids_list}

    # Note: Not validating count since some sites may be skipped based on MANAGED_SITES
    # Individual site validation will catch any discrepancies

    # Get Sites API to map site names to IDs
    ${s}=   Get Cached Sites Data
    
    # Validate each fabric site
    {% for fabric_site_name in extranet_policy.fabric_sites %}
    # Check if this fabric site should be skipped based on MANAGED_SITES
    ${should_skip_site_{{ loop.index }}}=   Should Skip Site Validation   {{ fabric_site_name }}
    IF   not ${should_skip_site_{{ loop.index }}}
        Validate Extranet Fabric Site   {{ fabric_site_name }}   ${rec_fabric_ids_list}   ${s}   ${fabric_sites}
    END
    {% endfor %}

*** Keywords ***
Validate Extranet Fabric Site
    [Arguments]   ${fabric_site_name}   ${rec_fabric_ids_list}   ${sites}   ${fabric_sites}

    # Step 1: Get site ID from Sites API
    ${site_data}=   Get Value From Json   ${sites.json()}   $.response[?(@.nameHierarchy=='${fabric_site_name}')]
    Run Keyword If   not ${site_data}   Fail   Site ${fabric_site_name} not found in Catalyst Center - deployment issue
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    Log To Console   Site ID for ${fabric_site_name}: ${site_id}

    # Step 2: Get fabric site ID from Fabric Sites API
    ${fabric_site_data}=   Get Value From Json   ${fabric_sites.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_site_data}   Fail   Fabric site with siteId ${site_id} not found in Fabric Sites API response
    ${fabric_site_entry}=   Set Variable   ${fabric_site_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_site_entry}   id
    Log To Console   Fabric ID for ${fabric_site_name}: ${fabric_id}

    # Step 3: Verify fabric ID is in the extranet policy's fabric IDs list
    List Should Contain Value   ${rec_fabric_ids_list}   ${fabric_id}   msg=Fabric site ${fabric_site_name} (ID: ${fabric_id}) not in extranet policy fabric IDs
    {% endif %}
    
    Log To Console   Extranet policy {{ extranet_policy.name }} validation completed

{% endfor %}

