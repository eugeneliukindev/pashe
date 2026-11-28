#!/bin/sh
# A Redis or Valkey cluster of one node per port in one container, the nodes announcing the address
# of the container: the tests reach every node there, as the bridge network of Docker is routed to
# the host on Linux. tests/harness/servers.py copies it into the container.
#
#   cluster.sh start redis 7000 7001 7002    start the nodes, join them, and stay up
#   cluster.sh ready redis 7000 7001 7002    succeed once every node serves every slot
set -eu

action=$1
program=$2
shift 2

node() {
    port=$1
    shift
    "$program-server" --port "$port" --cluster-enabled yes --cluster-config-file "/tmp/nodes-$port.conf" \
        --save "" --appendonly no --daemonize yes "$@"
}

case $action in
start)
    for port in "$@"; do
        # Redis 8.12 refuses a cluster bus with no TLS unless told it is reachable by trusted hosts only,
        # and an older Redis or Valkey refuses the option: it exits on it before it starts
        node "$port" --cluster-bus-port-protected-mode no 2> /dev/null || node "$port"
    done
    # every node answers before the cluster is made of them: a fixed sleep lost the race on a busy machine
    for port in "$@"; do
        until "$program-cli" -p "$port" ping > /dev/null 2>&1; do sleep 0.1; done
    done
    ip=$(hostname -i)
    nodes=""
    for port in "$@"; do nodes="$nodes $ip:$port"; done
    # shellcheck disable=SC2086 # one argument per node
    "$program-cli" --cluster create $nodes --cluster-replicas 0 --cluster-yes > /dev/null
    exec tail -f /dev/null
    ;;
ready)
    for port in "$@"; do
        "$program-cli" -p "$port" cluster info | grep -q cluster_state:ok
    done
    ;;
*)
    echo "cluster.sh: the action is start or ready, not $action" >&2
    exit 2
    ;;
esac
