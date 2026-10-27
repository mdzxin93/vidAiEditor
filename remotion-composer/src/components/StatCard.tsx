import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface StatCardProps {
  stat: string;
  subtitle?: string;
  statFontSize?: number;
  subtitleFontSize?: number;
  color?: string;
  accentColor?: string;
  backgroundColor?: string;
  trend?: "positive" | "negative" | "neutral";
  trendDelta?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  stat,
  subtitle,
  statFontSize = 128,
  subtitleFontSize = 36,
  color = "#FFFFFF",
  accentColor = "#F59E0B",
  backgroundColor = "#1F2937",
  trend,
  trendDelta,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 120 },
    from: 0.8,
    to: 1,
  });

  const subtitleOpacity = spring({
    frame: frame - 8,
    fps,
    config: { damping: 20 },
  });

  const badgeScale = spring({
    frame: frame - 5,
    fps,
    config: { damping: 14, stiffness: 140 },
    from: 0.5,
    to: 1,
  });

  // Infer trend if not explicitly passed
  let resolvedTrend = trend;
  if (!resolvedTrend) {
    if (stat.startsWith("-") || (trendDelta && trendDelta.startsWith("-"))) {
      resolvedTrend = "negative";
    } else if (stat.startsWith("+") || (trendDelta && trendDelta.startsWith("+"))) {
      resolvedTrend = "positive";
    }
  }

  const isNeg = resolvedTrend === "negative";
  const isPos = resolvedTrend === "positive";
  const trendColor = isNeg ? "#EF4444" : isPos ? "#10B981" : accentColor;
  const trendIcon = isNeg ? "▼" : isPos ? "▲" : "•";

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: backgroundColor,
      }}
    >
      <div style={{ textAlign: "center", padding: "0 24px" }}>
        {trendDelta && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              background: isNeg
                ? "rgba(239, 68, 68, 0.2)"
                : isPos
                ? "rgba(16, 185, 129, 0.2)"
                : "rgba(255, 255, 255, 0.1)",
              border: `1px solid ${trendColor}`,
              borderRadius: 999,
              padding: "4px 14px",
              marginBottom: 10,
              transform: `scale(${badgeScale})`,
            }}
          >
            <span style={{ color: trendColor, fontSize: 16, fontWeight: 700 }}>
              {trendIcon}
            </span>
            <span
              style={{
                color: "#FFFFFF",
                fontSize: 16,
                fontWeight: 600,
                fontFamily: "Inter, system-ui, sans-serif",
              }}
            >
              {trendDelta}
            </span>
          </div>
        )}
        <div
          style={{
            transform: `scale(${scale})`,
            fontSize: statFontSize,
            color: trendColor || accentColor,
            fontFamily: "Inter, system-ui, sans-serif",
            fontWeight: 800,
            lineHeight: 1.1,
            letterSpacing: "-0.02em",
          }}
        >
          {stat}
        </div>
        {subtitle && (
          <div
            style={{
              opacity: subtitleOpacity,
              fontSize: subtitleFontSize,
              color,
              fontFamily: "Inter, system-ui, sans-serif",
              fontWeight: 400,
              marginTop: 14,
              lineHeight: 1.3,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

