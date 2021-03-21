#!/bin/sh
#
# SysV init script for gitlab-python-runner
#

set -e

RUNNER_ETC=/etc/gitlab-python-runner
STARTUP_CONF=${RUNNER_ETC}/service.conf
RUNNER_CONF=${RUNNER_ETC}/gitlab-runner.yml
PIDFILE=${RUNNER_ETC}/service.pid

LOGFILE=${LOGFILE:-/var/log/gitlab-python-runner.log}

if [ -f ${STARTUP_CONF} ]
then
  . ${STARTUP_CONF}
else
  exit 0
fi

case "$1" in
  start)
    echo "Starting gitlab python runner as ${RUNNER_USER:-gitlab-python-runner} with ${RUNNER_CONF}"
    nohup su - ${RUNNER_USER} -c "gitlab-runner.py --start ${RUNNER_CONF}" >>${LOGFILE} 2>>${LOGFILE}&
    echo $! > $PIDFILE
    sleep 1
    ;;

  stop)
    echo "Stopping gitlab python runner"

    if [ -f ${PIDFILE} ]
    then
      kill $(cat ${PIDFILE})
      sleep 2
    fi
    rm ${PIDFILE}
    ;;

  restart)
    ;;
esac