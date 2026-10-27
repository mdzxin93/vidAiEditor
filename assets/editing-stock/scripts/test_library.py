import json,pathlib,subprocess
p=pathlib.Path(__file__).resolve().parents[1];a=json.loads((p/'catalog/assets.json').read_text())['assets'];assert len(a)>=25;assert all((p/x['path']).exists() for x in a);assert len([x for x in a if x['kind']=='motion_background'])==8;print('PASS',len(a),'assets found')
