#!/bin/sh
# wait for a short period for dockerd to be ready
set +e
for x in 5 4 3 2 1
do
  docker info 2>&1 > /dev/null && exit 0
  sleep $x
done
echo "dockerd not ready"
exit 1
