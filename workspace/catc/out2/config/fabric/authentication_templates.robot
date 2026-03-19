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

Verify Authentication Template for Fabric Site Global/Poland/Krakow
    Log To Console   Validating authentication template data model values for fabric site Global/Poland/Krakow
    # Check if this site should be skipped based on MANAGED_SITES
    ${should_skip}=   Should Skip Site Validation   Global/Poland/Krakow
    Pass Execution If   ${should_skip}   Fabric site Global/Poland/Krakow not managed by this deployment state - skipping validation
    # Step 1: Get fabric site ID
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='Global/Poland/Krakow')]
    Run Keyword If   not ${site_data}   Fail   Site Global/Poland/Krakow not found in Catalyst Center - deployment issue
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found.
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id
    # Step 2: Check authentication template configuration
    ${template_name}=   Set Variable   No Authentication
    # Handle "No Authentication" case - test passes without validation
    IF   '${template_name}' == 'No Authentication'
        Log To Console   No authentication template configured for fabric site Global/Poland/Krakow - test passed
        Log To Console   Authentication template validation completed for fabric site Global/Poland/Krakow
    ELSE
        # Step 3: Find authentication profile by name and fabric ID
        ${profiles_by_name}=   Get Value From Json   ${a.json()}   $.response[?(@.authenticationProfileName=='${template_name}')]
        Run Keyword If   not ${profiles_by_name}   Fail   Authentication profile ${template_name} not found for fabric site Global/Poland/Krakow
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
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.dot1xToMabFallbackTimeout   21
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.wakeOnLan   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.numberOfHosts   Unlimited
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.authenticationOrder   dot1x
        Run Keyword If   '${template_name}' == 'Closed Authentication'   Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.isBpduGuardEnabled   True
        # Step 5: Validate Pre-Auth ACL configuration
        Log To Console   Authentication template data model validation completed for fabric site Global/Poland/Krakow
    END

Verify Authentication Template for Fabric Site Global/Poland/Warsaw
    Log To Console   Validating authentication template data model values for fabric site Global/Poland/Warsaw
    # Check if this site should be skipped based on MANAGED_SITES
    ${should_skip}=   Should Skip Site Validation   Global/Poland/Warsaw
    Pass Execution If   ${should_skip}   Fabric site Global/Poland/Warsaw not managed by this deployment state - skipping validation
    # Step 1: Get fabric site ID
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='Global/Poland/Warsaw')]
    Run Keyword If   not ${site_data}   Fail   Site Global/Poland/Warsaw not found in Catalyst Center - deployment issue
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found.
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id
    # Step 2: Check authentication template configuration
    ${template_name}=   Set Variable   Closed Authentication
    # Handle "No Authentication" case - test passes without validation
    IF   '${template_name}' == 'No Authentication'
        Log To Console   No authentication template configured for fabric site Global/Poland/Warsaw - test passed
        Log To Console   Authentication template validation completed for fabric site Global/Poland/Warsaw
    ELSE
        # Step 3: Find authentication profile by name and fabric ID
        ${profiles_by_name}=   Get Value From Json   ${a.json()}   $.response[?(@.authenticationProfileName=='${template_name}')]
        Run Keyword If   not ${profiles_by_name}   Fail   Authentication profile ${template_name} not found for fabric site Global/Poland/Warsaw
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
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.dot1xToMabFallbackTimeout   30
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.wakeOnLan   False
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.numberOfHosts   Unlimited
        Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.authenticationOrder   dot1x
        Run Keyword If   '${template_name}' == 'Closed Authentication'   Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${profile_entry}   $.isBpduGuardEnabled   True
        # Step 5: Validate Pre-Auth ACL configuration
        Log To Console   Authentication template data model validation completed for fabric site Global/Poland/Warsaw
    END