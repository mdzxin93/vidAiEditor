#!/usr/bin/env python3
"""Reference-style editing planner. Stdlib BM25 + optional local sentence-transformers.
Accepts timed transcript segments (seconds) or an untimed plain-text script.
It does NOT train model weights or render video. All asset paths are relative to library root.
"""
from __future__ import annotations
import argparse,json,math,re,statistics
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
STOP=set('a an and are as at be been but by can do for from had has have he her his i in is it its my not of on or our she so that the their them there these they this to was we were what when where who will with you your'.split())
SYN={
 'time':['clock','hours','calendar','productivity','schedule','deadline','day'],
 'money':['revenue','profit','earnings','income','cash','sales','finance','price'],
 'business':['company','entrepreneur','customers','sales','startup','clients'],
 'growth':['increase','progress','scaling','growth','rise','improvement'],
 'problem':['struggle','challenge','failure','difficulty','issue','pain'],
 'technology':['ai','automation','software','digital','cloud','robot','machine'],
 'social':['social','media','instagram','content','creator','marketing'],
 'work':['job','working','labor','effort','hustle','hours','office'],
 'result':['results','outcome','success','impact','performance','metrics'],
 'team':['team','people','collaboration','meeting','staff'],
 'communication':['call','phone','chat','message','email','talk'],
 'comparison':['compare','versus','difference','before','after','alternative'],
 'security':['privacy','secure','password','protection','lock'],
}
REV={w:k for k,words in SYN.items() for w in words}
def toks(s):
 return [w for w in re.findall(r"[a-z0-9]+",s.lower()) if len(w)>1 and w not in STOP]
def enrich(words):
 out=list(words)
 for w in words:
  c=REV.get(w)
  if c:out.append(c)
  if w in SYN:out.extend(SYN[w][:4])
 return out
def index_asset(a):
 return enrich(toks(' '.join([a['id'].replace('_',' '),' '.join(a.get('tags',[])),' '.join(a.get('script_signals',[])),a.get('kind','')])) )
ASSETS=json.loads((ROOT/'catalog/assets.json').read_text())['assets']
DOCS=[index_asset(a) for a in ASSETS]
DF=Counter(w for d in DOCS for w in set(d))
AVG=sum(map(len,DOCS))/max(1,len(DOCS))
def bm25(q,d):
 freq=Counter(d);N=len(DOCS);score=0.0
 for w in set(q):
  if w not in freq:continue
  idf=math.log(1+(N-DF[w]+0.5)/(DF[w]+0.5))
  f=freq[w];score+=idf*f*2.2/(f+1.2*(0.25+0.75*len(d)/max(1,AVG)))
 return score
class Scorer:
 def __init__(self,semantic=False):
  self.semantic=None
  if semantic:
   try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    model=SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2',device='cpu')
    desc=[' '.join([a['id'].replace('_',' '),' '.join(a.get('tags',[]))]) for a in ASSETS]
    self.semantic=(model,model.encode(desc,normalize_embeddings=True,show_progress_bar=False))
   except Exception as e:
    print(f'Warning: optional embedding model unavailable ({e}); continuing with offline BM25',file=__import__('sys').stderr)
 def score(self,text):
  q=enrich(toks(text)); lex=[bm25(q,d) for d in DOCS]
  mx=max(lex,default=0) or 1
  lex=[v/mx for v in lex]
  if self.semantic:
   model,emb=self.semantic
   import numpy as np
   vector=model.encode([text],normalize_embeddings=True)[0]
   sem=[max(0,float(x)) for x in emb@vector]
   return [round(.6*l+.4*s,4) for l,s in zip(lex,sem)]
  return [round(x,4) for x in lex]
def transcript_to_segments(source):
 if isinstance(source,str):
  sentences=[s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+',source) if s.strip()]
  t=0.0;out=[]
  for s in sentences:
   dur=max(1.0,len(re.findall(r"\b[\w']+\b",s))/2.4)
   out.append(dict(start=round(t,3),end=round(t+dur,3),text=s,estimated=True));t+=dur
  return out
 if isinstance(source,dict):
  if 'segments' in source:source=source['segments']
  elif 'words' in source:source=source['words']
  else:raise ValueError('Expected segments or words')
 if not isinstance(source,list):raise ValueError('Expected list of timed segments')
 out=[]
 for item in source:
  if 'start' not in item or 'end' not in item:raise ValueError('Every segment needs start and end (seconds)')
  start,end=float(item['start']),float(item['end'])
  if not (0<=start<end):raise ValueError('Invalid timestamp')
  out.append(dict(start=start,end=end,text=item.get('text') or item.get('word',''),estimated=False))
 out.sort(key=lambda v:v['start'])
 return out
def merge_short_segments(segs,minimum=1.1):
 if not segs:return []
 result=[];curr=dict(segs[0])
 for s in segs[1:]:
  if (curr['end']-curr['start']<minimum and s['start']-curr['end']<0.5 and s['end']-curr['start']<4.5):
   curr['end']=s['end'];curr['text']=(curr['text']+' '+s['text']).strip()
  else:result.append(curr);curr=dict(s)
 result.append(curr);return result
def choose(seg,scorer,used,last_end,threshold=.19):
 candidates=scorer.score(seg['text']);ranked=[]
 for i,asset in enumerate(ASSETS):
  if asset['kind'] not in ('illustration','video','motion','overlay') and not asset['path'].endswith(('.mp4','.svg','.png')):continue
  raw=candidates[i]
  if raw<threshold:continue
  penalty=.65 if asset['id'] in used[-3:] else 0
  if last_end.get(asset['id'],-100)+12>seg['start']:penalty+=.65
  if asset['kind']!='illustration':penalty+=.06
  ranked.append((raw-penalty,raw,asset))
 ranked.sort(key=lambda r:r[0],reverse=True)
 if not ranked or ranked[0][0]<threshold:return None
 return ranked[0][1],ranked[0][2],ranked[:3]
def plan(source,semantic=False,max_broll_duration=2.7,threshold=.19):
 segments=merge_short_segments(transcript_to_segments(source));scorer=Scorer(semantic)
 events=[];used=[];last_end={};count=0
 for seg in segments:
  start,end=seg['start'],seg['end'];duration=end-start
  choice=choose(seg,scorer,used,last_end,threshold)
  if choice and duration>=1.25:
   score,asset,alts=choice
   bdur=min(max_broll_duration, duration*.65)
   bstart=start+(duration-bdur)*.50;bend=bstart+bdur
   if bstart-start>=.12:events.append({'type':'a_roll','start_s':round(start,3),'end_s':round(bstart,3),'script_text':seg['text']})
   events.append({'type':'b_roll_overlay','start_s':round(bstart,3),'end_s':round(bend,3), 'asset_id':asset['id'],'asset_path':asset['path'],'asset_kind':asset['kind'],'confidence':round(score,3),'script_text':seg['text'],'transition':'hard_cut','motion':'subtle_scale_pop' if asset['kind']=='illustration' else 'original_asset_motion','sfx':'soft_swoosh','alternatives':[{'id':a['id'],'score':round(s,3)} for _,s,a in alts[:3]],'requires_review':score<.44})
   if end-bend>=.12:events.append({'type':'a_roll','start_s':round(bend,3),'end_s':round(end,3),'script_text':seg['text']})
   last_end[asset['id']]=bend;used.append(asset['id']);count+=1
  else:events.append({'type':'a_roll','start_s':round(start,3),'end_s':round(end,3),'script_text':seg['text']})
 return {'schema':'openmontage.edl.v3','style_preset':'presets/cinematic_explainer.json','time_unit':'seconds','source_timing':('estimated_script' if any(s['estimated'] for s in segments) else 'asr_timed'),'status':'draft_review_before_render','duration_s':round(max((s['end'] for s in segments),default=0),3),'asset_root':'assets/editing-stock','settings':{'max_broll_duration_s':max_broll_duration,'hard_cuts_default':True,'repeat_cooldown_s':12,'audio':'preserve_original_dialogue','external_stock_licensed_only':True},'stats':{'segments':len(segments),'broll_events':count,'reviews_needed':sum(e.get('requires_review',False) for e in events)},'events':events}
def validate_edl(edl,root=ROOT):
 errors=[];items=edl['events']
 for j,e in enumerate(items):
  if not 0<=e['start_s']<e['end_s']<=edl['duration_s']+.002:errors.append(f'bad timing event {j}')
  if e['type']=='b_roll_overlay' and not (root/e['asset_path']).is_file():errors.append(f'missing file {e["asset_path"]}')
 for x,y in zip(items,items[1:]):
  if y['start_s']<x['start_s']:errors.append('unsorted events')
 return errors
if __name__=='__main__':
 p=argparse.ArgumentParser(description='OpenMontage script-aware B-roll planner')
 p.add_argument('input',help='Plain text script or transcript JSON with timed segments')
 p.add_argument('--output',default='edit_plan_v3.json');p.add_argument('--semantic',action='store_true',help='Optional local CPU sentence-transformer semantic scoring');p.add_argument('--threshold',type=float,default=.19)
 args=p.parse_args();fp=Path(args.input)
 source=json.loads(fp.read_text(encoding='utf-8')) if fp.suffix.lower()=='.json' else fp.read_text(encoding='utf-8')
 edl=plan(source,semantic=args.semantic,threshold=args.threshold)
 errors=validate_edl(edl)
 if errors:raise RuntimeError('; '.join(errors))
 Path(args.output).write_text(json.dumps(edl,indent=2),encoding='utf-8')
 print(json.dumps({'output':args.output,**edl['stats'],'timing':edl['source_timing']}))
