#!/bin/sh

set -x
cd `dirname $0`
HERE=`pwd`
cd $HERE/../jsctrl
tsc -p samples
PYTHONPATH=$HERE/../py \
python3 ../pyctrl/driver.py samples/dist/test.js

