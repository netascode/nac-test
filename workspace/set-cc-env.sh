#!/bin/bash
set -- $(env | egrep '^[A-Z]+_(URL|USERNAME|PASSWORD)=' | sed 's/=.*//')
for var in $* ; do 
    unset $var
done
#export CC_URL=https://10.62.190.84
#export CC_USERNAME=admin
#export CC_PASSWORD=C1sco12345
#export IOSXE_USERNAME=sdaadmin
#export IOSXE_PASSWORD=L1ons@svs

# Arystan's dcloud
export CC_MAX_TIMEOUT=600
export CC_URL=https://198.18.129.100
export CC_USERNAME=admin
export CC_PASSWORD=C1sco12345
export IOSXE_USERNAME=dnacadmin
export IOSXE_PASSWORD=C1sco12345
