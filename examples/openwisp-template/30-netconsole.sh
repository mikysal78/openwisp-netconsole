#!/bin/sh
# netconsole: kernel messages sent in real time over UDP to the server, which
# stores them in <log dir>/netconsole-<device name>/netconsole.log (rsyslog)
# and shows them in the "Netconsole" tab of the device in OpenWISP
# (openwisp-netconsole). Useful for hangs and kernel panics, when syslog has
# no time to send anything.
#
# netconsole binds to an interface and sends packets to a fixed MAC (the next
# hop towards the server): on every ifup the route is computed again and
# netconsole is reconfigured only if the parameters changed.
[ "$ACTION" = "ifup" ] || exit 0

DST_IP='{{ netconsole_server }}'
DST_PORT='{{ netconsole_port }}'
STATE=/tmp/netconsole.params
SELF=/etc/hotplug.d/iface/30-netconsole

# device name from OpenWISP (a hostname): only safe characters, otherwise no
# userdata
NODE='{{ name }}'
case "$NODE" in
	"" | *[!A-Za-z0-9._-]*) NODE="" ;;
esac

# netconsole_set <dev> <source ip> <mac>: points netconsole at the given
# route, in extended format with the ninux_node userdata (the device name), so
# the server keeps one folder per device whatever the source IP.
# With CONFIG_NETCONSOLE_DYNAMIC=y the "ninux" target is reconfigured from
# configfs without reloading the module (parameters can only be changed while
# the target is disabled). Without it the parameters are given to insmod and
# the server falls back to the source IP.
netconsole_set() {
	cfg=/sys/kernel/config
	[ -d "$cfg/netconsole" ] || mount -t configfs configfs "$cfg" 2>/dev/null
	grep -q '^netconsole ' /proc/modules || insmod netconsole 2>/dev/null
	if [ ! -d "$cfg/netconsole" ]; then
		rmmod netconsole 2>/dev/null
		insmod netconsole "netconsole=+6665@$2/$1,$DST_PORT@$DST_IP/$3"
		return
	fi
	nt="$cfg/netconsole/ninux"
	if [ ! -d "$nt" ]; then
		# module loaded with parameters by an older version of this script
		# (cmdline0 target): start again from a module without targets; the
		# cmdline0 folder keeps the module busy and must go before rmmod
		if [ -d "$cfg/netconsole/cmdline0" ]; then
			rmdir "$cfg/netconsole/cmdline0/userdata/ninux_node" "$cfg/netconsole/cmdline0" 2>/dev/null
			rmmod netconsole && insmod netconsole || return 1
		fi
		mkdir "$nt" || return 1
	fi
	[ "$(cat "$nt/enabled")" = 0 ] || echo 0 >"$nt/enabled" || return 1
	printf '%s' "$1" >"$nt/dev_name" &&
		printf '%s' "$2" >"$nt/local_ip" &&
		printf '%s' "$DST_IP" >"$nt/remote_ip" &&
		printf '%s' "$3" >"$nt/remote_mac" &&
		echo 6665 >"$nt/local_port" &&
		echo "$DST_PORT" >"$nt/remote_port" &&
		echo 1 >"$nt/extended" || return 1
	if [ -n "$NODE" ]; then
		mkdir -p "$nt/userdata/ninux_node" &&
			printf '%s' "$NODE" >"$nt/userdata/ninux_node/value"
	fi
	echo 1 >"$nt/enabled"
}

# on: with configfs the ninux target enabled (a module loaded with parameters
# by an older version does not count), without it the module loaded
netconsole_on() {
	if [ -d /sys/kernel/config/netconsole ]; then
		[ "$(cat /sys/kernel/config/netconsole/ninux/enabled 2>/dev/null)" = 1 ]
	else
		grep -q '^netconsole ' /proc/modules
	fi
}

# some bootloaders (e.g. Zyxel) pass loglevel=1 to the kernel: the consoles,
# netconsole included, would get only emergency messages. Use the usual
# OpenWrt values
[ "$(cut -f1 /proc/sys/kernel/printk)" -ge 7 ] || echo "7 4 1 7" >/proc/sys/kernel/printk

# check_later <seconds>: runs this script again by itself, even without an
# ifup: at boot the server may not be reachable yet, and VPN interfaces
# recreated after boot (e.g. ZeroTier) disable the target without a new ifup.
# With netconsole on, the check exits at once; one pending check at a time
check_later() {
	mkdir /tmp/netconsole.check 2>/dev/null || return 0
	(
		sleep "$1"
		rmdir /tmp/netconsole.check
		ACTION=ifup INTERFACE=check sh "$SELF"
	) </dev/null >/dev/null 2>&1 &
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
if [ -z "$dev" ] || [ -z "$src" ]; then
	check_later 60
	exit 0
fi

# MAC of the next hop: the gateway, or the server if it is on the same network
hop=${via:-$DST_IP}
ping -c 1 -W 2 -I "$dev" "$hop" >/dev/null 2>&1
mac="$(ip neigh show "$hop" dev "$dev" 2>/dev/null | awk '/lladdr/ { print $3; exit }')"
if [ -z "$mac" ]; then
	logger -t netconsole "no MAC for $hop on $dev: netconsole not enabled, retrying in a minute"
	check_later 60
	exit 0
fi

params="6665@$src/$dev,$DST_PORT@$DST_IP/$mac"
# when the device is recreated (e.g. VPN interfaces after boot) netconsole
# disables the target and it must be enabled again even with the same
# parameters: with configfs "enabled" says so, without it the ifindex changes
ifindex="$(cat "/sys/class/net/$dev/ifindex" 2>/dev/null)"
if [ "$(cat "$STATE" 2>/dev/null)" = "$params $ifindex $NODE" ] && netconsole_on; then
	check_later 300
	exit 0
fi

if netconsole_set "$dev" "$src" "$mac"; then
	echo "$params $ifindex $NODE" >"$STATE"
	logger -t netconsole "enabled: $src/$dev -> $DST_IP:$DST_PORT ($mac)"
	check_later 300
else
	rm -f "$STATE"
	logger -t netconsole "ERROR: netconsole not enabled ($params), retrying in a minute"
	check_later 60
fi
exit 0
