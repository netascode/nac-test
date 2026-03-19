*** Settings ***
Library   pabot.PabotLib
Library   RequestsLibrary
Library   JSONLibrary
Library   Collections
Library   OperatingSystem

*** Keywords ***
Get CatalystCenter Token
    ${auth}=   Create List   %{CC_USERNAME}   %{CC_PASSWORD}
    ${cc_insecure}=   Get Environment Variable   CC_INSECURE   True
    ${verify}=   Set Variable If   '${cc_insecure}' == 'True' or '${cc_insecure}' == 'true'   False   True
    Create Session   CatalystCenter_Session   %{CC_URL}   auth=${auth}   verify=${verify}   headers={"Accept": "application/json", "Content-Type": "application/json"}
    ${response}=  POST On Session   CatalystCenter_Session   /api/system/v1/auth/token
    ${token}=     Set Variable   ${response.json()["Token"]}
    RETURN   ${token}

Login CatalystCenter
    ${token}=   Get CatalystCenter Token
    ${headers}=   Create Dictionary   x-auth-token=${token}
    Create Session   CatalystCenter_Session   %{CC_URL}   headers=${headers}

Should Be Equal Value Json String
    [Arguments]   ${json}   ${json_path}   ${value}=${EMPTY}
    ${r_value}=   Get Value From Json   ${json}   ${json_path}
    Run Keyword If   "${value}" != "${EMPTY}"   Should Be Equal As Strings   ${r_value}[0]   ${value}

Should Be Equal Value Json List
    [Arguments]   ${json}   ${json_path}   ${value}=${None}
    ${r_value}=   Get Value From Json   ${json}   ${json_path}
    Run Keyword If   "${value}" != "${None}"   Lists Should Be Equal   ${r_value}[0]   ${value}   ignore_order=True

Should Be Equal Value Json Boolean
    [Arguments]   ${json}   ${json_path}   ${value}=${EMPTY}
    ${r_value}=   Get Value From Json   ${json}   ${json_path}
    Run Keyword If   "${value}" != "${EMPTY}"   Should Be Equal As Strings   ${r_value}[0]   ${value}

Should Be Equal Value Json Number
    [Arguments]   ${json}   ${json_path}   ${value}=${EMPTY}
    ${r_value}=   Get Value From Json   ${json}   ${json_path}
    Run Keyword If   "${value}" != "${EMPTY}"   Should Be Equal As Numbers   ${r_value}[0]   ${value}

Get Sites Data
   ${count_response}=   GET On Session   CatalystCenter_Session
   ...   url=/dna/intent/api/v1/sites/count
   ${total_count}=   Get Value From Json   ${count_response.json()}   $.response.count
   ${count}=   Convert To Integer   ${total_count}[0]
   ${all_sites}=   Create List
   ${offset}=   Set Variable   ${1}
   ${limit}=   Set Variable   ${500}
   WHILE   ${offset} <= ${count}
       &{params}=   Create Dictionary   offset=${offset}   limit=${limit}
       ${s}=   GET On Session   CatalystCenter_Session
       ...   url=/dna/intent/api/v1/sites
       ...   params=${params}
       ${sites_batch}=   Get Value From Json   ${s.json()}   $.response
       FOR   ${site}   IN   @{sites_batch}[0]
           Append To List   ${all_sites}   ${site}
       END
       ${offset}=   Evaluate   ${offset} + ${limit}
   END
   ${total_fetched}=   Get Length   ${all_sites}
   ${complete_json}=   Create Dictionary   response=${all_sites}   version=1.0
   ${wrapper}=   Evaluate   (lambda d: type('Response', (), {'json': lambda s: d, 'status_code': 200})())(${complete_json})
   Set Global Variable   ${SITES_DATA}   ${wrapper}
   RETURN   ${wrapper}

Get Cached Sites Data
    # Check if sites data is already cached, if not fetch it
    ${sites_exists}=   Run Keyword And Return Status   Variable Should Exist   ${SITES_DATA}
    Run Keyword If   not ${sites_exists}   Get Sites Data
    RETURN   ${SITES_DATA}

Get Fabric Sites Data
    ${f}=   GET On Session   CatalystCenter_Session   /dna/intent/api/v1/sda/fabricSites
    Log   Fabric Sites Response Status Code: ${f.status_code}
    Set Global Variable   ${FABRIC_SITES_DATA}   ${f}
    RETURN   ${f}

Get Cached Fabric Sites Data
    # Check if fabric sites data is already cached, if not fetch it
    ${fabric_sites_exists}=   Run Keyword And Return Status   Variable Should Exist   ${FABRIC_SITES_DATA}
    Run Keyword If   not ${fabric_sites_exists}   Get Fabric Sites Data
    RETURN   ${FABRIC_SITES_DATA}

Get All Network Devices
    # First, try to get the count of devices
    ${count_response}=   GET On Session   CatalystCenter_Session
    ...   url=/dna/data/api/v1/networkDevices/count
    ${total_count}=   Get Value From Json   ${count_response.json()}   $.response.count
    ${count}=   Convert To Integer   ${total_count}[0]
    ${all_devices}=   Create List
    ${offset}=   Set Variable   ${1}
    ${limit}=   Set Variable   ${500}
    WHILE   ${offset} <= ${count}
        &{params}=   Create Dictionary   offset=${offset}   limit=${limit}
        ${d}=   GET On Session   CatalystCenter_Session
        ...   url=/dna/data/api/v1/networkDevices
        ...   params=${params}
        ${devices_batch}=   Get Value From Json   ${d.json()}   $.response
        FOR   ${device}   IN   @{devices_batch}[0]
            Append To List   ${all_devices}   ${device}
        END
        ${offset}=   Evaluate   ${offset} + ${limit}
    END
    ${total_fetched}=   Get Length   ${all_devices}
    ${complete_json}=   Create Dictionary   response=${all_devices}   version=1.0
    ${wrapper}=   Evaluate   (lambda d: type('Response', (), {'json': lambda s: d, 'status_code': 200})())(${complete_json})
    Set Global Variable   ${NETWORK_DEVICES_DATA}   ${wrapper}
    RETURN   ${wrapper}

Get Cached Network Devices Data
    # Check if network devices data is already cached, if not fetch it
    ${devices_exists}=   Run Keyword And Return Status   Variable Should Exist   ${NETWORK_DEVICES_DATA}
    Run Keyword If   not ${devices_exists}   Get All Network Devices
    RETURN   ${NETWORK_DEVICES_DATA}

Should Skip Site Validation
    [Documentation]   Check if a site should be skipped based on MANAGED_SITES env var
    ...               Returns True if site should be skipped, False if it should be validated
    [Arguments]   ${site_name}
    # Get MANAGED_SITES env var (empty = validate all sites)
    ${managed_sites}=   Get Environment Variable   MANAGED_SITES   default=${EMPTY}
    # If MANAGED_SITES is empty, don't skip (validate all)
    ${should_validate_all}=   Evaluate   '${managed_sites}' == ''
    Return From Keyword If   ${should_validate_all}   ${False}
    # Get MANAGE_SPECIFIC_SITES_ONLY flag (default = false, meaning include children)
    ${manage_specific_only}=   Get Environment Variable   MANAGE_SPECIFIC_SITES_ONLY   default=false
    # Check if site_name is in managed_sites (comma-separated list)
    # If manage_specific_only = true: only exact matches
    # If manage_specific_only = false: exact matches OR children of managed sites
    ${site_is_managed}=   Evaluate   '${site_name}' in '${managed_sites}'.split(',') or ('${manage_specific_only}' == 'false' and any('${site_name}'.startswith(site + '/') for site in '${managed_sites}'.split(',')))
    # Return True if should skip (site NOT managed), False if should validate (site IS managed)
    ${should_skip}=   Evaluate   not ${site_is_managed}
    RETURN   ${should_skip}