import {
  AbsoluteFill,
  Audio,
  Easing,
  OffthreadVideo,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { CaptionOverlay, WordCaption } from "./components/CaptionOverlay";
import { resolveAsset } from "./lib/resolveAsset";
import { TextCard } from "./components/TextCard";
import { StatCard } from "./components/StatCard";
import { CalloutBox } from "./components/CalloutBox";
import { ComparisonCard } from "./components/ComparisonCard";
import { BarChart } from "./components/charts/BarChart";
import { LineChart } from "./components/charts/LineChart";
import { PieChart } from "./components/charts/PieChart";
import { KPIGrid } from "./components/charts/KPIGrid";
import { HeroTitle } from "./components/HeroTitle";
import { SectionTitle } from "./components/SectionTitle";
import { StatReveal } from "./components/StatReveal";
import { ProcessFlow, ProcessStep } from "./components/ProcessFlow";
import { FeatureCard } from "./components/FeatureCard";
import { Img } from "remotion";

// ---------------------------------------------------------------------------
// Overlay types for talking-head video
// ---------------------------------------------------------------------------

export interface TalkingHeadOverlay {
  id?: string;
  type: string;
  in_seconds: number;
  out_seconds: number;
  position?:
    | "lower_third"
    | "upper_third"
    | "upper_window"
    | "left_panel"
    | "right_panel"
    | "full_overlay";
  // Component-specific props (same as Explainer Cut)
  text?: string;
  stat?: string;
  subtitle?: string;
  callout_type?: "info" | "warning" | "tip" | "quote";
  title?: string;
  leftLabel?: string;
  rightLabel?: string;
  leftValue?: string;
  rightValue?: string;
  chartData?: any[];
  chartSeries?: any[];
  chartColors?: string[];
  chartAnimation?: string;
  donut?: boolean;
  centerLabel?: string;
  centerValue?: string;
  showGrid?: boolean;
  showValues?: boolean;
  showLegend?: boolean;
  showMarkers?: boolean;
  columns?: 2 | 3 | 4;
  // B-roll & Media props
  mediaSrc?: string;
  isVideo?: boolean;
  // Stat trend props
  trend?: "positive" | "negative" | "neutral";
  trendDelta?: string;
  // ProcessFlow props
  steps?: ProcessStep[];
  activeStep?: number;
  // FeatureCard props
  categoryTag?: string;
  metric?: string;
  // Styling
  backgroundColor?: string;
  color?: string;
  accentColor?: string;
  fontSize?: number;
  statFontSize?: number;
  subtitleFontSize?: number;
  titleFontSize?: number;
}

// ---------------------------------------------------------------------------
// Position presets for 9:16 (1080x1920) frame
// ---------------------------------------------------------------------------

const POSITION_STYLES: Record<string, React.CSSProperties> = {
  lower_third: {
    position: "absolute",
    top: 50,
    left: 60,
    right: 60,
    height: 190,
  },
  upper_third: {
    position: "absolute",
    top: 50,
    left: 60,
    right: 60,
    height: 210,
  },
  upper_window: {
    position: "absolute",
    top: 50,
    left: 60,
    right: 60,
    height: 380,
  },
  left_panel: {
    position: "absolute",
    top: 50,
    left: 40,
    width: 480,
    bottom: 400,
  },
  right_panel: {
    position: "absolute",
    top: 50,
    right: 40,
    width: 480,
    bottom: 400,
  },
  full_overlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
};

// ---------------------------------------------------------------------------
// Overlay component dispatcher — maps overlay type to Remotion component
// ---------------------------------------------------------------------------

const OverlayContent: React.FC<{ overlay: TalkingHeadOverlay }> = ({
  overlay,
}) => {
  const bgColor = overlay.backgroundColor || "#0F172A";

  if (overlay.type === "text_card" && overlay.text) {
    return (
      <TextCard
        text={overlay.text}
        fontSize={overlay.fontSize}
        color={overlay.color}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "stat_card" && overlay.stat) {
    return (
      <StatCard
        stat={overlay.stat}
        subtitle={overlay.subtitle}
        accentColor={overlay.accentColor}
        backgroundColor={bgColor}
        statFontSize={overlay.statFontSize || 68}
        subtitleFontSize={overlay.subtitleFontSize || 26}
        trend={overlay.trend}
        trendDelta={overlay.trendDelta}
      />
    );
  }
  if (overlay.type === "callout" && overlay.text) {
    return (
      <CalloutBox
        text={overlay.text}
        type={overlay.callout_type}
        title={overlay.title}
        borderColor={overlay.accentColor}
        backgroundColor={overlay.backgroundColor}
        textColor={overlay.color}
        containerBackgroundColor={bgColor}
        fontSize={overlay.fontSize || 26}
        titleFontSize={overlay.titleFontSize || 30}
      />
    );
  }
  if (
    overlay.type === "comparison" &&
    overlay.leftLabel &&
    overlay.rightLabel
  ) {
    return (
      <ComparisonCard
        leftLabel={overlay.leftLabel}
        rightLabel={overlay.rightLabel}
        leftValue={overlay.leftValue || ""}
        rightValue={overlay.rightValue || ""}
        title={overlay.title}
        backgroundColor={bgColor}
        textColor={overlay.color}
      />
    );
  }
  if (overlay.type === "process_flow" && overlay.steps) {
    return (
      <ProcessFlow
        title={overlay.title}
        steps={overlay.steps}
        activeStep={overlay.activeStep}
        accentColor={overlay.accentColor}
        backgroundColor={bgColor}
        textColor={overlay.color}
      />
    );
  }
  if (overlay.type === "feature_card" && (overlay.title || overlay.text)) {
    return (
      <FeatureCard
        title={overlay.title || overlay.text || ""}
        subtitle={overlay.subtitle}
        categoryTag={overlay.categoryTag}
        metric={overlay.metric}
        accentColor={overlay.accentColor}
        backgroundColor={bgColor}
        textColor={overlay.color}
      />
    );
  }
  if (overlay.type === "broll" && overlay.mediaSrc) {
    const isVideo =
      overlay.isVideo ?? !overlay.mediaSrc.match(/\.(png|jpg|jpeg|webp)$/i);
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
          overflow: "hidden",
          borderRadius: overlay.position === "full_overlay" ? 0 : 16,
          border:
            overlay.position === "full_overlay"
              ? "none"
              : `2px solid ${overlay.accentColor || "rgba(255, 255, 255, 0.15)"}`,
        }}
      >
        {isVideo ? (
          <OffthreadVideo
            src={resolveAsset(overlay.mediaSrc)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <Img
            src={resolveAsset(overlay.mediaSrc)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        )}
        {overlay.title && (
          <div
            style={{
              position: "absolute",
              bottom: 16,
              left: 16,
              right: 16,
              background: "rgba(15, 23, 42, 0.88)",
              backdropFilter: "blur(8px)",
              padding: "6px 14px",
              borderRadius: 8,
              color: "#FFF",
              fontFamily: "Inter, sans-serif",
              fontSize: 18,
              fontWeight: 700,
              borderLeft: `4px solid ${overlay.accentColor || "#38BDF8"}`,
            }}
          >
            {overlay.title}
          </div>
        )}
      </div>
    );
  }
  if (overlay.type === "bar_chart" && overlay.chartData) {
    return (
      <BarChart
        data={overlay.chartData}
        title={overlay.title}
        colors={overlay.chartColors}
        animationStyle={(overlay.chartAnimation as any) || "grow-up"}
        showValues={overlay.showValues}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "line_chart" && overlay.chartSeries) {
    return (
      <LineChart
        series={overlay.chartSeries}
        title={overlay.title}
        colors={overlay.chartColors}
        animationStyle={(overlay.chartAnimation as any) || "draw"}
        showGrid={overlay.showGrid}
        showMarkers={overlay.showMarkers}
        showLegend={overlay.showLegend}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "pie_chart" && overlay.chartData) {
    return (
      <PieChart
        data={overlay.chartData}
        title={overlay.title}
        colors={overlay.chartColors}
        animationStyle={(overlay.chartAnimation as any) || "expand"}
        donut={overlay.donut}
        centerLabel={overlay.centerLabel}
        centerValue={overlay.centerValue}
        showLegend={overlay.showLegend}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "kpi_grid" && overlay.chartData) {
    return (
      <KPIGrid
        metrics={overlay.chartData}
        title={overlay.title}
        columns={overlay.columns}
        colors={overlay.chartColors}
        animationStyle={(overlay.chartAnimation as any) || "count-up"}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "hero_title" && overlay.text) {
    return <HeroTitle title={overlay.text} subtitle={overlay.subtitle} />;
  }
  if (overlay.type === "section_title" && overlay.text) {
    return (
      <SectionTitle
        title={overlay.text}
        subtitle={overlay.subtitle}
        accentColor={overlay.accentColor}
        position="top-left"
      />
    );
  }
  if (overlay.type === "stat_reveal" && overlay.text) {
    return (
      <StatReveal
        stat={overlay.text}
        label={overlay.subtitle}
        accentColor={overlay.accentColor}
        position="bottom-right"
      />
    );
  }
  return null;
};

// ---------------------------------------------------------------------------
// Positioned overlay wrapper — handles position + fade in/out
// ---------------------------------------------------------------------------

const PositionedOverlay: React.FC<{ overlay: TalkingHeadOverlay }> = ({
  overlay,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Fade in over 8 frames (~0.27s), fade out over 8 frames
  const fadeIn = interpolate(frame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 8, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const opacity = fadeIn * fadeOut;

  const position = overlay.position || "lower_third";
  const posStyle = POSITION_STYLES[position] || POSITION_STYLES.lower_third;
  const isFullOverlay = position === "full_overlay";

  return (
    <div
      style={{
        ...posStyle,
        opacity,
        overflow: "hidden",
        borderRadius: isFullOverlay ? 0 : 16,
        boxShadow: isFullOverlay
          ? "none"
          : "0 8px 32px rgba(0, 0, 0, 0.4)",
      }}
    >
      {isFullOverlay && (
        <AbsoluteFill style={{ background: "rgba(0, 0, 0, 0.7)" }} />
      )}
      <OverlayContent overlay={overlay} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main TalkingHead composition
// ---------------------------------------------------------------------------

export interface TalkingHeadCut {
  id?: string;
  source?: string;
  in_seconds: number;
  out_seconds: number;
  speed?: number;
  transform?: {
    scale?: number;
    position?: string;
  };
}

export interface TalkingHeadProps {
  [key: string]: unknown;
  videoSrc: string;
  cuts?: TalkingHeadCut[];
  captions: WordCaption[];
  overlays?: TalkingHeadOverlay[];
  wordsPerPage?: number;
  fontSize?: number;
  highlightColor?: string;
  captionColor?: string;
  captionBackgroundColor?: string;
  captionFontFamily?: string;
  // Pass "" for CJK captions (no inter-word spacing); defaults to " ".
  captionWordSeparator?: string;
  captionPaddingBottom?: number;
}

interface TalkingHeadCutItemProps {
  cut: TalkingHeadCut;
  durationFrames: number;
  src: string;
  fps: number;
  idx: number;
  previousScale?: number;
}

const TalkingHeadCutItem: React.FC<TalkingHeadCutItemProps> = ({
  cut,
  durationFrames,
  src,
  fps,
  idx,
  previousScale = 1.0,
}) => {
  const frame = useCurrentFrame();
  const baseScale = cut.transform?.scale || 1.0;

  // Smooth Fade In transition at start of cut (dissolve into cut, avoiding harsh pop)
  const fadeInFrames = idx === 0 ? 0 : 5;
  const fadeOpacity =
    fadeInFrames === 0
      ? 1.0
      : interpolate(frame, [0, fadeInFrames], [0.35, 1.0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.out(Easing.quad),
        });

  // Dynamic zoom transition: smoothly zoom in / zoom out when cut framing changes
  let animatedScale = baseScale;
  if (idx > 0 && Math.abs(baseScale - previousScale) > 0.03) {
    const zoomTransFrames = Math.min(8, Math.floor(durationFrames / 2));
    if (frame < zoomTransFrames) {
      const zoomProgress = interpolate(frame, [0, zoomTransFrames], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.cubic),
      });
      const startScale =
        baseScale > previousScale
          ? baseScale * 0.94 // zoom in motion
          : baseScale * 1.06; // zoom out motion
      animatedScale = startScale + (baseScale - startScale) * zoomProgress;
    }
  }

  // Subtle continuous cinematic drift (gentle zoom in)
  const driftScale = interpolate(
    frame,
    [0, durationFrames],
    [1.0, 1.02],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const finalScale = animatedScale * driftScale;

  return (
    <AbsoluteFill style={{ overflow: "hidden", opacity: fadeOpacity }}>
      <OffthreadVideo
        src={resolveAsset(src)}
        startFrom={Math.round(cut.in_seconds * fps)}
        playbackRate={cut.speed || 1.0}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${finalScale})`,
          transformOrigin: "center 35%",
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

export const TalkingHead: React.FC<TalkingHeadProps> = ({
  videoSrc,
  cuts,
  captions,
  overlays,
  wordsPerPage = 4,
  fontSize = 52,
  highlightColor = "#22D3EE",
  captionColor = "#FFFFFF",
  captionBackgroundColor = "rgba(0, 0, 0, 0.65)",
  captionFontFamily,
  captionWordSeparator,
  captionPaddingBottom = 340,
}) => {
  const { fps } = useVideoConfig();

  const hasCuts = Array.isArray(cuts) && cuts.length > 0;
  let accumulatedFrames = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Layer 1: Video background & audio (either sequenced cuts with smooth zoom-in, zoom-out, and fade transitions or continuous video) */}
      {hasCuts ? (
        cuts!.map((cut, idx) => {
          const cutDurationSeconds =
            (cut.out_seconds - cut.in_seconds) / (cut.speed || 1.0);
          const durationFrames = Math.max(1, Math.round(cutDurationSeconds * fps));
          const fromFrame = accumulatedFrames;
          accumulatedFrames += durationFrames;
          const src = cut.source || videoSrc;
          const previousCut = idx > 0 ? cuts![idx - 1] : undefined;
          const prevScale = previousCut?.transform?.scale || 1.0;

          return (
            <Sequence
              key={cut.id || `cut-${idx}`}
              from={fromFrame}
              durationInFrames={durationFrames}
            >
              <TalkingHeadCutItem
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
      ) : (
        <>
          <OffthreadVideo
            src={resolveAsset(videoSrc)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
          <Audio src={resolveAsset(videoSrc)} />
        </>
      )}

      {/* Layer 2: Overlays (charts, stats, callouts, etc.) */}
      {overlays?.map((overlay, i) => {
        const inSec =
          typeof overlay.in_seconds === "number" && !isNaN(overlay.in_seconds)
            ? overlay.in_seconds
            : typeof (overlay as any).start_seconds === "number" &&
              !isNaN((overlay as any).start_seconds)
            ? (overlay as any).start_seconds
            : 0;
        const outSec =
          typeof overlay.out_seconds === "number" && !isNaN(overlay.out_seconds)
            ? overlay.out_seconds
            : typeof (overlay as any).end_seconds === "number" &&
              !isNaN((overlay as any).end_seconds)
            ? (overlay as any).end_seconds
            : inSec + 3;
        const from = Math.max(0, Math.round(inSec * fps));
        const duration = Math.max(1, Math.round((outSec - inSec) * fps));
        return (
          <Sequence
            key={overlay.id || (overlay as any).asset_id || `overlay-${i}`}
            from={from}
            durationInFrames={duration}
          >
            <PositionedOverlay overlay={overlay} />
          </Sequence>
        );
      })}

      {/* Layer 3: Captions (topmost — always visible above overlays) */}
      <CaptionOverlay
        words={captions}
        wordsPerPage={wordsPerPage}
        fontSize={fontSize}
        highlightColor={highlightColor}
        backgroundColor={captionBackgroundColor}
        color={captionColor}
        paddingBottom={captionPaddingBottom}
        {...(captionFontFamily ? { fontFamily: captionFontFamily } : {})}
        {...(captionWordSeparator !== undefined ? { wordSeparator: captionWordSeparator } : {})}
      />
    </AbsoluteFill>
  );
};
