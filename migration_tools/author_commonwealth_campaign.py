"""Validate/export the canonical authored campaign; edit simulation_data/campaign/commonwealth.json."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);a=p.parse_args();d=json.loads((ROOT/'simulation_data/campaign/commonwealth.json').read_text())
 assert len(d['encounters'])==7 and {e['stage'] for e in d['encounters']}==set(range(1,7))
 text=json.dumps(d,ensure_ascii=False,indent=2)+'\n'
 if a.output:a.output.write_text(text)
 else:print('Seven authored encounters, six stages, two stage-four alternatives; seed variation is native.')
if __name__=='__main__':main()
