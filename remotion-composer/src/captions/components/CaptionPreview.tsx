import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  interpolate,
  OffthreadVideo,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {
  BRollOverlayEvent,
  CaptionStylePreset,
  KineticCue,
  VideoCut,
} from '../types/caption.types';
import { CaptionSequence } from './CaptionSequence';
import defaultPreset from '../presets/caption_style_reference.json';
import { resolveAsset } from '../../lib/resolveAsset';

interface BrollOverlayItemProps {
  overlay: BRollOverlayEvent;
  durationInFrames: number;
}

const BrollOverlayItem: React.FC<BrollOverlayItemProps> = ({
  overlay,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const isVideo =
    overlay.asset_path.endsWith('.mp4') ||
    overlay.asset_path.endsWith('.webm');

  // Smooth Fade In (first 6 frames) and Fade Out (last 6 frames)
  const fadeInFrames = 6;
  const fadeOutFrames = 6;
  const fadeIn = interpolate(frame, [0, fadeInFrames], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });
  const fadeOut = interpolate(
    frame,
    [Math.max(0, durationInFrames - fadeOutFrames), durationInFrames],
    [1, 0],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.in(Easing.quad),
    }
  );
  const opacity = fadeIn * fadeOut;

  // Zoom In entrance (0.90 -> 1.0) with subtle spring ease, gentle floating drift, and Zoom Out on exit (1.0 -> 0.95)
  const popScale = interpolate(frame, [0, 8], [0.90, 1.0], {
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(1.15)),
  });

  const driftScale = interpolate(
    frame,
    [8, Math.max(9, durationInFrames - fadeOutFrames)],
    [1.0, 1.025],
    { extrapolateRight: 'clamp' }
  );

  const exitScale = interpolate(
    frame,
    [Math.max(0, durationInFrames - fadeOutFrames), durationInFrames],
    [1.0, 0.95],
    { extrapolateLeft: 'clamp', easing: Easing.in(Easing.cubic) }
  );

  const cardScale =
    (frame < 8 ? popScale : driftScale) *
    (frame >= durationInFrames - fadeOutFrames ? exitScale : 1.0);

  const sfxPath = overlay.sfx
    ? overlay.sfx.includes('.')
      ? overlay.sfx
      : `editing-stock/audio/sfx/${overlay.sfx}.wav`
    : null;

  const isCard = overlay.displayMode === 'card';
  const borderRadius = overlay.cardBorderRadius || 36;

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        opacity,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        pointerEvents: 'none',
        zIndex: 25,
      }}
    >
      {sfxPath && (
        <Audio src={resolveAsset(sfxPath)} volume={0.4} />
      )}
      {isCard ? (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            backgroundColor: 'rgba(0, 0, 0, 0.82)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: '85%',
              height: '76%',
              borderRadius: `${borderRadius}px`,
              overflow: 'hidden',
              boxShadow:
                '0 24px 60px rgba(0, 0, 0, 0.85), 0 0 0 1px rgba(255, 255, 255, 0.08)',
              transform: `scale(${cardScale})`,
              backgroundColor: '#121316',
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {isVideo ? (
              <OffthreadVideo
                src={resolveAsset(overlay.asset_path)}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                }}
              />
            ) : (
              <Img
                src={resolveAsset(overlay.asset_path)}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            )}
          </div>
        </div>
      ) : (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            transform: `scale(${cardScale})`,
            backgroundColor: '#f6f6f4',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
          }}
        >
          {isVideo ? (
            <OffthreadVideo
              src={resolveAsset(overlay.asset_path)}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
              }}
            />
          ) : (
            <Img
              src={resolveAsset(overlay.asset_path)}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            />
          )}
        </div>
      )}
    </div>
  );
};

interface VideoCutItemProps {
  cut: VideoCut;
  durationFrames: number;
  src: string;
  fps: number;
  idx: number;
  previousScale?: number;
}

const VideoCutItem: React.FC<VideoCutItemProps> = ({
  cut,
  durationFrames,
  src,
  fps,
  idx,
  previousScale = 1.0,
}) => {
  const frame = useCurrentFrame();
  const baseScale = cut.transform?.scale || 1.0;

  // Smooth Fade In on cut entrance (dissolve into cut, avoiding harsh pop)
  const fadeInFrames = idx === 0 ? 0 : 5;
  const fadeOpacity =
    fadeInFrames === 0
      ? 1.0
      : interpolate(frame, [0, fadeInFrames], [0.35, 1.0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
          easing: Easing.out(Easing.quad),
        });

  // Dynamic zoom transition: smoothly zoom in / zoom out when cut framing changes
  let animatedScale = baseScale;
  if (idx > 0 && Math.abs(baseScale - previousScale) > 0.03) {
    const zoomTransFrames = Math.min(8, Math.floor(durationFrames / 2));
    if (frame < zoomTransFrames) {
      const zoomProgress = interpolate(frame, [0, zoomTransFrames], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.out(Easing.cubic),
      });
      // Start scale slightly closer to previous perspective, smoothly moving to baseScale
      const startScale =
        baseScale > previousScale
          ? baseScale * 0.94 // zoom-in motion
          : baseScale * 1.06; // zoom-out motion
      animatedScale = startScale + (baseScale - startScale) * zoomProgress;
    }
  }

  // Subtle continuous cinematic drift (gentle zoom in) to keep footage dynamic and alive
  const driftScale = interpolate(
    frame,
    [0, durationFrames],
    [1.0, 1.02],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  const finalScale = animatedScale * driftScale;

  return (
    <AbsoluteFill style={{ overflow: 'hidden', opacity: fadeOpacity }}>
      <OffthreadVideo
        src={resolveAsset(src)}
        startFrom={Math.round(cut.in_seconds * fps)}
        playbackRate={cut.speed || 1.0}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `scale(${finalScale})`,
          transformOrigin: 'center 35%', // Preserves speaker face and eye-level framing
        }}
      />
      <Audio
        src={resolveAsset(src)}
        startFrom={Math.round(cut.in_seconds * fps)}
        playbackRate={cut.speed || 1.0}
      />
    </AbsoluteFill>
  );
};

export interface CaptionPreviewProps extends Record<string, unknown> {
  videoSrc?: string;
  cuts?: VideoCut[];
  cues: KineticCue[];
  overlays?: BRollOverlayEvent[];
  preset?: CaptionStylePreset;
  bgmSrc?: string;
  bgmVolume?: number;
  flares?: Array<{ startSeconds: number; durationFrames?: number }>;
}

export const CaptionPreview: React.FC<CaptionPreviewProps> = ({
  videoSrc,
  cuts,
  cues,
  overlays,
  preset,
  bgmSrc,
  bgmVolume,
}) => {
  const { fps } = useVideoConfig();
  const activePreset = preset || (defaultPreset as CaptionStylePreset);
  const hasCuts = Array.isArray(cuts) && cuts.length > 0;
  let accumulatedFrames = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: '#000000' }}>
      {/* Background Music Layer */}
      {bgmSrc && (
        <Audio
          src={resolveAsset(bgmSrc)}
          volume={bgmVolume !== undefined ? bgmVolume : 0.12}
        />
      )}

      {/* Layer 1: Source video & audio (sequenced cuts with smooth zoom-in, zoom-out, and fade transitions) */}
      {hasCuts ? (
        cuts!.map((cut, idx) => {
          const cutDurationSeconds =
            (cut.out_seconds - cut.in_seconds) / (cut.speed || 1.0);
          const durationFrames = Math.max(1, Math.round(cutDurationSeconds * fps));
          const fromFrame = accumulatedFrames;
          accumulatedFrames += durationFrames;
          const src = cut.source || videoSrc || '';
          const previousCut = idx > 0 ? cuts![idx - 1] : undefined;
          const prevScale = previousCut?.transform?.scale || 1.0;

          return (
            <Sequence
              key={cut.id || `cut-${idx}`}
              from={fromFrame}
              durationInFrames={durationFrames}
            >
              <VideoCutItem
                cut={cut}
                durationFrames={durationFrames}
                src={src}
                fps={fps}
                idx={idx}
                previousScale={prevScale}
              />
            </Sequence>
          );
        })
      ) : videoSrc ? (
        <>
          <OffthreadVideo
            src={resolveAsset(videoSrc)}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
          <Audio src={resolveAsset(videoSrc)} />
        </>
      ) : null}

      {/* Layer 2: Animated Kinetic Captions (active during A-Roll talking head) */}
      <CaptionSequence cues={cues} preset={activePreset} />

      {/* Layer 3: Full-Screen B-Roll & Technical Blueprint Grid Scenes with Smooth Zoom & Fade */}
      {Array.isArray(overlays) &&
        overlays.map((ov, idx) => {
          const startFrame = Math.round(ov.start_seconds * fps);
          const durationFrames = Math.max(
            1,
            Math.round((ov.end_seconds - ov.start_seconds) * fps)
          );
          return (
            <Sequence
              key={ov.id || `overlay-${idx}`}
              from={startFrame}
              durationInFrames={durationFrames}
            >
              <BrollOverlayItem overlay={ov} durationInFrames={durationFrames} />
            </Sequence>
          );
        })}
    </AbsoluteFill>
  );
};

