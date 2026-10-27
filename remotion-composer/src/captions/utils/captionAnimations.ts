import { Easing, interpolate } from 'remotion';
import { CaptionStylePreset } from '../types/caption.types';

export interface CueAnimationState {
  scale: number;
  opacity: number;
}

export function computeCueAnimation(
  frame: number,
  firstFrame: number,
  lastFrame: number,
  preset: CaptionStylePreset
): CueAnimationState {
  const duration = Math.max(1, lastFrame - firstFrame);
  const relFrame = frame - firstFrame;

  const anim = preset.animation;
  const enterFrames = Math.max(1, Math.min(anim.enter_frames || 3, duration));
  const exitFrames = Math.max(1, Math.min(anim.exit_frames || 2, duration));

  // Determine easing function
  let easeFn = Easing.out(Easing.cubic);
  if (anim.easing === 'easeOutBack') {
    easeFn = Easing.out(Easing.back(1.4));
  } else if (anim.easing === 'linear') {
    easeFn = Easing.linear;
  }

  // Entrance progress: 0.0 to 1.0
  const enterProgress = interpolate(
    relFrame,
    [0, enterFrames],
    [0, 1],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: easeFn,
    }
  );

  // Exit progress: 1.0 to 0.0
  const exitProgress = interpolate(
    relFrame,
    [duration - exitFrames, duration],
    [1, 0],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.in(Easing.cubic),
    }
  );

  // Scale computation
  const initialScale = anim.initial_scale ?? 0.94;
  const finalScale = anim.final_scale ?? 1.0;
  const exitScale = anim.exit_scale ?? finalScale;

  let scale = initialScale + (finalScale - initialScale) * enterProgress;
  if (relFrame >= duration - exitFrames && exitScale !== finalScale) {
    const exitFraction = 1.0 - exitProgress;
    scale = finalScale + (exitScale - finalScale) * exitFraction;
  }

  // Opacity computation
  let opacity = 1.0;
  if (anim.fade_in && anim.fade_out) {
    opacity = Math.min(enterProgress, exitProgress);
  } else if (anim.fade_in) {
    opacity = enterProgress;
  } else if (anim.fade_out) {
    opacity = exitProgress;
  }

  return { scale, opacity };
}
