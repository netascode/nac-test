*** Settings ***
Documentation   Test with lowercase "test concurrency"
Metadata        test concurrency     True

*** Test Cases ***
Lowercase Concurrent Test 1
    Set Suite Variable  $var1    value1

Lowercase Concurrent Test 2
    Run Keyword and Expect Error     Variable * does not exist.    Variable Should Exist   $var1
