*** Settings ***
Documentation     Verify Fabric Multicast Configurations in Catalyst Center
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   multicast   site_specific

*** Test Cases ***

Get Fabric Sites Data
    ${fabric_sites}=   Get Cached Fabric Sites Data
    Set Suite Variable   ${fabric_sites}