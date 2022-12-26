#!/bin/bash

# Start batfish-agent
python3 -m alto.agent.manage --pid /tmp start -c /etc/batfish-agent.json -D batfish &
  
# Start batfish-server
./wrapper.sh &
  
# Wait for any process to exit
wait -n
  
# Exit with status of process that exited first
exit $?
