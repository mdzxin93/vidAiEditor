#!/usr/bin/env python3
"""Heuristic EDL (edit decision list) planner, not a trained ML model."""
import json,re,sys,pathlib
BASE=pathlib.Path(__file__).resolve().parents[1]
assets=json.loads((BASE/'catalog/assets.json').read_text())['assets']
def plan(script,words_per_second=2.4):
 sentences=[s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+',script) if s.strip()]
 t=0;edl=[]
 for i,s in enumerate(sentences):
  toks=re.findall(r"[\w']+",s.lower()); duration=max(.7,len(toks)/words_per_second)
  matches=[]
  for a in assets:
   if a['kind']!='illustration':continue
   overlap=len(set(toks)&set(a['tags']))
   if overlap:matches.append((overlap,a['id'],a['path']))
  matches.sort(reverse=True)
  if matches:
   asset=matches[0];bstart=t+duration*.34;bend=min(t+duration,t+duration*.34+min(2.3,duration*.5))
   edl.append({'kind':'a_roll','start_s':round(t,3),'end_s':round(bstart,3),'script':s})
   edl.append({'kind':'graphic_broll','start_s':round(bstart,3),'end_s':round(bend,3),'asset':asset[2],'reason':'keyword relevance, review manually','suggested_effect':'scale_pop'})
   if bend<t+duration:edl.append({'kind':'a_roll','start_s':round(bend,3),'end_s':round(t+duration,3),'script':s})
  else:edl.append({'kind':'a_roll','start_s':round(t,3),'end_s':round(t+duration,3),'script':s})
  t+=duration
 return {'note':'Illustrative timing only. Align with real ASR word timestamps before rendering.','estimated_duration_s':round(t,3),'edl':edl}
if __name__=='__main__':
 script=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8') if len(sys.argv)>1 else 'I work twelve hours every day. My business needs growth and better strategy. Automate the content workflow.'
 print(json.dumps(plan(script),indent=2))
