#!/bin/bash

PORT=5678
if [[ "$OSTYPE" == "darwin"* ]]; then
    BASE_DIR=$HOME/Documents/DD/nac-test
    # Activate virtualenv
    test "$VIRTUAL_ENV" || source $BASE_DIR/.venv/bin/activate
else
    BASE_DIR=/DD/nac-test
    test "$VIRTUAL_ENV" || source /tmp/venv/bin/activate
fi
MOCK_DIR=$BASE_DIR/tests/e2e/mocks
export MOCK_DIR     # referencecd in testbed.yaml
RESULT_DIR=./results


set -- $(env | egrep '^[A-Z]+_(URL|USERNAME|PASSWORD)=' | sed 's/=.*//')
for var in $* ; do 
    unset $var
done
export SDWAN_URL=http://127.0.0.1:$PORT
export SDWAN_USERNAME=mock_user
export SDWAN_PASSWORD=mock_pass
export IOSXE_USERNAME=mock_user
export IOSXE_PASSWORD=mock_pass

export PYATS_MAX_WORKERS=5

python $MOCK_DIR/mock_server_ctl.py start --port $PORT || { echo "Failed to start mock API server on port $PORT"; exit 1; }
# stop the server on exit or error
trap 'python $MOCK_DIR/mock_server_ctl.py stop' EXIT INT ERR

cd $BASE_DIR/workspace/scale


#export NAC_TEST_CONSOLIDATE_D2D=1
rm -rf $RESULT_DIR
export PYATS_DEBUG=1
unset PYATS_DEBUG
echo \$ nac-test -d data -t templates-single/tests --testbed testbed.yaml -o $RESULT_DIR  # --verbosity INFO
nac-test -d data -t templates-single/tests --testbed testbed.yaml -o $RESULT_DIR  # --verbosity INFO
