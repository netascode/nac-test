#!/bin/bash
set -- $(env | egrep '^[A-Z]+_(URL|USERNAME|PASSWORD)=' | sed 's/=.*//')
for var in $* ; do 
    unset $var
done
