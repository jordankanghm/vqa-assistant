#!/bin/sh

set -e

# Loop over URLs until "--" is reached
while [ "$1" != "--" ]; do
  echo "Waiting for $1..."

  until curl -sf "$1" > /dev/null; do
    sleep 2
  done

  echo "$1 is up!"
  shift
done

shift

echo "Running command: $@"
exec "$@"
