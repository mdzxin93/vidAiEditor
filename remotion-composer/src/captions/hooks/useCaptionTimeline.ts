import { useMemo } from 'react';
import { KineticCue } from '../types/caption.types';
import { getActiveCues } from '../utils/captionTiming';

export function useCaptionTimeline(cues: KineticCue[], currentSeconds: number) {
  const activeCues = useMemo(() => {
    return getActiveCues(cues, currentSeconds);
  }, [cues, currentSeconds]);

  const activeCue = activeCues[0] || null;

  const totalDuration = useMemo(() => {
    if (!cues || cues.length === 0) return 0;
    return Math.max(...cues.map((c) => c.end));
  }, [cues]);

  return {
    activeCues,
    activeCue,
    totalDuration,
    cueCount: cues.length,
  };
}
