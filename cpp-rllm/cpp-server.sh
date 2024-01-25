#!/bin/sh

set -e
REL=--release
LOOP=
BUILD=
ADD_ARGS=

mkdir -p ../target
BIN=$(cd ../target; pwd)

if [ -f "../llama-cpp-low/llama.cpp/CMakeLists.txt" ] ; then
  :
else
  (cd .. && git submodule update --init --recursive)
fi

P=`ps -ax|grep 'aicir[t]\|rllm-serve[r]' | awk '{print $1}' | xargs echo`

if [ "X$P" != "X" ] ; then 
  echo "KILL $P"
  kill $P
fi

VER="--no-default-features"

if [ "$1" = "--cuda" ] ; then
    VER="$VER --features cuda"
    shift
fi

if [ "$1" = "--debug" ] ; then
    REL=
    shift
fi

case "$1" in
  phi2 )
    ARGS="-m https://huggingface.co/TheBloke/phi-2-GGUF/blob/main/phi-2.Q8_0.gguf -t phi -w ../rllm/expected/phi-2/cats.safetensors -s test_maxtol=0.8 -s test_avgtol=0.3"
    ;;
  orca )
    ARGS="-m https://huggingface.co/TheBloke/Orca-2-13B-GGUF/blob/main/orca-2-13b.Q8_0.gguf -t orca -w ../rllm/expected/orca/cats.safetensors"
    ;;
  build )
    BUILD=1
    ;;
  * )
    echo "usage: $0 [--cuda] [--debug] [phi2|orca|build] [rllm_args...]"
    echo "Try $0 phi2 --help to see available rllm_args"
    exit 1
    ;;
esac
shift

ARGS="--verbose --port 8080 --aicirt $BIN/release/aicirt $ARGS $ADD_ARGS"

(cd ../aicirt; cargo build --release)

cargo build $REL $VER

if [ "$BUILD" = "1" ] ; then
    exit
fi

if [ "X$REL" = "X" ] ; then
    BIN_SERVER=$BIN/debug/cpp-rllm
else
    BIN_SERVER=$BIN/release/cpp-rllm
fi

export RUST_BACKTRACE=1
export RUST_LOG=info,rllm=debug,aicirt=info

echo "running $BIN_SERVER $ARGS $@"

$BIN_SERVER $ARGS "$@"
exit $?
