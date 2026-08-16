set -e

function fail() { echo "$1" >&2; exit 1; }

hostname="$1"

[[ -z "$hostname" ]] && fail "Usage: $0 <hostname>"

sudo scutil --set HostName "$hostname"
sudo scutil --set LocalHostName "$hostname"
sudo scutil --set ComputerName "$hostname"

dscacheutil -flushcache

echo "Hostname set to $hostname. Please restart your computer to apply the changes."
