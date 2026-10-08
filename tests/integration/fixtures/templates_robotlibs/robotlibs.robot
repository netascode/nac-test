*** Variables ***
${SAMPLE_JSON}    {"device": "switch1", "interfaces": [{"name": "Eth1/1", "vlan": 10}, {"name": "Eth1/2", "vlan": 20}]}

*** Test Cases ***
Load Robot Libs
    [Template]    Import Library
    JMESPathLibrary
    JSONLibrary
    pabot.PabotLib
    RequestsLibrary

Verify JSONPath Query Execution
    ${json_obj}=    Convert String to JSON    ${SAMPLE_JSON}
    ${vlans}=    Get Value From Json    ${json_obj}    $.interfaces[*].vlan
    Should Be Equal As Strings    ${vlans}[0]    10
    Should Be Equal As Strings    ${vlans}[1]    20

Verify JMESPath Query Execution
    ${json_obj}=    Convert String to JSON    ${SAMPLE_JSON}
    ${vlan}=    Json Search    ${json_obj}    interfaces[?name=='Eth1/1'].vlan | [0]
    Should Be Equal As Numbers    ${vlan}    10
