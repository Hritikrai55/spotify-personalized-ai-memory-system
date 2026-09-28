"use client";

import { useState, useRef, useEffect, Fragment } from "react";
import { sendMessage } from "../lib/api";

type ChatMessage = {
  role: "user" | "bot";
  text: string;
};

/**
 * Render inline Markdown such as:
 * **bold text**
 * *italic text*
 */
function renderInlineMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={index}>
          {part.slice(2, -2)}
        </strong>
      );
    }

    if (part.startsWith("*") && part.endsWith("*")) {
      return (
        <em key={index}>
          {part.slice(1, -1)}
        </em>
      );
    }

    return <Fragment key={index}>{part}</Fragment>;
  });
}

/**
 * Detect a Markdown table.
 */
function isTableLine(line: string) {
  return line.trim().startsWith("|") && line.trim().endsWith("|");
}

function isTableSeparator(line: string) {
  return /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(line);
}

/**
 * Convert Markdown table rows into cells.
 */
function parseTableRow(line: string) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

/**
 * Render the AI response with basic Markdown support.
 *
 * Supported:
 * - **bold**
 * - *italic*
 * - bullet lists
 * - numbered lists
 * - Markdown tables
 * - normal paragraphs
 */
function FormattedMessage({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");

  const elements: React.ReactNode[] = [];

  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Empty line
    if (!line.trim()) {
      i++;
      continue;
    }

    // Markdown table
    if (
      i + 1 < lines.length &&
      isTableLine(line) &&
      isTableSeparator(lines[i + 1])
    ) {
      const headers = parseTableRow(line);

      const rows: string[][] = [];

      i += 2;

      while (i < lines.length && isTableLine(lines[i])) {
        rows.push(parseTableRow(lines[i]));
        i++;
      }

      elements.push(
        <div className="response-table-wrapper" key={`table-${i}`}>
          <table className="response-table">
            <thead>
              <tr>
                {headers.map((header, index) => (
                  <th key={index}>{renderInlineMarkdown(header)}</th>
                ))}
              </tr>
            </thead>

            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {headers.map((_, cellIndex) => (
                    <td key={cellIndex}>
                      {renderInlineMarkdown(row[cellIndex] || "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );

      continue;
    }

    // Bullet list
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];

      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }

      elements.push(
        <ul className="response-list" key={`ul-${i}`}>
          {items.map((item, index) => (
            <li key={index}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>
      );

      continue;
    }

    // Numbered list
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];

      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }

      elements.push(
        <ol className="response-list" key={`ol-${i}`}>
          {items.map((item, index) => (
            <li key={index}>{renderInlineMarkdown(item)}</li>
          ))}
        </ol>
      );

      continue;
    }

    // Heading
    if (/^\s*#{1,3}\s+/.test(line)) {
      const heading = line.replace(/^\s*#{1,3}\s+/, "");

      elements.push(
        <h3 className="response-heading" key={`heading-${i}`}>
          {renderInlineMarkdown(heading)}
        </h3>
      );

      i++;
      continue;
    }

    // Normal paragraph.
    const paragraphLines = [line];
    i++;

    while (
      i < lines.length &&
      lines[i].trim() &&
      !isTableLine(lines[i]) &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i]) &&
      !/^\s*#{1,3}\s+/.test(lines[i])
    ) {
      paragraphLines.push(lines[i]);
      i++;
    }

    elements.push(
      <p className="response-paragraph" key={`p-${i}`}>
        {renderInlineMarkdown(paragraphLines.join(" "))}
      </p>
    );
  }

  return <div className="formatted-response">{elements}</div>;
}

export default function ChatPanel({
  subjectId,
  onMemoryUpdate,
}: {
  subjectId: string;
  onMemoryUpdate: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "bot",
      text: "Hi! Tell me what you like listening to, and I'll remember it.",
    },
  ]);

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, sending]);

  const handleSend = async () => {
    const text = input.trim();

    if (!text || sending) return;

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        text,
      },
    ]);

    setInput("");
    setSending(true);

    try {
      const reply = await sendMessage(subjectId, text);

      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text: reply,
        },
      ]);

      onMemoryUpdate();
    } catch (err) {
      console.error(err);

      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text: "Couldn't reach the backend. Is the FastAPI server running on :8000?",
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="chat-col">
      <div className="header">
        <span className="dot" />

        <div>
          <h1>AI Listening Assistant</h1>
          <div className="subtitle">
            subject: {subjectId}
          </div>
        </div>
      </div>

      <div className="messages" ref={scrollRef}>
        {messages.map((m, i) => (
          <div
            key={i}
            className={`bubble ${m.role}`}
          >
            {m.role === "bot" ? (
              <FormattedMessage text={m.text} />
            ) : (
              m.text
            )}
          </div>
        ))}

        {sending && (
          <div className="bubble bot loading">
            thinking…
          </div>
        )}
      </div>

      <div className="input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleSend();
            }
          }}
          placeholder="Ask for a recommendation, or tell it a preference…"
          disabled={sending}
        />

        <button
          onClick={handleSend}
          disabled={sending || !input.trim()}
        >
          {sending ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}