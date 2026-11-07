#!/usr/bin/env bash
set -euo pipefail
RTT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DOTNET_CLI_HOME="$RTT_ROOT/.tools/dotnet-home"
export NUGET_PACKAGES="$RTT_ROOT/.tools/nuget"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
if [[ -x "$RTT_ROOT/.tools/dotnet/dotnet" ]]; then
    export DOTNET_ROOT="$RTT_ROOT/.tools/dotnet"
    export PATH="$DOTNET_ROOT:$PATH"
fi
RTT_GODOT="${GODOT_DOTNET:-$RTT_ROOT/.tools/godot-mono/Godot_v4.7.2-stable_mono_linux_x86_64/Godot_v4.7.2-stable_mono_linux.x86_64}"
if [[ ! -x "$RTT_GODOT" ]]; then
    echo 'Install Godot 4.7.2 .NET locally or set GODOT_DOTNET to its executable. See godot/README.md.' >&2
    exit 1
fi
exec "$RTT_GODOT" --path "$RTT_ROOT/godot" "$@"
