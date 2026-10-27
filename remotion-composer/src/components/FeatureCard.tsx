import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface FeatureCardProps {
  title: string;
  subtitle?: string;
  categoryTag?: string;
  metric?: string;
  accentColor?: string;
  backgroundColor?: string;
  textColor?: string;
}

export const FeatureCard: React.FC<FeatureCardProps> = ({
  title,
  subtitle,
  categoryTag = "CAPABILITY",
  metric,
  accentColor = "#38BDF8",
  backgroundColor = "#0F172A",
  textColor = "#FFFFFF",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const cardScale = spring({
    frame,
    fps,
    config: { damping: 13, stiffness: 110 },
    from: 0.88,
    to: 1,
  });

  const contentOpacity = spring({
    frame: frame - 4,
    fps,
    config: { damping: 18 },
    from: 0,
    to: 1,
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor,
        padding: "24px 30px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        fontFamily: "Inter, system-ui, sans-serif",
        borderLeft: `5px solid ${accentColor}`,
      }}
    >
      <div
        style={{
          transform: `scale(${cardScale})`,
          opacity: contentOpacity,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          {categoryTag && (
            <span
              style={{
                color: accentColor,
                fontSize: 15,
                fontWeight: 800,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              {categoryTag}
            </span>
          )}
          {metric && (
            <span
              style={{
                background: "rgba(255, 255, 255, 0.1)",
                border: `1px solid ${accentColor}`,
                color: "#FFFFFF",
                fontSize: 14,
                fontWeight: 700,
                padding: "3px 10px",
                borderRadius: 999,
              }}
            >
              {metric}
            </span>
          )}
        </div>

        <div
          style={{
            color: textColor,
            fontSize: 28,
            fontWeight: 800,
            lineHeight: 1.15,
            letterSpacing: "-0.01em",
          }}
        >
          {title}
        </div>

        {subtitle && (
          <div
            style={{
              color: "rgba(255, 255, 255, 0.75)",
              fontSize: 18,
              fontWeight: 400,
              lineHeight: 1.35,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
