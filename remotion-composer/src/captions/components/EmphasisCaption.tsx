import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { CaptionStylePreset, KineticCue } from '../types/caption.types';
import { computeCueLayout } from '../utils/captionLayout';
import { computeCueAnimation } from '../utils/captionAnimations';

export interface EmphasisCaptionProps {
  cue: KineticCue;
  preset: CaptionStylePreset;
}

export const EmphasisCaption: React.FC<EmphasisCaptionProps> = ({ cue, preset }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const firstFrame = Math.round(cue.start * fps);
  const lastFrame = Math.round(cue.end * fps);

  if (frame < firstFrame || frame >= lastFrame) {
    return null;
  }

  const { x, y, fontSize, maxWidth } = computeCueLayout(cue, preset, width, height);
  const { scale, opacity } = computeCueAnimation(frame, firstFrame, lastFrame, preset);

  const fontFamily = cue.fontFamily || `"${preset.font_family}", Inter, -apple-system, sans-serif`;
  const fontWeight = cue.fontWeight || preset.emphasis_font_weight || 900;
  const fontColor = cue.color || preset.font_color || '#FFFFFF';
  const letterSpacing = preset.letter_spacing_em !== undefined ? `${preset.letter_spacing_em}em` : '-0.06em';
  const textShadow = preset.shadow_enabled ? preset.shadow_style || '0 3px 8px rgba(0,0,0,0.3)' : 'none';

  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${scale})`,
        opacity,
        width: 'max-content',
        maxWidth,
        fontFamily,
        fontWeight,
        letterSpacing,
        color: fontColor,
        fontSize,
        lineHeight: 0.95,
        textAlign: 'center',
        textTransform: 'uppercase',
        textShadow,
        pointerEvents: 'none',
        userSelect: 'none',
        WebkitTextStroke: preset.outline_enabled
          ? `${preset.outline_width_px || 4}px ${preset.outline_color || 'black'}`
          : 'none',
        paintOrder: 'stroke fill',
      }}
    >
      {/* Supporting helper word above/below the dominant emphasis word */}
      {cue.support && (
        <div
          style={{
            fontSize: `${(cue.support.scale || 0.48) * 100}%`,
            fontWeight: 700,
            letterSpacing: '-0.02em',
            opacity: 0.92,
            textTransform: 'none',
            lineHeight: 1.1,
            marginBottom: cue.support.position?.startsWith('bottom') ? 0 : 6,
            marginTop: cue.support.position?.startsWith('bottom') ? 6 : 0,
            color: '#FFFFFF',
          }}
        >
          {cue.support.text}
        </div>
      )}

      {/* Dominant oversized emphasis word or Two-tier glowing badge */}
      {cue.scriptText ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <span
            style={{
              color: cue.color || '#ff1f38',
              fontSize: '76px',
              fontWeight: 900,
              textShadow: '0 0 32px rgba(255, 31, 56, 0.95), 0 4px 18px rgba(0, 0, 0, 0.95)',
              letterSpacing: '-0.02em',
              lineHeight: 1.0,
            }}
          >
            {cue.text}
          </span>
          <span
            style={{
              fontFamily: '"Caveat", "Dancing Script", "Brush Script MT", cursive',
              fontSize: '84px',
              fontWeight: 700,
              color: '#ffffff',
              textShadow: '0 4px 20px rgba(0,0,0,0.95)',
              marginTop: '-12px',
              lineHeight: 1.05,
              textTransform: 'none',
            }}
          >
            {cue.scriptText}
          </span>
          {cue.showCursor && (
            <svg
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              style={{
                filter: 'drop-shadow(0 4px 10px rgba(0,0,0,0.9))',
                marginTop: -6,
                marginLeft: 120,
                transform: 'rotate(-20deg)',
              }}
            >
              <path
                d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z"
                fill="#ffffff"
                stroke="#171821"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>
      ) : (
        <span>{cue.text}</span>
      )}
    </div>
  );
};
