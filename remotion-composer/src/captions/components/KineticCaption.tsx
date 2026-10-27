import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { CaptionStylePreset, KineticCue } from '../types/caption.types';
import { computeCueLayout } from '../utils/captionLayout';
import { computeCueAnimation } from '../utils/captionAnimations';
import { isWordActive } from '../utils/captionTiming';

export interface KineticCaptionProps {
  cue: KineticCue;
  preset: CaptionStylePreset;
}

export const KineticCaption: React.FC<KineticCaptionProps> = ({ cue, preset }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const currentSeconds = frame / fps;
  const firstFrame = Math.round(cue.start * fps);
  const lastFrame = Math.round(cue.end * fps);

  // Frame gating for deterministic rendering
  if (frame < firstFrame || frame >= lastFrame) {
    return null;
  }

  const { x, y, fontSize, maxWidth } = computeCueLayout(cue, preset, width, height);
  const { scale, opacity } = computeCueAnimation(frame, firstFrame, lastFrame, preset);

  const fontFamily = cue.fontFamily || `"${preset.font_family}", Inter, -apple-system, sans-serif`;
  const fontWeight = cue.fontWeight || preset.font_weight || 800;
  const fontColor = cue.color || preset.font_color || '#FFFFFF';
  const letterSpacing = preset.letter_spacing_em !== undefined ? `${preset.letter_spacing_em}em` : '-0.05em';
  const textShadow = preset.shadow_enabled ? preset.shadow_style || '0 2px 6px rgba(0,0,0,0.3)' : 'none';

  const hasWords = Array.isArray(cue.words) && cue.words.length > 0;

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
        lineHeight: 1.05,
        textAlign: preset.text_alignment || 'center',
        whiteSpace: 'normal',
        wordBreak: 'break-word',
        textShadow,
        pointerEvents: 'none',
        userSelect: 'none',
        WebkitTextStroke: preset.outline_enabled
          ? `${preset.outline_width_px || 3}px ${preset.outline_color || 'black'}`
          : 'none',
        paintOrder: 'stroke fill',
      }}
    >
      {/* Background container if configured */}
      {preset.background && preset.background !== 'transparent' && (
        <div
          style={{
            position: 'absolute',
            inset: '-8px -16px',
            backgroundColor: preset.background,
            backdropFilter: preset.background_blur_px ? `blur(${preset.background_blur_px}px)` : undefined,
            borderRadius: preset.background_border_radius_px || 12,
            zIndex: -1,
          }}
        />
      )}

      {/* Two-tier glowing red sans + white script badge (matches reference video hero callout) */}
      {cue.scriptText ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', pointerEvents: 'none' }}>
          <span
            style={{
              color: cue.color || '#ff1f38',
              fontSize: '84px',
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
              fontSize: '96px',
              fontWeight: 700,
              color: '#ffffff',
              textShadow: '0 4px 20px rgba(0,0,0,0.95)',
              marginTop: '-14px',
              lineHeight: 1.05,
            }}
          >
            {cue.scriptText}
          </span>
          {cue.showCursor && (
            <svg
              width="44"
              height="44"
              viewBox="0 0 24 24"
              fill="none"
              style={{
                filter: 'drop-shadow(0 4px 10px rgba(0,0,0,0.9))',
                marginTop: -8,
                marginLeft: 140,
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
      ) : !preset.highlight_active_word ? (
        <span>{cue.text}</span>
      ) : hasWords ? (
        cue.words!.map((w, idx) => {
          const nextWord = cue.words![idx + 1];
          const active = isWordActive(w.start, w.end, nextWord?.start, currentSeconds);
          const isEmphasized = w.isEmphasized || false;
          const wordColor = active
            ? preset.emphasis_color || '#22D3EE'
            : isEmphasized
            ? '#FACC15'
            : fontColor;

          return (
            <span
              key={`${w.start}-${idx}`}
              style={{
                display: 'inline-block',
                margin: '0 4px',
                color: wordColor,
                transform: active ? 'scale(1.06)' : 'scale(1.0)',
                transformOrigin: 'center center',
                transition: 'none',
                textShadow: active
                  ? `0 0 20px ${wordColor}88, ${textShadow}`
                  : textShadow,
              }}
            >
              {w.word}
            </span>
          );
        })
      ) : (
        <span>{cue.text}</span>
      )}

      {/* Support word (split stack layout e.g. "on my" above "podcast") */}
      {cue.support && (
        <span
          style={{
            position: 'absolute',
            fontSize: `${(cue.support.scale || 0.5) * 100}%`,
            fontWeight: Math.max(600, fontWeight - 100),
            letterSpacing: '-0.02em',
            opacity: 0.9,
            whiteSpace: 'nowrap',
            ...(cue.support.position === 'top-left'
              ? { bottom: '100%', left: 0, marginBottom: 4 }
              : cue.support.position === 'top-right'
              ? { bottom: '100%', right: 0, marginBottom: 4 }
              : cue.support.position === 'bottom-right'
              ? { top: '100%', right: 0, marginTop: 4 }
              : cue.support.position === 'bottom-left'
              ? { top: '100%', left: 0, marginTop: 4 }
              : { bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: 4 }),
          }}
        >
          {cue.support.text}
        </span>
      )}
    </div>
  );
};
