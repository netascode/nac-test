*** Settings ***
Documentation     Verify L2 Virtual Networks Configuration
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   l2_virtual_networks

*** Test Cases ***

Get L2 Virtual Networks
    ${r}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/layer2VirtualNetworks
    Log   Response Status Code (L2 Virtual Networks): ${r.status_code}
    Log To Console   L2 Virtual Networks API Response: ${r.json()}
    Set Suite Variable   ${r}