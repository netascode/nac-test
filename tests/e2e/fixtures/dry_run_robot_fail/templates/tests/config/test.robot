*** Settings ***
Documentation    Robot test that fails during dry-run due to non-existent keyword — Ü ö 日本語

*** Test Cases ***
Failing Dryrun Test
    This keyword better not exist as native robot keyword
