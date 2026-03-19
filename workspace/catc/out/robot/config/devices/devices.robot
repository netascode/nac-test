*** Settings ***
Documentation     Verify Device Inventory in Catalyst Center
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   inventory   devices

*** Test Cases ***

Get Device Inventory
    ${r}=   Get Cached Network Devices Data
    Log     Response Status Code: ${r.status_code}
    Log To Console   API Response: ${r.json()}
    Set Suite Variable   ${r}

Get Device Tags
    ${tags_response}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/tags/networkDevices/membersAssociations
    Log   Response Status Code (Device Tags): ${tags_response.status_code}
    Log To Console   Device Tags API Response: ${tags_response.json()}
    Set Suite Variable   ${DEVICE_TAGS_RESPONSE}   ${tags_response}

Verify Device BR10
    Run Keyword If   'PROVISION' == 'PNP'   Pass Execution   Skipping further steps as device is in PNP process
    Run Keyword If   'PROVISION' == 'INIT'   Pass Execution   Skipping further steps as device is in INIT state
    # Validate that the device exists in the API response
    ${device_data}=   Get Value From Json   ${r.json()}   $.response[?(@.name=='BR10')]
    ${device_data}=   Run Keyword If   ${device_data} == []   Get Value From Json   ${r.json()}   $.response[?(@.name=='BR10.cisco.eu')]   ELSE   Set Variable   ${device_data}
    Run Keyword If    not ${device_data}    Fail    Device BR10 or BR10.cisco.eu not found in API response.
    # Extract the first matching device from the API response
    ${device_entry}=   Set Variable   ${device_data}[0]
    Log To Console   Extracted Device Entry: ${device_entry}
    # Validate device attributes
    ${name_matches}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_entry['name']}   BR10
    Run Keyword If   not ${name_matches}   Should Be Equal As Strings   ${device_entry['name']}   BR10.cisco.eu
    Should Be Equal As Strings   ${device_entry['managementIpAddress']}   198.18.130.10
    Should Be Equal As Strings   ${device_entry['platformId'].split(',')[0].strip()}    C9KV-UADP-8P
    Should Be Equal As Strings   ${device_entry['deviceRole']}   BORDER ROUTER
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.id=='${device_entry['siteId']}')]
    ${site_entry}=   Set Variable   ${site_data}[0]
    Log To Console   Extracted stedata: ${site_entry}
    Should Be Equal As Strings   ${site_entry['nameHierarchy']}   Global/Poland/Krakow/Bld A
    # Validate device tags if defined in data model
Verify Device EDGE01
    Run Keyword If   'PROVISION' == 'PNP'   Pass Execution   Skipping further steps as device is in PNP process
    Run Keyword If   'PROVISION' == 'INIT'   Pass Execution   Skipping further steps as device is in INIT state
    # Validate that the device exists in the API response
    ${device_data}=   Get Value From Json   ${r.json()}   $.response[?(@.name=='EDGE01')]
    ${device_data}=   Run Keyword If   ${device_data} == []   Get Value From Json   ${r.json()}   $.response[?(@.name=='EDGE01.cisco.eu')]   ELSE   Set Variable   ${device_data}
    Run Keyword If    not ${device_data}    Fail    Device EDGE01 or EDGE01.cisco.eu not found in API response.
    # Extract the first matching device from the API response
    ${device_entry}=   Set Variable   ${device_data}[0]
    Log To Console   Extracted Device Entry: ${device_entry}
    # Validate device attributes
    ${name_matches}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_entry['name']}   EDGE01
    Run Keyword If   not ${name_matches}   Should Be Equal As Strings   ${device_entry['name']}   EDGE01.cisco.eu
    Should Be Equal As Strings   ${device_entry['managementIpAddress']}   198.18.130.1
    Should Be Equal As Strings   ${device_entry['platformId'].split(',')[0].strip()}    C9KV-UADP-8P
    Should Be Equal As Strings   ${device_entry['deviceRole']}   ACCESS
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.id=='${device_entry['siteId']}')]
    ${site_entry}=   Set Variable   ${site_data}[0]
    Log To Console   Extracted stedata: ${site_entry}
    Should Be Equal As Strings   ${site_entry['nameHierarchy']}   Global/Poland/Krakow/Bld A
    # Validate device tags if defined in data model
Verify Device EDGE02
    Run Keyword If   'PROVISION' == 'PNP'   Pass Execution   Skipping further steps as device is in PNP process
    Run Keyword If   'PROVISION' == 'INIT'   Pass Execution   Skipping further steps as device is in INIT state
    # Validate that the device exists in the API response
    ${device_data}=   Get Value From Json   ${r.json()}   $.response[?(@.name=='EDGE02')]
    ${device_data}=   Run Keyword If   ${device_data} == []   Get Value From Json   ${r.json()}   $.response[?(@.name=='EDGE02.cisco.eu')]   ELSE   Set Variable   ${device_data}
    Run Keyword If    not ${device_data}    Fail    Device EDGE02 or EDGE02.cisco.eu not found in API response.
    # Extract the first matching device from the API response
    ${device_entry}=   Set Variable   ${device_data}[0]
    Log To Console   Extracted Device Entry: ${device_entry}
    # Validate device attributes
    ${name_matches}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_entry['name']}   EDGE02
    Run Keyword If   not ${name_matches}   Should Be Equal As Strings   ${device_entry['name']}   EDGE02.cisco.eu
    Should Be Equal As Strings   ${device_entry['managementIpAddress']}   198.18.130.2
    Should Be Equal As Strings   ${device_entry['platformId'].split(',')[0].strip()}    C9KV-UADP-8P
    Should Be Equal As Strings   ${device_entry['deviceRole']}   ACCESS
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.id=='${device_entry['siteId']}')]
    ${site_entry}=   Set Variable   ${site_data}[0]
    Log To Console   Extracted stedata: ${site_entry}
    Should Be Equal As Strings   ${site_entry['nameHierarchy']}   Global/Poland/Krakow/Bld A
    # Validate device tags if defined in data model
Verify Device FIAB
    Run Keyword If   'PROVISION' == 'PNP'   Pass Execution   Skipping further steps as device is in PNP process
    Run Keyword If   'PROVISION' == 'INIT'   Pass Execution   Skipping further steps as device is in INIT state
    # Validate that the device exists in the API response
    ${device_data}=   Get Value From Json   ${r.json()}   $.response[?(@.name=='FIAB')]
    ${device_data}=   Run Keyword If   ${device_data} == []   Get Value From Json   ${r.json()}   $.response[?(@.name=='FIAB.cisco.eu')]   ELSE   Set Variable   ${device_data}
    Run Keyword If    not ${device_data}    Fail    Device FIAB or FIAB.cisco.eu not found in API response.
    # Extract the first matching device from the API response
    ${device_entry}=   Set Variable   ${device_data}[0]
    Log To Console   Extracted Device Entry: ${device_entry}
    # Validate device attributes
    ${name_matches}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_entry['name']}   FIAB
    Run Keyword If   not ${name_matches}   Should Be Equal As Strings   ${device_entry['name']}   FIAB.cisco.eu
    Should Be Equal As Strings   ${device_entry['managementIpAddress']}   198.18.130.33
    Should Be Equal As Strings   ${device_entry['platformId'].split(',')[0].strip()}    C9KV-UADP-8P
    Should Be Equal As Strings   ${device_entry['deviceRole']}   BORDER ROUTER
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.id=='${device_entry['siteId']}')]
    ${site_entry}=   Set Variable   ${site_data}[0]
    Log To Console   Extracted stedata: ${site_entry}
    Should Be Equal As Strings   ${site_entry['nameHierarchy']}   Global/Poland/Warsaw/Bld_B
    # Validate device tags if defined in data model
Verify Device Transit-CP-1
    Run Keyword If   'PROVISION' == 'PNP'   Pass Execution   Skipping further steps as device is in PNP process
    Run Keyword If   'PROVISION' == 'INIT'   Pass Execution   Skipping further steps as device is in INIT state
    # Validate that the device exists in the API response
    ${device_data}=   Get Value From Json   ${r.json()}   $.response[?(@.name=='Transit-CP-1')]
    ${device_data}=   Run Keyword If   ${device_data} == []   Get Value From Json   ${r.json()}   $.response[?(@.name=='Transit-CP-1.cisco.eu')]   ELSE   Set Variable   ${device_data}
    Run Keyword If    not ${device_data}    Fail    Device Transit-CP-1 or Transit-CP-1.cisco.eu not found in API response.
    # Extract the first matching device from the API response
    ${device_entry}=   Set Variable   ${device_data}[0]
    Log To Console   Extracted Device Entry: ${device_entry}
    # Validate device attributes
    ${name_matches}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_entry['name']}   Transit-CP-1
    Run Keyword If   not ${name_matches}   Should Be Equal As Strings   ${device_entry['name']}   Transit-CP-1.cisco.eu
    Should Be Equal As Strings   ${device_entry['managementIpAddress']}   198.18.130.34
    Should Be Equal As Strings   ${device_entry['platformId'].split(',')[0].strip()}    C8000V
    Should Be Equal As Strings   ${device_entry['deviceRole']}   BORDER ROUTER
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.id=='${device_entry['siteId']}')]
    ${site_entry}=   Set Variable   ${site_data}[0]
    Log To Console   Extracted stedata: ${site_entry}
    Should Be Equal As Strings   ${site_entry['nameHierarchy']}   Global/Poland/Warsaw/Bld_B
    # Validate device tags if defined in data model
Verify Device C9800-CL-WLC
    Run Keyword If   'PROVISION' == 'PNP'   Pass Execution   Skipping further steps as device is in PNP process
    Run Keyword If   'PROVISION' == 'INIT'   Pass Execution   Skipping further steps as device is in INIT state
    # Validate that the device exists in the API response
    ${device_data}=   Get Value From Json   ${r.json()}   $.response[?(@.name=='C9800-CL-WLC')]
    ${device_data}=   Run Keyword If   ${device_data} == []   Get Value From Json   ${r.json()}   $.response[?(@.name=='C9800-CL-WLC.cisco.eu')]   ELSE   Set Variable   ${device_data}
    Run Keyword If    not ${device_data}    Fail    Device C9800-CL-WLC or C9800-CL-WLC.cisco.eu not found in API response.
    # Extract the first matching device from the API response
    ${device_entry}=   Set Variable   ${device_data}[0]
    Log To Console   Extracted Device Entry: ${device_entry}
    # Validate device attributes
    ${name_matches}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_entry['name']}   C9800-CL-WLC
    Run Keyword If   not ${name_matches}   Should Be Equal As Strings   ${device_entry['name']}   C9800-CL-WLC.cisco.eu
    Should Be Equal As Strings   ${device_entry['managementIpAddress']}   198.18.130.35
    Should Be Equal As Strings   ${device_entry['platformId'].split(',')[0].strip()}    C9800-CL-K9
    Should Be Equal As Strings   ${device_entry['deviceRole']}   ACCESS
    ${s}=   Get Cached Sites Data
    ${site_data}=   Get Value From Json   ${s.json()}   $.response[?(@.id=='${device_entry['siteId']}')]
    ${site_entry}=   Set Variable   ${site_data}[0]
    Log To Console   Extracted stedata: ${site_entry}
    Should Be Equal As Strings   ${site_entry['nameHierarchy']}   Global/Poland/Warsaw/Bld_B
    # Validate device tags if defined in data model