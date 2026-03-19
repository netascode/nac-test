*** Settings ***
Documentation     Verify Transit Networks
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   transits

*** Test Cases ***

Get Transit Networks
    ${r}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/transitNetworks
    ${d}=   GET On Session   CatalystCenter_Session   /dna/data/api/v1/networkDevices
    Log   Response Status Code (Transit Networks): ${r.status_code}
    Log   Response Status Code (Network Devices): ${d.status_code}
    Log To Console   Transit Networks API Response: ${r.json()}
    Set Suite Variable   ${r}
    Set Suite Variable   ${d}

Verify Transit BGP65002
    # Validate that the transit exists in the API response
    ${transit_data}=   Get Value From Json   ${r.json()}   $.response[?(@.name=='BGP65002')]
    Log To Console   Transit data: ${transit_data}
    Run Keyword If   not ${transit_data}   Fail   Transit BGP65002 not found in Transit Networks API response.
    # Extract the matching transit
    ${t}=   Set Variable   ${transit_data}[0]
    Log To Console   Extracted Transit Entry: ${t}
    # Validate basic transit attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.name   BGP65002
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.type   IP_BASED_TRANSIT
    # Validate IP Transit Settings
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.ipTransitSettings.routingProtocolName   BGP
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.ipTransitSettings.autonomousSystemNumber   65002

Verify Transit SDA-TRANSIT
    # Validate that the transit exists in the API response
    ${transit_data}=   Get Value From Json   ${r.json()}   $.response[?(@.name=='SDA-TRANSIT')]
    Log To Console   Transit data: ${transit_data}
    Run Keyword If   not ${transit_data}   Fail   Transit SDA-TRANSIT not found in Transit Networks API response.
    # Extract the matching transit
    ${t}=   Set Variable   ${transit_data}[0]
    Log To Console   Extracted Transit Entry: ${t}
    # Validate basic transit attributes
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.name   SDA-TRANSIT
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.type   SDA_LISP_PUB_SUB_TRANSIT
    # Validate SDA Transit Settings
    # Map device IDs to device names and validate
    ${device_ids_result}=   Get Value From Json   ${t}   $.sdaTransitSettings.controlPlaneNetworkDeviceIds
    ${device_ids}=   Set Variable   ${device_ids_result}[0]
    ${actual_device_names}=   Create List
    ${actual_device_hostnames}=   Create List
    FOR   ${device_id}   IN   @{device_ids}
        ${device_data}=   Get Value From Json   ${d.json()}   $.response[?(@.id=='${device_id}')]
        Run Keyword If   not ${device_data}   Fail   Device ID ${device_id} not found in network devices API response.
        ${device_entry}=   Set Variable   ${device_data}[0]
        ${device_name}=   Get From Dictionary   ${device_entry}   name
        Append To List   ${actual_device_names}   ${device_name}
        # Extract hostname by splitting on first dot
        ${hostname}=   Evaluate   "${device_name}".split('.')[0]
        Append To List   ${actual_device_hostnames}   ${hostname}
    END
    Log To Console   Control plane devices - Expected: Transit-CP-1, Actual: ${actual_device_names}, Hostnames: ${actual_device_hostnames}
    # Validate each expected device name is present (check both FQDN and hostname)
    # Handle both string and object formats for device references
    # Simple string format - check against both full names and hostnames
    ${device_found_fqdn}=   Run Keyword And Return Status   List Should Contain Value   ${actual_device_names}   Transit-CP-1
    ${device_found_hostname}=   Run Keyword And Return Status   List Should Contain Value   ${actual_device_hostnames}   Transit-CP-1
    ${device_found}=   Evaluate   ${device_found_fqdn} or ${device_found_hostname}
    Run Keyword If   not ${device_found}   Fail   Device Transit-CP-1 not found in control plane devices list: ${actual_device_names} (hostnames: ${actual_device_hostnames})
    # Validate multicast over transit setting
    Run Keyword And Continue On Failure   Should Be Equal Value Json String   ${t}   $.sdaTransitSettings.isMulticastOverTransitEnabled   False