*** Settings ***
Documentation     Verify Anycast Gateways Configuration
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   anycast_gateways   site_specific

*** Test Cases ***

Check Anycast Gateways Configuration in Data Model
    # Check if any fabric sites with anycast gateways are configured in the data model
    {% set fabric_sites_with_gateways = [] %}
    {% for fabric_site in catalyst_center.fabric.fabric_sites | default([]) %}
    {% if fabric_site.anycast_gateways is defined %}
    {% set _ = fabric_sites_with_gateways.append(fabric_site) %}
    {% endif %}
    {% endfor %}
    {% if not fabric_sites_with_gateways %}
    Pass Execution   No fabric sites with anycast gateways configured in data model - skipping anycast gateway validation tests
    {% else %}
    Log   Found {{ fabric_sites_with_gateways | length }} fabric site(s) with anycast gateways in data model
    {% endif %}

Get Anycast Gateways
    # Only execute if fabric sites with anycast gateways are configured in data model
    {% set fabric_sites_with_gateways = [] %}
    {% for fabric_site in catalyst_center.fabric.fabric_sites | default([]) %}
    {% if fabric_site.anycast_gateways is defined %}
    {% set _ = fabric_sites_with_gateways.append(fabric_site) %}
    {% endif %}
    {% endfor %}
    {% if fabric_sites_with_gateways %}
    ${r}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/anycastGateways
    Log   Response Status Code (Anycast Gateways): ${r.status_code}
    Log To Console   Anycast Gateways API Response: ${r.json()}
    Set Suite Variable   ${r}
    {% else %}
    Pass Execution   No fabric sites with anycast gateways configured in data model - skipping API calls
    {% endif %}

{% for fabric_site in catalyst_center.fabric.fabric_sites | default([]) %}
{% if fabric_site.anycast_gateways is defined %}
Verify Anycast Gateways for Fabric Site {{ fabric_site.name }}
    # Check if this site should be skipped based on MANAGED_SITES
    ${should_skip}=   Should Skip Site Validation   {{ fabric_site.name }}
    Pass Execution If   ${should_skip}   Fabric site {{ fabric_site.name }} not managed by this deployment state - skipping validation

    # Validate that the site exists in the Sites API response
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='{{ fabric_site.name }}')]
    Log To Console   Site data: ${site_data}
    Run Keyword If   not ${site_data}   Fail   Site {{ fabric_site.name }} not found in Catalyst Center - deployment issue

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

    # Validate anycast gateways exist for this fabric
    ${gateway_data}=   Get Value From Json   ${r.json()}   $.response[?(@.fabricId=='${fabric_id}')]
    Run Keyword If   not ${gateway_data}   Fail   No anycast gateways found for fabricId ${fabric_id} in Anycast Gateways API response.
    Log To Console   Gateway data for fabric ${fabric_id}: ${gateway_data}
    Set Suite Variable   ${gateway_data}

{% for gateway in fabric_site.anycast_gateways %}
Validate {{ gateway.ip_pool_name }}
    # Check if the parent fabric site is managed (skip if parent was skipped)
    ${should_skip}=   Should Skip Site Validation   {{ fabric_site.name }}
    Pass Execution If   ${should_skip}   Gateway {{ gateway.ip_pool_name }} in fabric site {{ fabric_site.name }} not managed by this deployment state - skipping validation

    # Validate individual gateway {{ gateway.ip_pool_name }}
    ${gateway_match}=   Get Value From Json   ${gateway_data}   $[?(@.ipPoolName=='{{ gateway.ip_pool_name }}')]
    Run Keyword If   not ${gateway_match}   Fail   Gateway {{ gateway.ip_pool_name }} not found in Anycast Gateways API response.
    ${g}=   Set Variable   ${gateway_match}[0]
    Log To Console   Extracted Gateway Entry: ${g}

    # Validate basic gateway attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.ipPoolName   {{ gateway.ip_pool_name }}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.virtualNetworkName   {{ gateway.l3_virtual_network }}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.trafficType   {{ gateway.traffic_type | default(defaults.catalyst_center.fabric.fabric_sites.anycast_gateways.traffic_type) }}

    # Validate VLAN configuration
{% if gateway.auto_generate_vlan_name is defined and gateway.auto_generate_vlan_name %}
    Log To Console   Skipping VLAN name validation as auto_generate_vlan_name is enabled for {{ gateway.ip_pool_name }}
{% else %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.vlanName   {{ gateway.vlan_name }}
{% endif %}

{% if gateway.vlan_id is defined %}
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.vlanId   {{ gateway.vlan_id }}
{% endif %}

    # Check if this is a special pool type (EXTENDED_NODE or FABRIC_AP)
    ${pool_type}=   Run Keyword And Return Status   Dictionary Should Contain Key   ${g}   poolType
    
    # Validate boolean gateway attributes only for regular pools (not EXTENDED_NODE or FABRIC_AP)
    IF    not ${pool_type}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isCriticalPool   {{ gateway.critical_pool | default(defaults.catalyst_center.fabric.fabric_sites.anycast_gateways.critical_pool) | default('false') }}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isLayer2FloodingEnabled   {{ gateway.layer2_flooding | default(defaults.catalyst_center.fabric.fabric_sites.anycast_gateways.layer2_flooding) | default('false') }}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isWirelessPool   {{ gateway.wireless_pool | default(defaults.catalyst_center.fabric.fabric_sites.anycast_gateways.wireless_pool) | default('false') }}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isIpDirectedBroadcast   {{ gateway.ip_directed_broadcast | default(defaults.catalyst_center.fabric.fabric_sites.anycast_gateways.ip_directed_broadcast) | default('false') }}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isIntraSubnetRoutingEnabled   {{ gateway.intra_subnet_routing_enabled | default(defaults.catalyst_center.fabric.fabric_sites.anycast_gateways.intra_subnet_routing_enabled) | default('false') }}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isMultipleIpToMacAddresses   {{ gateway.multiple_ip_to_mac_addresses | default(defaults.catalyst_center.fabric.fabric_sites.anycast_gateways.multiple_ip_to_mac_addresses) | default('false') }}
        Log To Console   Validated standard pool attributes for ${g['ipPoolName']}
    ELSE
        ${actual_pool_type}=   Get From Dictionary   ${g}   poolType
        Log To Console   Skipping standard pool validation for ${g['ipPoolName']} (poolType: ${actual_pool_type})
{% if gateway.pool_type is defined %}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.poolType   {{ gateway.pool_type }}
{% endif %}
    END

    # Validate additional API fields with defaults (direct boolean comparison)
    ${actual_supplicant_onboarding}=   Get From Dictionary   ${g}   isSupplicantBasedExtendedNodeOnboarding
{% if gateway.supplicant_based_extended_node_onboarding is defined %}
    ${expected_supplicant_onboarding_bool}=   Evaluate   {{ gateway.supplicant_based_extended_node_onboarding }}
{% else %}
    ${expected_supplicant_onboarding_bool}=   Evaluate   False
{% endif %}
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_supplicant_onboarding}   ${expected_supplicant_onboarding_bool}

    ${actual_group_policy_enforcement}=   Get From Dictionary   ${g}   isGroupBasedPolicyEnforcementEnabled
{% if gateway.group_based_policy_enforcement_enabled is defined %}
    ${expected_group_policy_enforcement_bool}=   Evaluate   {{ gateway.group_based_policy_enforcement_enabled }}
{% else %}
    # Default based on pool type: False for special pools (EXTENDED_NODE, FABRIC_AP), True for regular pools
    IF    ${pool_type}
        ${expected_group_policy_enforcement_bool}=   Evaluate   False
    ELSE
        ${expected_group_policy_enforcement_bool}=   Evaluate   True
    END
{% endif %}
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_group_policy_enforcement}   ${expected_group_policy_enforcement_bool}

{% endfor %}

{% endif %}
{% endfor %} 