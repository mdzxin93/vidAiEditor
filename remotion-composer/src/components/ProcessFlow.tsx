import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface ProcessStep {
  stepNumber: number;
  title: string;
  description?: string;
  tag?: string;
}

export interface ProcessFlowProps {
  title?: string;
  steps: ProcessStep[];
  activeStep?: number;
  accentColor?: string;
  backgroundColor?: string;
  textColor?: string;
}

export const ProcessFlow: React.FC<ProcessFlowProps> = ({
  title = "PROCESS TIMELINE",
  steps,
  activeStep = 1,
  accentColor = "#38BDF8",
  backgroundColor = "#0F172A",
  textColor = "#FFFFFF",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 100 },
    from: 0,
    to: 1,
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor,
        padding: "24px 28px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      {title && (
        <div
          style={{
            opacity: titleSpring,
            transform: `translateY(${(1 - titleSpring) * -10}px)`,
            color: accentColor,
            fontSize: 20,
            fontWeight: 800,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            marginBottom: 20,
          }}
        >
          {title}
        </div>
      )}

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        {steps.map((st, i) => {
          const stepSpring = spring({
            frame: frame - (i * 6 + 4),
            fps,
            config: { damping: 13, stiffness: 120 },
            from: 0,
            to: 1,
          });

          const isActive = st.stepNumber === activeStep;

          return (
            <div
              key={st.stepNumber || i}
              style={{
                opacity: stepSpring,
                transform: `translateX(${(1 - stepSpring) * -20}px)`,
                display: "flex",
                alignItems: "center",
                gap: 16,
                background: isActive
                  ? "rgba(255, 255, 255, 0.08)"
                  : "rgba(255, 255, 255, 0.03)",
                border: isActive
                  ? `1px solid ${accentColor}`
                  : "1px solid rgba(255, 255, 255, 0.06)",
                borderRadius: 12,
                padding: "10px 16px",
              }}
            >
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: "50%",
                  background: isActive ? accentColor : "rgba(255, 255, 255, 0.12)",
                  color: isActive ? "#0F172A" : "#FFFFFF",
                  fontWeight: 800,
                  fontSize: 16,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                {st.stepNumber}
              </div>

              <div style={{ flex: 1 }}>
                <div
                  style={{
                    color: textColor,
                    fontWeight: 700,
                    fontSize: 22,
                    lineHeight: 1.2,
                  }}
                >
                  {st.title}
                </div>
                {st.description && (
                  <div
                    style={{
                      color: "rgba(255, 255, 255, 0.65)",
                      fontSize: 16,
                      fontWeight: 400,
                      marginTop: 2,
                    }}
                  >
                    {st.description}
                  </div>
                )}
              </div>

              {st.tag && (
                <div
                  style={{
                    background: "rgba(255, 255, 255, 0.1)",
                    borderRadius: 6,
                    padding: "2px 8px",
                    color: accentColor,
                    fontSize: 13,
                    fontWeight: 600,
                    textTransform: "uppercase",
                  }}
                >
                  {st.tag}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
