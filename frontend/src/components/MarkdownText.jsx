/**
 * Lightweight markdown renderer — no external dependencies.
 * Handles: bold, italic, inline code, code blocks, bullet lists,
 *          numbered lists, headings, horizontal rules, and line breaks.
 */

function parseInline(text) {
  const parts = [];
  const re = /(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[2]) parts.push(<strong key={m.index}><em>{m[2]}</em></strong>);
    else if (m[3]) parts.push(<strong key={m.index}>{m[3]}</strong>);
    else if (m[4]) parts.push(<em key={m.index}>{m[4]}</em>);
    else if (m[5]) parts.push(<code key={m.index} className="md-code">{m[5]}</code>);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export default function MarkdownText({ children }) {
  if (!children) return null;

  const lines = children.split("\n");
  const elements = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      elements.push(
        <pre key={i} className="md-pre">
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      i++;
      continue;
    }

    // Horizontal rule
    if (/^[-*_]{3,}$/.test(line.trim())) {
      elements.push(<hr key={i} className="md-hr" />);
      i++;
      continue;
    }

    // Headings
    const heading = line.match(/^(#{1,3})\s+(.+)/);
    if (heading) {
      const level = heading[1].length;
      const Tag = `h${level}`;
      elements.push(<Tag key={i} className={`md-h${level}`}>{parseInline(heading[2])}</Tag>);
      i++;
      continue;
    }

    // Bullet list — collect consecutive items
    if (/^[-*+]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*+]\s+/.test(lines[i])) {
        items.push(<li key={i}>{parseInline(lines[i].replace(/^[-*+]\s+/, ""))}</li>);
        i++;
      }
      elements.push(<ul key={`ul-${i}`} className="md-ul">{items}</ul>);
      continue;
    }

    // Numbered list — collect consecutive items
    if (/^\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(<li key={i}>{parseInline(lines[i].replace(/^\d+\.\s+/, ""))}</li>);
        i++;
      }
      elements.push(<ol key={`ol-${i}`} className="md-ol">{items}</ol>);
      continue;
    }

    // Blank line — skip
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Paragraph
    elements.push(<p key={i} className="md-p">{parseInline(line)}</p>);
    i++;
  }

  return <div className="md">{elements}</div>;
}
