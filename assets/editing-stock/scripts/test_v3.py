import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from semantic_edit_planner import plan,validate_edl,transcript_to_segments
class Test(unittest.TestCase):
 def test_script(self):
  r=plan('We waste hours of time at work. Our business revenue must grow. AI automation improves productivity.')
  self.assertGreaterEqual(r['stats']['broll_events'],2);self.assertFalse(validate_edl(r))
 def test_timestamped(self):
  inp=json.loads((Path(__file__).parent/'example_transcript.json').read_text());r=plan(inp)
  self.assertEqual(r['source_timing'],'asr_timed');self.assertFalse(validate_edl(r));self.assertEqual(r['duration_s'],12.4)
 def test_reject_bad_time(self):
  with self.assertRaises(ValueError):transcript_to_segments([{'start':5,'end':2,'text':'oops'}])
 def test_missing_asset(self):
  x=plan('I waste hours of time in meetings.');
  for e in x['events']:
   if e['type']=='b_roll_overlay':e['asset_path']='missing_file.svg';break
  self.assertTrue(validate_edl(x))
if __name__=='__main__':unittest.main()
