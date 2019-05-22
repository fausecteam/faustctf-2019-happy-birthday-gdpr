#!/usr/bin/env python3

import os.path
import subprocess
import sys

BASEDIR = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.join(BASEDIR, 'checker'))

from happybirthdaygdpr import generated


def fmt(r):
    return '{} ({})'.format(repr(r), hex(ord(r)))


runes = set()
for attr in dir(generated):
    if attr.startswith('__'):
        continue
    v = getattr(generated, attr)
    if not isinstance(v, str):
        continue
    runes |= set(v)
for r in list(runes):
    runes.add(r.lower())
    runes.add(r.upper())

runes = ''.join(sorted(runes))
for rune in runes:
    if len(rune) != len(rune.upper()) or len(rune) != len(rune.lower()):
        print('weird rune changing len in python:', fmt(rune), file=sys.stderr)
        sys.exit(1)
runes_upper = runes.upper()
runes_lower = runes.lower()
assert len(runes) == len(runes_upper)
assert len(runes) == len(runes_lower)

GODIR = os.path.join(BASEDIR, 'misc', 'convert-case')
GOCMD = ['go', 'run', os.path.join(GODIR, 'main.go'), os.path.join(GODIR, 'utils.go')]

resupper = subprocess.check_output(
    GOCMD + ['upper'],
    input=runes.encode('utf-8')).decode('utf-8')
reslower = subprocess.check_output(
    GOCMD + ['lower'],
    input=runes.encode('utf-8')).decode('utf-8')

for inp, lopy, uppy, logo, upgo in zip(runes, runes_lower, runes_upper, reslower, resupper):
    if uppy != upgo:
        print('{}: Python: {}, Go: {}'.format(fmt(inp), fmt(uppy), fmt(upgo)))
        sys.exit(1)
    if lopy != logo:
        print('{}: Python: {}, Go: {}'.format(fmt(inp), fmt(lopy), fmt(logo)))
        sys.exit(1)
assert len(runes_upper) == len(resupper)

print(len(runes), 'runes checked successfully', file=sys.stderr)
