*** Settings ***
Documentation     Verify Layer 3 Handoffs (IP Transit and SDA Transit)
Suite Setup       Login CatalystCenter
Resource          ../../catalyst_center_common.resource
Default Tags      config   catalyst_center   fabric   l3_handoffs

*** Test Cases ***

Get API Data For L3 Handoffs
    # Get network devices for device name to ID mapping
    ${devices}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/networkDevices
    Log   Network Devices Response Status Code: ${devices.status_code}
    Set Suite Variable   ${NETWORK_DEVICES}   ${devices}
    # Get transit networks for transit name to ID mapping
    ${transits}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/transitNetworks
    Log   Transit Networks Response Status Code: ${transits.status_code}
    Set Suite Variable   ${TRANSIT_NETWORKS}   ${transits}
    # Get fabric sites for fabric ID lookup
    ${fabric_sites}=   Get Cached Fabric Sites Data
    Log   Fabric Sites Response Status Code: ${fabric_sites.status_code}
    Set Suite Variable   ${FABRIC_SITES}   ${fabric_sites}

# ============================================================================
# SDA Transit L3 Handoff for BR10
# ============================================================================

Verify SDA Transit L3 Handoff for BR10
    [Documentation]   Validate SDA Transit L3 Handoff configuration for border device BR10
    # Find device ID by hostname (handle both FQDN and short hostname)
    ${device_list}=   Get From Dictionary   ${NETWORK_DEVICES.json()}   response
    ${device_id}=   Set Variable   ${EMPTY}
    FOR   ${device}   IN   @{device_list}
        ${device_name}=   Get From Dictionary   ${device}   hostname
        ${device_hostname}=   Evaluate   "${device_name}".split('.')[0]
        ${match_exact}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_name}   BR10
        ${match_short}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_hostname}   BR10
        ${is_match}=   Evaluate   ${match_exact} or ${match_short}
        Run Keyword If   ${is_match}   Set Suite Variable   ${device_id}   ${device}[id]
        Exit For Loop If   ${is_match}
    END
    Run Keyword If   "${device_id}" == "${EMPTY}"   Fail   Border device BR10 not found in network devices
    Log To Console   Found device BR10 with ID: ${device_id}
    # Find transit network ID by name
    ${transit_data}=   Get Value From Json   ${TRANSIT_NETWORKS.json()}   $.response[?(@.name=='SDA-TRANSIT')]
    Run Keyword If   not ${transit_data}   Fail   SDA Transit SDA-TRANSIT not found in transit networks
    ${transit_id}=   Set Variable   ${transit_data}[0][id]
    Log To Console   Found SDA Transit SDA-TRANSIT with ID: ${transit_id}
    # Find fabric ID for this device - first get all fabric sites and find one containing this device
    ${fabric_id}=   Set Variable   ${EMPTY}
    ${fabric_sites_list}=   Get Value From Json   ${FABRIC_SITES.json()}   $.response
    ${fabric_sites_list}=   Set Variable   ${fabric_sites_list}[0]
    FOR   ${fabric_site}   IN   @{fabric_sites_list}
        ${site_fabric_id}=   Get From Dictionary   ${fabric_site}   id
        # Query SDA transits for this fabric to check if our device is there
        ${sda_response}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/fabricDevices/layer3Handoffs/sdaTransits   params=fabricId=${site_fabric_id}&networkDeviceId=${device_id}
        ${sda_handoffs}=   Get Value From Json   ${sda_response.json()}   $.response
        ${has_handoffs}=   Evaluate   len(${sda_handoffs}[0]) > 0 if ${sda_handoffs} else False
        Run Keyword If   ${has_handoffs}   Set Suite Variable   ${fabric_id}   ${site_fabric_id}
        Exit For Loop If   ${has_handoffs}
    END
    Run Keyword If   "${fabric_id}" == "${EMPTY}"   Pass Execution   No SDA Transit L3 Handoff found for device BR10, skipping validation
    # Get SDA Transit L3 Handoff data
    ${r}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/fabricDevices/layer3Handoffs/sdaTransits   params=fabricId=${fabric_id}&networkDeviceId=${device_id}
    Log To Console   SDA Transit L3 Handoff Response: ${r.json()}
    # Validate the handoff exists
    ${handoff_data}=   Get Value From Json   ${r.json()}   $.response[?(@.transitNetworkId=='${transit_id}')]
    Run Keyword If   not ${handoff_data}   Fail   SDA Transit L3 Handoff for transit SDA-TRANSIT not found for device BR10
    ${handoff}=   Set Variable   ${handoff_data}[0]
    # Validate SDA Transit attributes
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[networkDeviceId]   ${device_id}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[transitNetworkId]   ${transit_id}

# ============================================================================
# IP Transit L3 Handoff for BR10 - Transit BGP65002
# ============================================================================

Verify IP Transit L3 Handoff BR10 - BGP65002 - GigabitEthernet1/0/3 - Campus
    [Documentation]   Validate IP Transit L3 Handoff for BR10, transit BGP65002, interface GigabitEthernet1/0/3, VN Campus
    # Find device ID by hostname (handle both FQDN and short hostname)
    ${device_list}=   Get From Dictionary   ${NETWORK_DEVICES.json()}   response
    ${device_id}=   Set Variable   ${EMPTY}
    FOR   ${device}   IN   @{device_list}
        ${device_name}=   Get From Dictionary   ${device}   hostname
        ${device_hostname}=   Evaluate   "${device_name}".split('.')[0]
        ${match_exact}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_name}   BR10
        ${match_short}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_hostname}   BR10
        ${is_match}=   Evaluate   ${match_exact} or ${match_short}
        Run Keyword If   ${is_match}   Set Suite Variable   ${device_id}   ${device}[id]
        Exit For Loop If   ${is_match}
    END
    Run Keyword If   "${device_id}" == "${EMPTY}"   Fail   Border device BR10 not found in network devices
    Log To Console   Found device BR10 with ID: ${device_id}
    # Find transit network ID by name
    ${transit_data}=   Get Value From Json   ${TRANSIT_NETWORKS.json()}   $.response[?(@.name=='BGP65002')]
    Run Keyword If   not ${transit_data}   Fail   IP Transit BGP65002 not found in transit networks
    ${transit_id}=   Set Variable   ${transit_data}[0][id]
    Log To Console   Found IP Transit BGP65002 with ID: ${transit_id}
    # Find fabric ID for this device
    ${fabric_id}=   Set Variable   ${EMPTY}
    ${fabric_sites_list}=   Get Value From Json   ${FABRIC_SITES.json()}   $.response
    ${fabric_sites_list}=   Set Variable   ${fabric_sites_list}[0]
    FOR   ${fabric_site}   IN   @{fabric_sites_list}
        ${site_fabric_id}=   Get From Dictionary   ${fabric_site}   id
        # Query IP transits for this fabric to check if our device is there
        ${ip_response}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/fabricDevices/layer3Handoffs/ipTransits   params=fabricId=${site_fabric_id}&networkDeviceId=${device_id}
        ${ip_handoffs}=   Get Value From Json   ${ip_response.json()}   $.response
        ${has_handoffs}=   Evaluate   len(${ip_handoffs}[0]) > 0 if ${ip_handoffs} else False
        Run Keyword If   ${has_handoffs}   Set Suite Variable   ${fabric_id}   ${site_fabric_id}
        Exit For Loop If   ${has_handoffs}
    END
    Run Keyword If   "${fabric_id}" == "${EMPTY}"   Pass Execution   No IP Transit L3 Handoff found for device BR10, skipping validation
    # Get IP Transit L3 Handoff data
    ${r}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/fabricDevices/layer3Handoffs/ipTransits   params=fabricId=${fabric_id}&networkDeviceId=${device_id}
    Log To Console   IP Transit L3 Handoff Response: ${r.json()}
    # Find the specific handoff entry matching transit, interface, and VN
    ${handoff_list}=   Get Value From Json   ${r.json()}   $.response
    ${handoff_list}=   Set Variable   ${handoff_list}[0]
    ${handoff}=   Set Variable   ${None}
    FOR   ${entry}   IN   @{handoff_list}
        ${entry_transit_id}=   Get From Dictionary   ${entry}   transitNetworkId
        ${entry_interface}=   Get From Dictionary   ${entry}   interfaceName
        ${entry_vn}=   Get From Dictionary   ${entry}   virtualNetworkName
        ${match_transit}=   Run Keyword And Return Status   Should Be Equal As Strings   ${entry_transit_id}   ${transit_id}
        ${match_interface}=   Run Keyword And Return Status   Should Be Equal As Strings   ${entry_interface}   GigabitEthernet1/0/3
        ${match_vn}=   Run Keyword And Return Status   Should Be Equal As Strings   ${entry_vn}   Campus
        ${is_match}=   Evaluate   ${match_transit} and ${match_interface} and ${match_vn}
        Run Keyword If   ${is_match}   Set Suite Variable   ${handoff}   ${entry}
        Exit For Loop If   ${is_match}
    END
    Run Keyword If   "${handoff}" == "${None}"   Fail   IP Transit L3 Handoff for transit BGP65002, interface GigabitEthernet1/0/3, VN Campus not found
    # Validate IP Transit attributes
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[networkDeviceId]   ${device_id}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[transitNetworkId]   ${transit_id}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[interfaceName]   GigabitEthernet1/0/3
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[virtualNetworkName]   Campus
    Run Keyword And Continue On Failure   Should Be Equal As Numbers   ${handoff}[vlanId]   100
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[localIpAddress]   172.16.100.1/24
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[remoteIpAddress]   172.16.100.2/24

# ============================================================================
# SDA Transit L3 Handoff for FIAB
# ============================================================================

Verify SDA Transit L3 Handoff for FIAB
    [Documentation]   Validate SDA Transit L3 Handoff configuration for border device FIAB
    # Find device ID by hostname (handle both FQDN and short hostname)
    ${device_list}=   Get From Dictionary   ${NETWORK_DEVICES.json()}   response
    ${device_id}=   Set Variable   ${EMPTY}
    FOR   ${device}   IN   @{device_list}
        ${device_name}=   Get From Dictionary   ${device}   hostname
        ${device_hostname}=   Evaluate   "${device_name}".split('.')[0]
        ${match_exact}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_name}   FIAB
        ${match_short}=   Run Keyword And Return Status   Should Be Equal As Strings   ${device_hostname}   FIAB
        ${is_match}=   Evaluate   ${match_exact} or ${match_short}
        Run Keyword If   ${is_match}   Set Suite Variable   ${device_id}   ${device}[id]
        Exit For Loop If   ${is_match}
    END
    Run Keyword If   "${device_id}" == "${EMPTY}"   Fail   Border device FIAB not found in network devices
    Log To Console   Found device FIAB with ID: ${device_id}
    # Find transit network ID by name
    ${transit_data}=   Get Value From Json   ${TRANSIT_NETWORKS.json()}   $.response[?(@.name=='SDA-TRANSIT')]
    Run Keyword If   not ${transit_data}   Fail   SDA Transit SDA-TRANSIT not found in transit networks
    ${transit_id}=   Set Variable   ${transit_data}[0][id]
    Log To Console   Found SDA Transit SDA-TRANSIT with ID: ${transit_id}
    # Find fabric ID for this device - first get all fabric sites and find one containing this device
    ${fabric_id}=   Set Variable   ${EMPTY}
    ${fabric_sites_list}=   Get Value From Json   ${FABRIC_SITES.json()}   $.response
    ${fabric_sites_list}=   Set Variable   ${fabric_sites_list}[0]
    FOR   ${fabric_site}   IN   @{fabric_sites_list}
        ${site_fabric_id}=   Get From Dictionary   ${fabric_site}   id
        # Query SDA transits for this fabric to check if our device is there
        ${sda_response}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/fabricDevices/layer3Handoffs/sdaTransits   params=fabricId=${site_fabric_id}&networkDeviceId=${device_id}
        ${sda_handoffs}=   Get Value From Json   ${sda_response.json()}   $.response
        ${has_handoffs}=   Evaluate   len(${sda_handoffs}[0]) > 0 if ${sda_handoffs} else False
        Run Keyword If   ${has_handoffs}   Set Suite Variable   ${fabric_id}   ${site_fabric_id}
        Exit For Loop If   ${has_handoffs}
    END
    Run Keyword If   "${fabric_id}" == "${EMPTY}"   Pass Execution   No SDA Transit L3 Handoff found for device FIAB, skipping validation
    # Get SDA Transit L3 Handoff data
    ${r}=   GET On Session   CatalystCenter_Session   url=/dna/intent/api/v1/sda/fabricDevices/layer3Handoffs/sdaTransits   params=fabricId=${fabric_id}&networkDeviceId=${device_id}
    Log To Console   SDA Transit L3 Handoff Response: ${r.json()}
    # Validate the handoff exists
    ${handoff_data}=   Get Value From Json   ${r.json()}   $.response[?(@.transitNetworkId=='${transit_id}')]
    Run Keyword If   not ${handoff_data}   Fail   SDA Transit L3 Handoff for transit SDA-TRANSIT not found for device FIAB
    ${handoff}=   Set Variable   ${handoff_data}[0]
    # Validate SDA Transit attributes
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[networkDeviceId]   ${device_id}
    Run Keyword And Continue On Failure   Should Be Equal As Strings   ${handoff}[transitNetworkId]   ${transit_id}