*** Settings ***
Documentation     Verify Fabric Sites Configuration
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   fabric_sites   site_specific

*** Test Cases ***

Verify Fabric Site Global/Poland/Krakow
    Log To Console   Validating fabric site Global/Poland/Krakow
    # Check if this site should be skipped based on MANAGED_SITES
    ${should_skip}=   Should Skip Site Validation   Global/Poland/Krakow
    Pass Execution If   ${should_skip}   Fabric site Global/Poland/Krakow not managed by this deployment state - skipping validation
    # Validate that the site exists in the Sites API response
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='Global/Poland/Krakow')]
    Run Keyword If   not ${site_data}   Fail   Site Global/Poland/Krakow not found in Catalyst Center - deployment issue
    # Extract site information
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    Log To Console   Site ID for Global/Poland/Krakow: ${site_id}
    # Validate that the fabric site exists in the Fabric Sites API response
    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found in Fabric Sites API response.
    # Extract fabric information
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id
    Log To Console   Fabric site ID: ${fabric_id}
    # Validate fabric site attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${fabric_entry}   $.authenticationProfileName   No Authentication
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${fabric_entry}   $.isPubSubEnabled   True
    Log To Console   Fabric site Global/Poland/Krakow validation completed

Verify Fabric Site Global/Poland/Warsaw
    Log To Console   Validating fabric site Global/Poland/Warsaw
    # Check if this site should be skipped based on MANAGED_SITES
    ${should_skip}=   Should Skip Site Validation   Global/Poland/Warsaw
    Pass Execution If   ${should_skip}   Fabric site Global/Poland/Warsaw not managed by this deployment state - skipping validation
    # Validate that the site exists in the Sites API response
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='Global/Poland/Warsaw')]
    Run Keyword If   not ${site_data}   Fail   Site Global/Poland/Warsaw not found in Catalyst Center - deployment issue
    # Extract site information
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    Log To Console   Site ID for Global/Poland/Warsaw: ${site_id}
    # Validate that the fabric site exists in the Fabric Sites API response
    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found in Fabric Sites API response.
    # Extract fabric information
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id
    Log To Console   Fabric site ID: ${fabric_id}
    # Validate fabric site attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${fabric_entry}   $.authenticationProfileName   Closed Authentication
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${fabric_entry}   $.isPubSubEnabled   True
    Log To Console   Fabric site Global/Poland/Warsaw validation completed