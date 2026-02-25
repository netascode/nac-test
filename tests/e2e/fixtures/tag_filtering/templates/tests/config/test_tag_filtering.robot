*** Test Cases ***
Robot BGP Test
    [Tags]    bgp
    [Documentation]    Robot test with bgp tag for filtering tests
    Log    BGP test passes
    Should Be Equal    1    1

Robot OSPF Test
    [Tags]    ospf
    [Documentation]    Robot test with ospf tag for filtering tests
    Log    OSPF test passes
    Should Be Equal    1    1
