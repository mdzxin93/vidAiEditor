import { KineticCue } from '../types/caption.types';

export function getActiveCues(cues: KineticCue[], currentSeconds: number): KineticCue[] {
  if (!Array.isArray(cues) || cues.length === 0) return [];
  return cues.filter((cue) => currentSeconds >= cue.start && currentSeconds < cue.end);
}

export function isWordActive(
  wordStart: number,
  wordEnd: number,
  nextWordStart: number | undefined,
  currentSeconds: number
): boolean {
  // Bridge micro-gaps under 250ms between words in continuous speech
  const activeEnd = nextWordStart ? Math.min(nextWordStart, wordEnd + 0.15) : wordEnd;
  return currentSeconds >= wordStart && currentSeconds < activeEnd;
}
