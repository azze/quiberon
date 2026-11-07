"""Optional native Godot camera/render-contract tests; no desktop required."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest

@pytest.mark.parametrize('script',['test_camera_3d.gd','test_viewer_3d.gd'])
def test_3d_contract(script,tmp_path):
    engine=shutil.which('godot') or shutil.which('godot4')
    if engine is None:pytest.skip('Godot 4 is not installed')
    root=Path(__file__).resolve().parents[1]
    env={**os.environ,'XDG_DATA_HOME':str(tmp_path/'data'),'XDG_CONFIG_HOME':str(tmp_path/'config'),'XDG_CACHE_HOME':str(tmp_path/'cache')}
    result=subprocess.run([engine,'--headless','--path',str(root/'godot'),'--script','tests/'+script],env=env,text=True,capture_output=True,timeout=45)
    output=result.stdout+result.stderr
    assert result.returncode==0 and 'failed: false' in output and 'SCRIPT ERROR' not in output,output
