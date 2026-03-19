#!/bin/bash
set -- $(env | egrep '^[A-Z]+_(URL|USERNAME|PASSWORD)=' | sed 's/=.*//')
for var in $* ; do 
    unset $var
done
export SDWAN_URL=https://10.62.190.146
export SDWAN_USERNAME=admin
export SDWAN_PASSWORD=cisco123
export IOSXE_USERNAME=admin
export IOSXE_PASSWORD=cisco123
