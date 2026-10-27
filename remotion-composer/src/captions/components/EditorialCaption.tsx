import React from 'react';
import { Img, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { CaptionStylePreset, KineticCue } from '../types/caption.types';
import { resolveAsset } from '../../lib/resolveAsset';

export interface EditorialCaptionProps {
  cue: KineticCue;
  preset: CaptionStylePreset;
}

export const EditorialCaption: React.FC<EditorialCaptionProps> = ({ cue, preset }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const firstFrame = Math.round(cue.start * fps);
  const lastFrame = Math.round(cue.end * fps);

  if (frame < firstFrame || frame >= lastFrame) {
    return null;
  }

  const activeFrame = frame - firstFrame;
  const duration = lastFrame - firstFrame;

  // Spring scale entrance: 0.94 -> 1.0
  const popProgress = Math.min(1, activeFrame / 5);
  const scale = 0.92 + 0.08 * (1 - Math.pow(1 - popProgress, 3));
  
  // Fade out on last 3 frames
  const fadeOutProgress = Math.max(0, activeFrame - (duration - 3));
  const opacity = fadeOutProgress > 0 ? 1 - fadeOutProgress / 3 : 1;

  const x = cue.x !== undefined ? cue.x * width : width * 0.5;
  const y = cue.y !== undefined ? cue.y * height : height * 0.68;

  const heroColor = cue.serifColor || cue.color || '#e5ff00';
  const bulletColor = cue.bulletColor || heroColor;
  const heroFont = cue.serifFontFamily || '"Playfair Display", "Instrument Serif", "Prata", Georgia, serif';
  const sansFont = cue.fontFamily || '"Outfit", "Inter", -apple-system, sans-serif';

  // Helper to render text with colored bullet dots
  const renderTextWithBullets = (str: string) => {
    if (!str.includes('•')) {
      return str;
    }
    const parts = str.split('•');
    return parts.map((part, idx) => (
      <React.Fragment key={idx}>
        <span>{part.trim()}</span>
        {idx < parts.length - 1 && (
          <span style={{ color: bulletColor, margin: '0 8px', fontSize: '1.2em', verticalAlign: 'middle' }}>
            •
          </span>
        )}
      </React.Fragment>
    ));
  };

  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${scale})`,
        opacity,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        width: 'max-content',
        maxWidth: width * 0.9,
        pointerEvents: 'none',
        userSelect: 'none',
        zIndex: 40,
      }}
    >
      {/* 1. Top Supporting Text (Thin Geometric Sans) */}
      {cue.topText && (
        <div
          style={{
            fontFamily: sansFont,
            fontSize: '38px',
            fontWeight: 400,
            letterSpacing: '0.02em',
            color: '#ffffff',
            lineHeight: 1.2,
            marginBottom: '4px',
            textShadow: '0 3px 12px rgba(0,0,0,0.85)',
          }}
        >
          {renderTextWithBullets(cue.topText)}
        </div>
      )}

      {/* 2. Hero Emphasis Word (Giant High-Contrast Editorial Serif) */}
      <div
        style={{
          fontFamily: heroFont,
          fontSize: '92px',
          fontWeight: 700,
          fontStyle: 'normal',
          letterSpacing: '-0.02em',
          lineHeight: 0.96,
          color: heroColor,
          textShadow: '0 4px 24px rgba(0,0,0,0.9)',
          textTransform: 'none',
          padding: '0 10px',
        }}
      >
        {cue.text}
      </div>

      {/* 3. Bottom Supporting Text (Thin Geometric Sans) */}
      {cue.bottomText && (
        <div
          style={{
            fontFamily: sansFont,
            fontSize: '36px',
            fontWeight: 400,
            letterSpacing: '0.01em',
            color: '#ffffff',
            lineHeight: 1.2,
            marginTop: '2px',
            alignSelf: 'flex-end',
            paddingRight: '6px',
            textShadow: '0 3px 12px rgba(0,0,0,0.85)',
          }}
        >
          {renderTextWithBullets(cue.bottomText)}
        </div>
      )}

      {/* 4. Feature Stickers (Soft-Yellow Rounded Icon Cards at Chest Level) */}
      {Array.isArray(cue.stickers) && cue.stickers.length > 0 && (
        <div
          style={{
            display: 'flex',
            gap: '18px',
            marginTop: '24px',
            justifyContent: 'center',
            alignItems: 'center',
          }}
        >
          {cue.stickers.map((st, sIdx) => {
            const delay = st.delayFrames || sIdx * 4;
            const stickerActive = Math.max(0, activeFrame - delay);
            const stickerSpring = spring({
              frame: stickerActive,
              fps,
              config: { damping: 12, stiffness: 180 },
            });

            return (
              <div
                key={st.id || `sticker-${sIdx}`}
                style={{
                  width: '106px',
                  height: '106px',
                  borderRadius: '24px',
                  backgroundColor: '#fef08a',
                  boxShadow: '0 14px 28px rgba(0,0,0,0.5)',
                  transform: `scale(${stickerSpring})`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden',
                }}
              >
                <Img
                  src={resolveAsset(st.src)}
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
