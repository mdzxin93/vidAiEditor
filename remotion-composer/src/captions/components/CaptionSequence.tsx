import React from 'react';
import { AbsoluteFill } from 'remotion';
import { CaptionStylePreset, KineticCue } from '../types/caption.types';
import { KineticCaption } from './KineticCaption';
import { EmphasisCaption } from './EmphasisCaption';
import { EditorialCaption } from './EditorialCaption';

export interface CaptionSequenceProps {
  cues: KineticCue[];
  preset: CaptionStylePreset;
}

export const CaptionSequence: React.FC<CaptionSequenceProps> = ({ cues, preset }) => {
  if (!Array.isArray(cues) || cues.length === 0) {
    return null;
  }

  return (
    <AbsoluteFill style={{ pointerEvents: 'none', overflow: 'hidden' }}>
      {cues.map((cue, i) => {
        const key = cue.id || `cue-${i}-${cue.start}`;
        if (cue.mode === 'editorial' || cue.topText || cue.stickers) {
          return <EditorialCaption key={key} cue={cue} preset={preset} />;
        }
        if (cue.mode === 'emphasis' || cue.mode === 'stack') {
          return <EmphasisCaption key={key} cue={cue} preset={preset} />;
        }
        return <KineticCaption key={key} cue={cue} preset={preset} />;
      })}
    </AbsoluteFill>
  );
};
