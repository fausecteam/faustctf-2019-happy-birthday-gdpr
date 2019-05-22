#!/bin/bash

set -euo pipefail

export GDPR_HOST=${GDPR_HOST:-localhost}
export GDPR_PORT=${GDPR_PORT:-4377}

exec 42>&1

first=$(date +%s)
data=$(mktemp -d)
BASEDIR=$(dirname "$(readlink -f "$0/..")")
export PYTHONPATH="$CTF_GAMESERVER_CHECKOUT/src:$BASEDIR/checker"
for i in {0..100}; do
	echo ">> Tick $i"
	"$CTF_GAMESERVER_CHECKOUT"/scripts/checker/ctf-testrunner \
		--first "$first" \
		--backend "$data" \
		--tick $i \
		--ip "$GDPR_HOST" \
		--team 1 \
		--service 1 \
		happybirthdaygdpr:HappyBirthdayGdprChecker
done |& tee checker.log

cat checker.log \
	| grep -E '^DEBUG:service[0-9]+-team[0-9]+-tick[0-9]+:checker result:' \
	| grep -v ': OK' && { echo found non-OK checker result >&2; exit 1; } || test $? = 1

cat checker.log \
	| grep -E '^ERRPR:service[0-9]+-team[0-9]+-tick[0-9]+:' && { echo found errors in checker result >&2; exit 1; } || test $? = 1

for exploit in exploits/unicode-user-impersonation.py; do
	echo ">>> Testing exploit $(basename "$exploit")"
	for tick in {000..100}; do
		flag_id=$(cat "$data/flagid_$tick.blob")
		echo ">>> Testing tick $tick (flagid $flag_id)"
		"$exploit" "http://$GDPR_HOST:$GDPR_PORT" "$flag_id" | tee /proc/self/fd/42 | grep -qE 'FAUST_[A-Za-z0-9/\+]{32}'
	done
done

exec 42>&-
rm -r "$data"
