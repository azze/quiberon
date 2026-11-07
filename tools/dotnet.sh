#!/usr/bin/env bash
set -euo pipefail
RTT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DOTNET_CLI_HOME="$RTT_ROOT/.tools/dotnet-home"
export NUGET_PACKAGES="$RTT_ROOT/.tools/nuget"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_NOLOGO=1
export XDG_RUNTIME_DIR="$RTT_ROOT/.tools/runtime"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
if [[ -x "$RTT_ROOT/.tools/dotnet/dotnet" ]]; then
    export DOTNET_ROOT="$RTT_ROOT/.tools/dotnet"
    exec "$DOTNET_ROOT/dotnet" "$@"
fi
exec dotnet "$@"
