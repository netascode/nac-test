*** Settings ***
Documentation     Verify Anycast Gateways Configuration
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   anycast_gateways   site_specific

*** Test Cases ***

Check Anycast Gateways Configuration in Data Model
    # Check if any fabric sites with anycast gateways are configured in the data model
    Log   Found 1 fabric site(s) with anycast gateways in data model

Get Anycast Gateways
    # Only execute if fabric sites with anycast gateways are configured in data model
    ${r}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/anycastGateways
    Log   Response Status Code (Anycast Gateways): ${r.status_code}
    Log To Console   Anycast Gateways API Response: ${r.json()}
    Set Suite Variable   ${r}

Verify Anycast Gateways for Fabric Site Global/Poland/Krakow
    # Check if this site should be skipped based on MANAGED_SITES
    ${should_skip}=   Should Skip Site Validation   Global/Poland/Krakow
    Pass Execution If   ${should_skip}   Fabric site Global/Poland/Krakow not managed by this deployment state - skipping validation
    # Validate that the site exists in the Sites API response
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='Global/Poland/Krakow')]
    Log To Console   Site data: ${site_data}
    Run Keyword If   not ${site_data}   Fail   Site Global/Poland/Krakow not found in Catalyst Center - deployment issue
    # Extract site information
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    Log To Console   Site ID for Global/Poland/Krakow: ${site_id}
    # Validate that the fabric site exists in the Fabric Sites API response
    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Log To Console   Fabric data: ${fabric_data}
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found in Fabric Sites API response.
    # Extract fabric information
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id
    Log To Console   Fabric ID for Global/Poland/Krakow: ${fabric_id}
    # Validate anycast gateways exist for this fabric
    ${gateway_data}=   Get Value From Json   ${r.json()}   $.response[?(@.fabricId=='${fabric_id}')]
    Run Keyword If   not ${gateway_data}   Fail   No anycast gateways found for fabricId ${fabric_id} in Anycast Gateways API response.
    Log To Console   Gateway data for fabric ${fabric_id}: ${gateway_data}
    Set Suite Variable   ${gateway_data}

Validate CampusVN-IPPool
    # Check if the parent fabric site is managed (skip if parent was skipped)
    ${should_skip}=   Should Skip Site Validation   Global/Poland/Krakow
    Pass Execution If   ${should_skip}   Gateway CampusVN-IPPool in fabric site Global/Poland/Krakow not managed by this deployment state - skipping validation
    # Validate individual gateway CampusVN-IPPool
    ${gateway_match}=   Get Value From Json   ${gateway_data}   $[?(@.ipPoolName=='CampusVN-IPPool')]
    Run Keyword If   not ${gateway_match}   Fail   Gateway CampusVN-IPPool not found in Anycast Gateways API response.
    ${g}=   Set Variable   ${gateway_match}[0]
    Log To Console   Extracted Gateway Entry: ${g}
    # Validate basic gateway attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.ipPoolName   CampusVN-IPPool
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.virtualNetworkName   Campus
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.trafficType   DATA
    # Validate VLAN configuration
    Log To Console   Skipping VLAN name validation as auto_generate_vlan_name is enabled for CampusVN-IPPool
    # Check if this is a special pool type (EXTENDED_NODE or FABRIC_AP)
    ${pool_type}=   Run Keyword And Return Status   Dictionary Should Contain Key   ${g}   poolType
    # Validate boolean gateway attributes only for regular pools (not EXTENDED_NODE or FABRIC_AP)
    IF    not ${pool_type}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isCriticalPool   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isLayer2FloodingEnabled   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isWirelessPool   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isIpDirectedBroadcast   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isIntraSubnetRoutingEnabled   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isMultipleIpToMacAddresses   False
        Log To Console   Validated standard pool attributes for ${g['ipPoolName']}
    ELSE
        ${actual_pool_type}=   Get From Dictionary   ${g}   poolType
        Log To Console   Skipping standard pool validation for ${g['ipPoolName']} (poolType: ${actual_pool_type})
    END
    # Validate additional API fields with defaults (direct boolean comparison)
    ${actual_supplicant_onboarding}=   Get From Dictionary   ${g}   isSupplicantBasedExtendedNodeOnboarding
    ${expected_supplicant_onboarding_bool}=   Evaluate   False
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_supplicant_onboarding}   ${expected_supplicant_onboarding_bool}
    ${actual_group_policy_enforcement}=   Get From Dictionary   ${g}   isGroupBasedPolicyEnforcementEnabled
    # Default based on pool type: False for special pools (EXTENDED_NODE, FABRIC_AP), True for regular pools
    IF    ${pool_type}
        ${expected_group_policy_enforcement_bool}=   Evaluate   False
    ELSE
        ${expected_group_policy_enforcement_bool}=   Evaluate   True
    END
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_group_policy_enforcement}   ${expected_group_policy_enforcement_bool}

Validate GuestVN-IPPool
    # Check if the parent fabric site is managed (skip if parent was skipped)
    ${should_skip}=   Should Skip Site Validation   Global/Poland/Krakow
    Pass Execution If   ${should_skip}   Gateway GuestVN-IPPool in fabric site Global/Poland/Krakow not managed by this deployment state - skipping validation
    # Validate individual gateway GuestVN-IPPool
    ${gateway_match}=   Get Value From Json   ${gateway_data}   $[?(@.ipPoolName=='GuestVN-IPPool')]
    Run Keyword If   not ${gateway_match}   Fail   Gateway GuestVN-IPPool not found in Anycast Gateways API response.
    ${g}=   Set Variable   ${gateway_match}[0]
    Log To Console   Extracted Gateway Entry: ${g}
    # Validate basic gateway attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.ipPoolName   GuestVN-IPPool
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.virtualNetworkName   Guest
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.trafficType   DATA
    # Validate VLAN configuration
    Log To Console   Skipping VLAN name validation as auto_generate_vlan_name is enabled for GuestVN-IPPool
    # Check if this is a special pool type (EXTENDED_NODE or FABRIC_AP)
    ${pool_type}=   Run Keyword And Return Status   Dictionary Should Contain Key   ${g}   poolType
    # Validate boolean gateway attributes only for regular pools (not EXTENDED_NODE or FABRIC_AP)
    IF    not ${pool_type}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isCriticalPool   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isLayer2FloodingEnabled   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isWirelessPool   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isIpDirectedBroadcast   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isIntraSubnetRoutingEnabled   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isMultipleIpToMacAddresses   False
        Log To Console   Validated standard pool attributes for ${g['ipPoolName']}
    ELSE
        ${actual_pool_type}=   Get From Dictionary   ${g}   poolType
        Log To Console   Skipping standard pool validation for ${g['ipPoolName']} (poolType: ${actual_pool_type})
    END
    # Validate additional API fields with defaults (direct boolean comparison)
    ${actual_supplicant_onboarding}=   Get From Dictionary   ${g}   isSupplicantBasedExtendedNodeOnboarding
    ${expected_supplicant_onboarding_bool}=   Evaluate   False
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_supplicant_onboarding}   ${expected_supplicant_onboarding_bool}
    ${actual_group_policy_enforcement}=   Get From Dictionary   ${g}   isGroupBasedPolicyEnforcementEnabled
    # Default based on pool type: False for special pools (EXTENDED_NODE, FABRIC_AP), True for regular pools
    IF    ${pool_type}
        ${expected_group_policy_enforcement_bool}=   Evaluate   False
    ELSE
        ${expected_group_policy_enforcement_bool}=   Evaluate   True
    END
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_group_policy_enforcement}   ${expected_group_policy_enforcement_bool}

Validate BYOD-IPPool
    # Check if the parent fabric site is managed (skip if parent was skipped)
    ${should_skip}=   Should Skip Site Validation   Global/Poland/Krakow
    Pass Execution If   ${should_skip}   Gateway BYOD-IPPool in fabric site Global/Poland/Krakow not managed by this deployment state - skipping validation
    # Validate individual gateway BYOD-IPPool
    ${gateway_match}=   Get Value From Json   ${gateway_data}   $[?(@.ipPoolName=='BYOD-IPPool')]
    Run Keyword If   not ${gateway_match}   Fail   Gateway BYOD-IPPool not found in Anycast Gateways API response.
    ${g}=   Set Variable   ${gateway_match}[0]
    Log To Console   Extracted Gateway Entry: ${g}
    # Validate basic gateway attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.ipPoolName   BYOD-IPPool
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.virtualNetworkName   BYOD
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.trafficType   DATA
    # Validate VLAN configuration
    Log To Console   Skipping VLAN name validation as auto_generate_vlan_name is enabled for BYOD-IPPool
    # Check if this is a special pool type (EXTENDED_NODE or FABRIC_AP)
    ${pool_type}=   Run Keyword And Return Status   Dictionary Should Contain Key   ${g}   poolType
    # Validate boolean gateway attributes only for regular pools (not EXTENDED_NODE or FABRIC_AP)
    IF    not ${pool_type}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isCriticalPool   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isLayer2FloodingEnabled   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isWirelessPool   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isIpDirectedBroadcast   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isIntraSubnetRoutingEnabled   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isMultipleIpToMacAddresses   False
        Log To Console   Validated standard pool attributes for ${g['ipPoolName']}
    ELSE
        ${actual_pool_type}=   Get From Dictionary   ${g}   poolType
        Log To Console   Skipping standard pool validation for ${g['ipPoolName']} (poolType: ${actual_pool_type})
    END
    # Validate additional API fields with defaults (direct boolean comparison)
    ${actual_supplicant_onboarding}=   Get From Dictionary   ${g}   isSupplicantBasedExtendedNodeOnboarding
    ${expected_supplicant_onboarding_bool}=   Evaluate   False
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_supplicant_onboarding}   ${expected_supplicant_onboarding_bool}
    ${actual_group_policy_enforcement}=   Get From Dictionary   ${g}   isGroupBasedPolicyEnforcementEnabled
    # Default based on pool type: False for special pools (EXTENDED_NODE, FABRIC_AP), True for regular pools
    IF    ${pool_type}
        ${expected_group_policy_enforcement_bool}=   Evaluate   False
    ELSE
        ${expected_group_policy_enforcement_bool}=   Evaluate   True
    END
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_group_policy_enforcement}   ${expected_group_policy_enforcement_bool}

Validate PrintersVN-IPPool
    # Check if the parent fabric site is managed (skip if parent was skipped)
    ${should_skip}=   Should Skip Site Validation   Global/Poland/Krakow
    Pass Execution If   ${should_skip}   Gateway PrintersVN-IPPool in fabric site Global/Poland/Krakow not managed by this deployment state - skipping validation
    # Validate individual gateway PrintersVN-IPPool
    ${gateway_match}=   Get Value From Json   ${gateway_data}   $[?(@.ipPoolName=='PrintersVN-IPPool')]
    Run Keyword If   not ${gateway_match}   Fail   Gateway PrintersVN-IPPool not found in Anycast Gateways API response.
    ${g}=   Set Variable   ${gateway_match}[0]
    Log To Console   Extracted Gateway Entry: ${g}
    # Validate basic gateway attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.ipPoolName   PrintersVN-IPPool
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.virtualNetworkName   Printers
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.trafficType   DATA
    # Validate VLAN configuration
    Log To Console   Skipping VLAN name validation as auto_generate_vlan_name is enabled for PrintersVN-IPPool
    # Check if this is a special pool type (EXTENDED_NODE or FABRIC_AP)
    ${pool_type}=   Run Keyword And Return Status   Dictionary Should Contain Key   ${g}   poolType
    # Validate boolean gateway attributes only for regular pools (not EXTENDED_NODE or FABRIC_AP)
    IF    not ${pool_type}
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isCriticalPool   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isLayer2FloodingEnabled   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isWirelessPool   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isIpDirectedBroadcast   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isIntraSubnetRoutingEnabled   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${g}   $.isMultipleIpToMacAddresses   False
        Log To Console   Validated standard pool attributes for ${g['ipPoolName']}
    ELSE
        ${actual_pool_type}=   Get From Dictionary   ${g}   poolType
        Log To Console   Skipping standard pool validation for ${g['ipPoolName']} (poolType: ${actual_pool_type})
    END
    # Validate additional API fields with defaults (direct boolean comparison)
    ${actual_supplicant_onboarding}=   Get From Dictionary   ${g}   isSupplicantBasedExtendedNodeOnboarding
    ${expected_supplicant_onboarding_bool}=   Evaluate   False
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_supplicant_onboarding}   ${expected_supplicant_onboarding_bool}
    ${actual_group_policy_enforcement}=   Get From Dictionary   ${g}   isGroupBasedPolicyEnforcementEnabled
    # Default based on pool type: False for special pools (EXTENDED_NODE, FABRIC_AP), True for regular pools
    IF    ${pool_type}
        ${expected_group_policy_enforcement_bool}=   Evaluate   False
    ELSE
        ${expected_group_policy_enforcement_bool}=   Evaluate   True
    END
    Run Keyword And Continue On Failure   Should Be Equal   ${actual_group_policy_enforcement}   ${expected_group_policy_enforcement_bool}