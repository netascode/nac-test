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