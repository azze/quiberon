#!/usr/bin/env bash
# Optional Linux x86_64 toolchain, confined to the repository's ignored .tools/.
set -euo pipefail
RTT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$RTT_ROOT/.tools/downloads"
if [[ ! -x "$RTT_ROOT/.tools/dotnet/dotnet" ]]; then
    curl -fL --retry 2 https://dot.net/v1/dotnet-install.sh -o "$RTT_ROOT/.tools/downloads/dotnet-install.sh"
    bash "$RTT_ROOT/.tools/downloads/dotnet-install.sh" --version 10.0.403 --install-dir "$RTT_ROOT/.tools/dotnet" --no-path
fi
RTT_GODOT="$RTT_ROOT/.tools/godot-mono/Godot_v4.7.2-stable_mono_linux_x86_64/Godot_v4.7.2-stable_mono_linux.x86_64"
if [[ ! -f "$RTT_GODOT" ]]; then
    curl -fL --retry 2 https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/Godot_v4.7.2-stable_mono_linux_x86_64.zip -o "$RTT_ROOT/.tools/downloads/godot-mono.zip"
    python3 - "$RTT_ROOT" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import sys
root=Path(sys.argv[1])
with ZipFile(root/'.tools/downloads/godot-mono.zip') as archive:
    archive.extractall(root/'.tools/godot-mono')
PY
fi
chmod +x "$RTT_GODOT"
echo 'Local Godot .NET and SDK ready. Build: bash tools/dotnet.sh build godot/Quiberon.csproj'
