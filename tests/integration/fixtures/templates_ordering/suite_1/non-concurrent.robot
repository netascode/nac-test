*** Settings ***
Documentation   Suite not yet refactored

*** Test Cases ***
Sequential Test 1
    Set Suite Variable  $foo    bar

Sequential Test 2
    Variable Should Exist   $foo
