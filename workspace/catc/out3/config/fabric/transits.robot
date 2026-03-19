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