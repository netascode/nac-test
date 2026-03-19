*** Settings ***
Documentation     Verify L3 Virtual Networks Association for Fabric Sites and Fabric Zones
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   l3_virtual_networks

*** Test Cases ***

Get Fabric Zones
    ${z}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/fabricZones
    Log   Response Status Code (Fabric Zones): ${z.status_code}
    Set Suite Variable   ${z}

Get L3 Virtual Networks
    ${l}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/layer3VirtualNetworks
    Log   Response Status Code (L3 Virtual Networks): ${l.status_code}
    Set Suite Variable   ${l}

Verify L3 Virtual Networks for Fabric Site Global/Poland/Krakow
    Log To Console   Validating L3 virtual networks for fabric site Global/Poland/Krakow
    # Step 1: Get fabric site ID
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='Global/Poland/Krakow')]
    ${site_count}=   Get Length   ${site_data}
    Run Keyword If   ${site_count} == 0   Log To Console   Skipping site association check - Site Global/Poland/Krakow not deployed yet (GLOBAL state)
    Pass Execution If   ${site_count} == 0   Site Global/Poland/Krakow not deployed - skipping validation
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found in Fabric Sites API response.
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id
    Log To Console   Fabric site ID: ${fabric_id}
    # Step 2: Validate L3 Virtual Networks association
    ${network_data}=   Get Value From Json   ${l.json()}   $.response[?(@.virtualNetworkName=='BYOD')]
    Run Keyword If   not ${network_data}   Fail   L3 Virtual Network BYOD not found in L3 Virtual Networks API response.
    ${network_entry}=   Set Variable   ${network_data}[0]
    # Validate that the fabricId is associated with the L3 Virtual Network
    ${fabric_ids}=   Get From Dictionary   ${network_entry}   fabricIds
    Run Keyword And Continue On Failure   List Should Contain Value   ${fabric_ids}   ${fabric_id}   L3 Virtual Network BYOD not associated with fabric site Global/Poland/Krakow
    Log To Console   L3 Virtual Network BYOD associated with fabric site Global/Poland/Krakow
    ${network_data}=   Get Value From Json   ${l.json()}   $.response[?(@.virtualNetworkName=='Guest')]
    Run Keyword If   not ${network_data}   Fail   L3 Virtual Network Guest not found in L3 Virtual Networks API response.
    ${network_entry}=   Set Variable   ${network_data}[0]
    # Validate that the fabricId is associated with the L3 Virtual Network
    ${fabric_ids}=   Get From Dictionary   ${network_entry}   fabricIds
    Run Keyword And Continue On Failure   List Should Contain Value   ${fabric_ids}   ${fabric_id}   L3 Virtual Network Guest not associated with fabric site Global/Poland/Krakow
    Log To Console   L3 Virtual Network Guest associated with fabric site Global/Poland/Krakow
    ${network_data}=   Get Value From Json   ${l.json()}   $.response[?(@.virtualNetworkName=='Printers')]
    Run Keyword If   not ${network_data}   Fail   L3 Virtual Network Printers not found in L3 Virtual Networks API response.
    ${network_entry}=   Set Variable   ${network_data}[0]
    # Validate that the fabricId is associated with the L3 Virtual Network
    ${fabric_ids}=   Get From Dictionary   ${network_entry}   fabricIds
    Run Keyword And Continue On Failure   List Should Contain Value   ${fabric_ids}   ${fabric_id}   L3 Virtual Network Printers not associated with fabric site Global/Poland/Krakow
    Log To Console   L3 Virtual Network Printers associated with fabric site Global/Poland/Krakow
    ${network_data}=   Get Value From Json   ${l.json()}   $.response[?(@.virtualNetworkName=='Campus')]
    Run Keyword If   not ${network_data}   Fail   L3 Virtual Network Campus not found in L3 Virtual Networks API response.
    ${network_entry}=   Set Variable   ${network_data}[0]
    # Validate that the fabricId is associated with the L3 Virtual Network
    ${fabric_ids}=   Get From Dictionary   ${network_entry}   fabricIds
    Run Keyword And Continue On Failure   List Should Contain Value   ${fabric_ids}   ${fabric_id}   L3 Virtual Network Campus not associated with fabric site Global/Poland/Krakow
    Log To Console   L3 Virtual Network Campus associated with fabric site Global/Poland/Krakow
    Log To Console   L3 virtual networks validation completed for fabric site Global/Poland/Krakow

Verify L3 Virtual Networks for Fabric Site Global/Poland/Warsaw
    Log To Console   Validating L3 virtual networks for fabric site Global/Poland/Warsaw
    # Step 1: Get fabric site ID
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.nameHierarchy=='Global/Poland/Warsaw')]
    ${site_count}=   Get Length   ${site_data}
    Run Keyword If   ${site_count} == 0   Log To Console   Skipping site association check - Site Global/Poland/Warsaw not deployed yet (GLOBAL state)
    Pass Execution If   ${site_count} == 0   Site Global/Poland/Warsaw not deployed - skipping validation
    ${site_entry}=   Set Variable   ${site_data}[0]
    ${site_id}=   Get From Dictionary   ${site_entry}   id
    ${f}=   Get Cached Fabric Sites Data
    ${fabric_data}=   Get Value From Json   ${f.json()}   $.response[?(@.siteId=='${site_id}')]
    Run Keyword If   not ${fabric_data}   Fail   Fabric site with siteId ${site_id} not found in Fabric Sites API response.
    ${fabric_entry}=   Set Variable   ${fabric_data}[0]
    ${fabric_id}=   Get From Dictionary   ${fabric_entry}   id
    Log To Console   Fabric site ID: ${fabric_id}
    # Step 2: Validate L3 Virtual Networks association
    ${network_data}=   Get Value From Json   ${l.json()}   $.response[?(@.virtualNetworkName=='BYOD')]
    Run Keyword If   not ${network_data}   Fail   L3 Virtual Network BYOD not found in L3 Virtual Networks API response.
    ${network_entry}=   Set Variable   ${network_data}[0]
    # Validate that the fabricId is associated with the L3 Virtual Network
    ${fabric_ids}=   Get From Dictionary   ${network_entry}   fabricIds
    Run Keyword And Continue On Failure   List Should Contain Value   ${fabric_ids}   ${fabric_id}   L3 Virtual Network BYOD not associated with fabric site Global/Poland/Warsaw
    Log To Console   L3 Virtual Network BYOD associated with fabric site Global/Poland/Warsaw
    ${network_data}=   Get Value From Json   ${l.json()}   $.response[?(@.virtualNetworkName=='Guest')]
    Run Keyword If   not ${network_data}   Fail   L3 Virtual Network Guest not found in L3 Virtual Networks API response.
    ${network_entry}=   Set Variable   ${network_data}[0]
    # Validate that the fabricId is associated with the L3 Virtual Network
    ${fabric_ids}=   Get From Dictionary   ${network_entry}   fabricIds
    Run Keyword And Continue On Failure   List Should Contain Value   ${fabric_ids}   ${fabric_id}   L3 Virtual Network Guest not associated with fabric site Global/Poland/Warsaw
    Log To Console   L3 Virtual Network Guest associated with fabric site Global/Poland/Warsaw
    ${network_data}=   Get Value From Json   ${l.json()}   $.response[?(@.virtualNetworkName=='Printers')]
    Run Keyword If   not ${network_data}   Fail   L3 Virtual Network Printers not found in L3 Virtual Networks API response.
    ${network_entry}=   Set Variable   ${network_data}[0]
    # Validate that the fabricId is associated with the L3 Virtual Network
    ${fabric_ids}=   Get From Dictionary   ${network_entry}   fabricIds
    Run Keyword And Continue On Failure   List Should Contain Value   ${fabric_ids}   ${fabric_id}   L3 Virtual Network Printers not associated with fabric site Global/Poland/Warsaw
    Log To Console   L3 Virtual Network Printers associated with fabric site Global/Poland/Warsaw
    ${network_data}=   Get Value From Json   ${l.json()}   $.response[?(@.virtualNetworkName=='Campus')]
    Run Keyword If   not ${network_data}   Fail   L3 Virtual Network Campus not found in L3 Virtual Networks API response.
    ${network_entry}=   Set Variable   ${network_data}[0]
    # Validate that the fabricId is associated with the L3 Virtual Network
    ${fabric_ids}=   Get From Dictionary   ${network_entry}   fabricIds
    Run Keyword And Continue On Failure   List Should Contain Value   ${fabric_ids}   ${fabric_id}   L3 Virtual Network Campus not associated with fabric site Global/Poland/Warsaw
    Log To Console   L3 Virtual Network Campus associated with fabric site Global/Poland/Warsaw
    Log To Console   L3 virtual networks validation completed for fabric site Global/Poland/Warsaw