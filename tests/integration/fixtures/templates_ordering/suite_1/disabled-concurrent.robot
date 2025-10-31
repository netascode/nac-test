*** Settings ***
Documentation   Test with Test Concurrency explicitly disabled
Metadata        Test Concurrency     False

*** Test Cases ***
Disabled Concurrent Test 1
    Set Suite Variable  $var3    value3

Disabled Concurrent Test 2
    Variable Should Exist   $var3
