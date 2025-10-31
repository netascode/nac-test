*** Settings ***
Documentation   Test with mixed case "TeSt CoNcUrReNcY"
Metadata        TeSt CoNcUrReNcY     True

*** Test Cases ***
Mixed Case Concurrent Test 1
    Set Suite Variable  $var2    value2

Mixed Case Concurrent Test 2
    Run Keyword and Expect Error     Variable * does not exist.    Variable Should Exist   $var2
