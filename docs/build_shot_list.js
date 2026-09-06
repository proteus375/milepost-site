/* Build docs/shot-list.docx from docs/shot-list.md.
 *
 *   cd docs && npm install docx && node build_shot_list.js
 *
 * THE MARKDOWN IS THE SOURCE. The Word file is a rendering of it, regenerated
 * rather than maintained, because the first version of it was hand-written and
 * had already drifted from the markdown within an hour -- the provenance column
 * went into one and not the other, and nothing said so.
 *
 * This reads only what the markdown contains, so the two cannot disagree. If a
 * heading or a table looks wrong in Word, the fix is in the markdown or in the
 * converter, never in the .docx.
 *
 * Handles: headings, paragraphs with **bold** *italic* `code` ~~strike~~,
 * bullets, blockquotes, fenced code, horizontal rules, and pipe tables (both
 * the headed kind and the two-column key/value kind that has an empty header).
 * A `{# #}`-style multi-line construct is not markdown and is not handled --
 * see the note in base.html about Django's single-line comments.
 */
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, PageOrientation,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, LevelFormat, convertInchesToTwip,
} = require('docx');
const fs = require('fs');

const INK = '1F2A24', MUTED = '5F6B63', ACCENT = '2F6B4F', CLAY = 'A8542A';
const PAGE_W = 12240, MARGIN = 1080;          // US Letter, 0.75in margins
const CONTENT = PAGE_W - MARGIN * 2;

/* Inline markdown: **bold**, *italic*, `code`. Returns TextRun[]. */
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|~~[^~]+~~|\*[^*]+\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith('**')) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith('~~')) out.push(new TextRun({ text: t.slice(2, -2), strike: true, color: MUTED, ...base }));
    else if (t.startsWith('`')) out.push(new TextRun({ text: t.slice(1, -1), font: 'Consolas', size: 19, color: CLAY, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = re.lastIndex;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out.length ? out : [new TextRun({ text: '', ...base })];
}

const body = (text, opts = {}) => new Paragraph({
  children: runs(text), spacing: { after: 160, line: 276 }, ...opts,
});
const bullet = (text) => new Paragraph({
  children: runs(text), numbering: { reference: 'dots', level: 0 },
  spacing: { after: 100, line: 276 },
});
const h1 = (text) => new Paragraph({
  children: [new TextRun({ text, bold: true, size: 30, color: ACCENT })],
  heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 160 },
});
const h2 = (text) => new Paragraph({
  children: [new TextRun({ text, bold: true, size: 24, color: INK })],
  heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 120 },
});
const h3 = (text) => new Paragraph({
  children: [new TextRun({ text, bold: true, size: 22, color: INK })],
  heading: HeadingLevel.HEADING_3, spacing: { before: 240, after: 100 },
});
const rule = () => new Paragraph({
  text: '', spacing: { before: 200, after: 200 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: 'D3D0C5' } },
});
const quote = (text) => new Paragraph({
  children: runs(text, { italics: true, color: MUTED }),
  indent: { left: convertInchesToTwip(0.35) },
  border: { left: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 12 } },
  spacing: { before: 120, after: 200, line: 276 },
});
const code = (lines) => new Paragraph({
  children: lines.flatMap((l, i) => {
    const r = [new TextRun({ text: l, font: 'Consolas', size: 18, color: '3A4A42' })];
    return i < lines.length - 1 ? [...r, new TextRun({ break: 1 })] : r;
  }),
  shading: { type: ShadingType.CLEAR, fill: 'F2F5F1' },
  indent: { left: convertInchesToTwip(0.2), right: convertInchesToTwip(0.2) },
  spacing: { before: 120, after: 220, line: 240 },
});

function table(rowsIn, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cols = widths.map(w => Math.round(w / total * CONTENT));
  cols[cols.length - 1] = CONTENT - cols.slice(0, -1).reduce((a, b) => a + b, 0);
  return new Table({
    columnWidths: cols,
    width: { size: CONTENT, type: WidthType.DXA },
    rows: rowsIn.map((cells, r) => new TableRow({
      tableHeader: opts.header && r === 0,
      children: cells.map((c, i) => new TableCell({
        width: { size: cols[i], type: WidthType.DXA },
        shading: opts.header && r === 0
          ? { type: ShadingType.CLEAR, fill: 'EEF3EA' }
          : (opts.keyValue && i === 0 ? { type: ShadingType.CLEAR, fill: 'F7F9F5' } : undefined),
        margins: { top: 90, bottom: 90, left: 120, right: 120 },
        children: [new Paragraph({
          children: runs(c, opts.header && r === 0 ? { bold: true, color: ACCENT } : {}),
          spacing: { after: 0, line: 260 },
        })],
      })),
    })),
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: 'D3D0C5' },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: 'D3D0C5' },
      left: { style: BorderStyle.SINGLE, size: 2, color: 'D3D0C5' },
      right: { style: BorderStyle.SINGLE, size: 2, color: 'D3D0C5' },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: 'E4E2DA' },
      insideVertical: { style: BorderStyle.SINGLE, size: 2, color: 'E4E2DA' },
    },
  });
}
const gap = () => new Paragraph({ text: '', spacing: { after: 200 } });


/* shot-list.md -> shot-list.docx. The markdown is the source; this never
   invents content, so the two cannot drift. Run it again after any edit. */

const src = fs.readFileSync('shot-list.md', 'utf8').split('\n');
const out = [];
let i = 0;

/* Markdown hard-wraps at ~100 chars; join a paragraph's lines back together. */
const unwrap = (lines) => lines.join(' ').replace(/\s+/g, ' ').trim();
const isTable = (l) => /^\|.*\|\s*$/.test(l);
const cells = (l) => l.replace(/^\|/, '').replace(/\|\s*$/, '').split('|').map(c => c.trim());

while (i < src.length) {
  const line = src[i];

  if (!line.trim()) { i++; continue; }

  if (line.startsWith('# ')) {                      // title -> cover block
    out.push(new Paragraph({
      children: [new TextRun({ text: 'MILEPOST', bold: true, size: 18, color: ACCENT, characterSpacing: 60 })],
      spacing: { after: 60 },
    }));
    out.push(new Paragraph({
      children: [new TextRun({ text: line.slice(2).replace(/^Milepost\s*[—-]\s*/i, '').replace(/^./, c => c.toUpperCase()), bold: true, size: 48, color: INK })],
      spacing: { after: 80 },
    }));
    out.push(new Paragraph({
      children: [new TextRun({ text: 'Eleven slots on the home page — what to buy, where to buy it, and who is in it', size: 22, color: MUTED, italics: true })],
      spacing: { after: 120 },
    }));
    out.push(rule());
    i++; continue;
  }
  if (line.startsWith('### ')) { out.push(h2(line.slice(4).trim())); i++; continue; }
  if (line.startsWith('## '))  { out.push(h1(line.slice(3).trim())); i++; continue; }

  if (line.trim() === '---') { out.push(rule()); i++; continue; }

  if (line.startsWith('```')) {                      // fenced code
    const buf = []; i++;
    while (i < src.length && !src[i].startsWith('```')) buf.push(src[i++]);
    i++; out.push(code(buf)); continue;
  }

  if (line.startsWith('> ')) {                       // blockquote
    const buf = [];
    while (i < src.length && src[i].startsWith('> ')) buf.push(src[i++].slice(2));
    out.push(quote(unwrap(buf))); continue;
  }

  if (line.startsWith('- ')) {                       // bullet, possibly wrapped
    const buf = [src[i++].slice(2)];
    while (i < src.length && /^\s{2,}\S/.test(src[i]) && !src[i].startsWith('- ')) buf.push(src[i++].trim());
    out.push(bullet(unwrap(buf))); continue;
  }

  if (isTable(line)) {
    const rows = [];
    while (i < src.length && isTable(src[i])) rows.push(cells(src[i++]));
    const sep = rows.findIndex(r => r.every(c => /^:?-{3,}:?$/.test(c)));
    const head = sep === 1 ? rows[0] : null;
    const data = rows.filter((_, n) => n !== sep && !(sep === 1 && n === 0));
    const keyValue = head && head.every(c => c === '');
    const n = (head || data[0]).length;
    let widths;
    if (keyValue) widths = [16, 84];
    else if (n === 4) widths = [14, 26, 26, 34];
    else if (n === 3) widths = [16, 30, 54];
    else widths = Array(n).fill(100 / n);
    out.push(table(keyValue || !head ? data : [head, ...data], widths,
                   { header: !!head && !keyValue, keyValue }));
    out.push(gap());
    continue;
  }

  const buf = [src[i++]];                            // paragraph
  while (i < src.length && src[i].trim() && !/^[#>\-|`]|^---$/.test(src[i])) buf.push(src[i++]);
  out.push(body(unwrap(buf)));
}

const doc = new Document({
  creator: 'Milepost', title: 'Milepost — photo shot list',
  description: 'Eleven home page photo slots: brief, sourcing, casting and the current-set audit.',
  numbering: { config: [{ reference: 'dots', levels: [{
    level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 360, hanging: 200 } } },
  }] }] },
  styles: { default: { document: { run: { font: 'Calibri', size: 21, color: INK } } } },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 15840 },
      margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN } } },
    children: out,
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync('shot-list.docx', b); console.log('wrote', b.length, 'bytes from', src.length, 'lines of markdown'); });
