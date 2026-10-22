#!/bin/sh
# netconsole: kernel messages sent in real time over UDP to the server, which
# stores them in <log dir>/netconsole-<device name>/netconsole.log (rsyslog)
# and shows them in the "Netconsole" tab of the device in OpenWISP
# (openwisp-netconsole). Useful for hangs and kernel panics, when syslog has
# no time to send anything.
#
# netconsole binds to an interface and sends packets to a fixed MAC (the next
# hop towards the server): on every ifup the route is computed again and the
# module is reloaded only if the parameters changed.
[ "$ACTION" = "ifup" ] || exit 0

DST_IP='{{ netconsole_server }}'
DST_PORT='{{ netconsole_port }}'
STATE=/tmp/netconsole.params

# device name from OpenWISP (a hostname): only safe characters, otherwise no
# userdata
NODE='{{ name }}'
case "$NODE" in
	"" | *[!A-Za-z0-9._-]*) NODE="" ;;
esac

# Device name in every message: extended format ("+") with the ninux_node
# userdata, so the server keeps one folder per device whatever the source IP.
# Needs a kernel with CONFIG_NETCONSOLE_DYNAMIC=y; without it messages still
# arrive and the server falls back to the source IP.
netconsole_userdata() {
	cfg=/sys/kernel/config
	[ -d "$cfg/netconsole" ] || mount -t configfs configfs "$cfg" 2>/dev/null
	ud="$cfg/netconsole/cmdline0/userdata"
	[ -d "$ud" ] || return 0
	mkdir -p "$ud/ninux_node" && printf '%s' "$NODE" >"$ud/ninux_node/value"
}

# shellcheck disable=SC2046
set -- $(ip -4 route get "$DST_IP" 2>/dev/null | head -n 1)
dev="" via="" src=""
while [ $# -gt 0 ]; do
	case "$1" in
		dev) dev=$2 ;;
		via) via=$2 ;;
		src) src=$2 ;;
	esac
	shift
done
[ -n "$dev" ] && [ -n "$src" ] || exit 0

# MAC of the next hop: the gateway, or the server if it is on the same network
hop=${via:-$DST_IP}
ping -c 1 -W 2 -I "$dev" "$hop" >/dev/null 2>&1
mac="$(ip neigh show "$hop" dev "$dev" 2>/dev/null | awk '/lladdr/ { print $3; exit }')"
if [ -z "$mac" ]; then
	logger -t netconsole "no MAC for $hop on $dev: netconsole not enabled"
	exit 0
fi

params="6665@$src/$dev,$DST_PORT@$DST_IP/$mac"
# the ifindex changes when the device is recreated (e.g. VPN interfaces after
# boot): netconsole detaches and must be reloaded even with the same parameters
ifindex="$(cat "/sys/class/net/$dev/ifindex" 2>/dev/null)"
if [ "$(cat "$STATE" 2>/dev/null)" = "$params $ifindex $NODE" ] && grep -q '^netconsole ' /proc/modules; then
	exit 0
fi

rmmod netconsole 2>/dev/null
if insmod netconsole "netconsole=+$params"; then
	[ -z "$NODE" ] || netconsole_userdata
	echo "$params $ifindex $NODE" >"$STATE"
	logger -t netconsole "enabled: $src/$dev -> $DST_IP:$DST_PORT ($mac)"
else
	rm -f "$STATE"
	logger -t netconsole "ERROR: netconsole not enabled ($params)"
fi
exit 0
