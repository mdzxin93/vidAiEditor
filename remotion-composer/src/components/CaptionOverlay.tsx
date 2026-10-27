import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// Word-level caption for TikTok-style highlight display
export interface WordCaption {
  word: string;
  startMs?: number;
  endMs?: number;
  start?: number; // In seconds (from Whisper/transcriber)
  end?: number;   // In seconds (from Whisper/transcriber)
  // Force a page break after this word (e.g. sentence or scene boundaries).
  // Useful for CJK captions where pages should align with clause boundaries.
  pageBreakAfter?: boolean;
}

type CaptionOverlayProps = {
  words: WordCaption[];
  // How many words to show at once in a "page"
  wordsPerPage?: number;
  fontSize?: number;
  color?: string;
  highlightColor?: string;
  backgroundColor?: string;
  fontFamily?: string;
  paddingBottom?: number;
  // Separator rendered between words. Space-delimited languages want the
  // default " "; CJK languages (no inter-word spacing) should pass "".
  wordSeparator?: string;
};

interface CaptionPage {
  words: { word: string; startMs: number; endMs: number; pageBreakAfter?: boolean }[];
  startMs: number;
  endMs: number;
}

function buildPages(words: WordCaption[], wordsPerPage: number): CaptionPage[] {
  const normalizedWords = (words || []).map((w) => {
    const startMs =
      w.startMs !== undefined
        ? w.startMs
        : w.start !== undefined
        ? Math.round(w.start * 1000)
        : 0;
    const endMs =
      w.endMs !== undefined
        ? w.endMs
        : w.end !== undefined
        ? Math.round(w.end * 1000)
        : startMs + 300;
    return {
      word: w.word || "",
      startMs,
      endMs,
      pageBreakAfter: w.pageBreakAfter,
    };
  });

  const pages: CaptionPage[] = [];
  let pageWords: { word: string; startMs: number; endMs: number; pageBreakAfter?: boolean }[] = [];
  const flush = () => {
    if (pageWords.length === 0) return;
    pages.push({
      words: pageWords,
      startMs: pageWords[0].startMs,
      endMs: pageWords[pageWords.length - 1].endMs,
    });
    pageWords = [];
  };
  for (const w of normalizedWords) {
    pageWords.push(w);
    if (pageWords.length >= wordsPerPage || w.pageBreakAfter) flush();
  }
  flush();
  return pages;
}

const PageRenderer: React.FC<{
  page: CaptionPage;
  fontSize: number;
  color: string;
  highlightColor: string;
  backgroundColor: string;
  fontFamily: string;
  wordSeparator: string;
  paddingBottom: number;
}> = ({ page, fontSize, color, highlightColor, backgroundColor, fontFamily, wordSeparator, paddingBottom }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentMs = page.startMs + (frame / fps) * 1000;

  // Fast, subtle 2-frame fade with ZERO vertical movement (no jumping spring)
  const opacity = interpolate(frame, [0, 2], [0.6, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          opacity,
          backgroundColor: backgroundColor || "rgba(10, 15, 29, 0.65)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          borderRadius: 18,
          padding: "14px 28px",
          maxWidth: "86%",
          textAlign: "center",
          border: "1px solid rgba(255, 255, 255, 0.12)",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.4)",
        }}
      >
        <span
          style={{
            fontSize,
            fontWeight: 800,
            fontFamily: fontFamily || "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            lineHeight: 1.35,
            letterSpacing: "-0.01em",
            whiteSpace: "pre-wrap",
          }}
        >
          {page.words.map((w, i) => {
            const nextWord = page.words[i + 1];
            // Smoothly bridge micro-gaps between consecutive words in a phrase
            const activeEnd = nextWord ? nextWord.startMs : w.endMs;
            const isActive = currentMs >= w.startMs && currentMs < activeEnd;
            const isPast = currentMs >= activeEnd;
            return (
              <span
                key={`${w.startMs}-${i}`}
                style={{
                  display: "inline-block",
                  whiteSpace: "nowrap",
                  margin: "0 6px",
                  transform: isActive ? "scale(1.08)" : "scale(1.0)",
                  transformOrigin: "center center",
                  color: isActive ? highlightColor : isPast ? color : `${color}88`,
                  transition: "none",
                  textShadow: isActive
                    ? `0 0 20px ${highlightColor}, 0 2px 8px rgba(0,0,0,0.9)`
                    : "0 2px 6px rgba(0,0,0,0.85)",
                }}
              >
                {w.word}
              </span>
            );
          })}
        </span>
      </div>
    </AbsoluteFill>
  );
};

export const CaptionOverlay: React.FC<CaptionOverlayProps> = ({
  words,
  wordsPerPage = 6,
  fontSize = 42,
  color = "#F8FAFC",
  highlightColor = "#22D3EE",
  backgroundColor = "rgba(15, 23, 42, 0.75)",
  fontFamily = "Space Grotesk, Inter, system-ui, sans-serif",
  paddingBottom = 340,
  wordSeparator = " ",
}) => {
  const { fps } = useVideoConfig();
  const pages = buildPages(words, wordsPerPage);

  return (
    <AbsoluteFill>
      {pages.map((page, i) => {
        const fromFrame = Math.round((page.startMs / 1000) * fps);
        const nextStart = pages[i + 1]?.startMs ?? page.endMs + 500;
        const duration = Math.max(
          1,
          Math.round(((nextStart - page.startMs) / 1000) * fps)
        );

        return (
          <Sequence key={i} from={fromFrame} durationInFrames={duration}>
            <PageRenderer
              page={page}
              fontSize={fontSize}
              color={color}
              highlightColor={highlightColor}
              backgroundColor={backgroundColor}
              fontFamily={fontFamily}
              wordSeparator={wordSeparator}
              paddingBottom={paddingBottom}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
