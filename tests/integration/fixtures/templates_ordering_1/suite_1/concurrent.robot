*** Settings ***
Documentation   Test using Concurrency
Metadata        Test Concurrency     True

*** Test Cases ***
Concurrent Test 1
    Set Suite Variable  $foo    bar

Concurrent Test 2
    Run Keyword and Expect Error     Variable * does not exist.    Variable Should Exist   $foo
