from pathlib import Path
import json,subprocess,sys
root=Path(__file__).resolve().parents[1]
cat=json.loads((root/'catalog/assets.json').read_text())
missing=[];bad=[]
for item in cat['assets']:
 p=root/item['path']
 if not p.is_file():missing.append(str(p));continue
 if p.suffix in ('.mp4','.wav'):
  proc=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nokey=1:noprint_wrappers=1',str(p)],capture_output=True,text=True)
  if proc.returncode!=0 or not proc.stdout.strip():bad.append(item['id'])
print('Indexed:',len(cat['assets']),'Missing:',len(missing),'Invalid media:',len(bad))
if missing:print('\n'.join(missing[:20]))
if bad:print('Invalid:',bad)
sys.exit(bool(missing or bad))
