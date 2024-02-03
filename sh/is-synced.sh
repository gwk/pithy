cd $(dirname $0)/..
local_commit=$(git rev-parse HEAD)
remote_commit=$(git ls-remote -h origin main  | cut -f1)
[[ "$local_commit" == "$remote_commit" ]]
