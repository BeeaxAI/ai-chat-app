/**
 * Lightweight Markdown renderer — no external dependencies.
 * Supports: headers, bold, italic, code blocks, inline code, lists,
 * blockquotes, links, images, tables, horizontal rules.
 */
const MarkdownRenderer = (() => {

    function escapeHtml(text) {
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return text.replace(/[&<>"']/g, c => map[c]);
    }

    function renderInline(text) {
        // Code inline (must be first to prevent inner parsing)
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Bold + Italic
        text = text.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
        // Bold
        text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Italic
        text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
        // Links
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
        // Images
        text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;border-radius:8px">');
        return text;
    }

    function render(markdown) {
        if (!markdown) return '';

        const lines = markdown.split('\n');
        const output = [];
        let inCodeBlock = false;
        let codeBlockLang = '';
        let codeLines = [];
        let inList = false;
        let listType = '';

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];

            // Fenced code blocks
            if (line.startsWith('```')) {
                if (!inCodeBlock) {
                    inCodeBlock = true;
                    codeBlockLang = line.slice(3).trim();
                    codeLines = [];
                } else {
                    inCodeBlock = false;
                    const langLabel = codeBlockLang || 'code';
                    const codeId = 'code-' + Math.random().toString(36).slice(2, 8);
                    output.push(
                        `<pre><div class="code-header"><span>${escapeHtml(langLabel)}</span>` +
                        `<button class="copy-btn" onclick="copyCode('${codeId}')">Copy</button></div>` +
                        `<code id="${codeId}">${escapeHtml(codeLines.join('\n'))}</code></pre>`
                    );
                }
                continue;
            }

            if (inCodeBlock) {
                codeLines.push(line);
                continue;
            }

            // Close list if needed
            if (inList && !line.match(/^(\s*[-*+]|\s*\d+\.)\s/)) {
                output.push(listType === 'ul' ? '</ul>' : '</ol>');
                inList = false;
            }

            // Empty line
            if (line.trim() === '') {
                if (inList) {
                    output.push(listType === 'ul' ? '</ul>' : '</ol>');
                    inList = false;
                }
                continue;
            }

            // Horizontal rule
            if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
                output.push('<hr>');
                continue;
            }

            // Headers
            const headerMatch = line.match(/^(#{1,6})\s+(.+)/);
            if (headerMatch) {
                const level = headerMatch[1].length;
                output.push(`<h${level}>${renderInline(headerMatch[2])}</h${level}>`);
                continue;
            }

            // Blockquote
            if (line.startsWith('>')) {
                const quoteContent = line.replace(/^>\s?/, '');
                output.push(`<blockquote>${renderInline(quoteContent)}</blockquote>`);
                continue;
            }

            // Unordered list
            const ulMatch = line.match(/^(\s*)[-*+]\s+(.+)/);
            if (ulMatch) {
                if (!inList || listType !== 'ul') {
                    if (inList) output.push(listType === 'ul' ? '</ul>' : '</ol>');
                    output.push('<ul>');
                    inList = true;
                    listType = 'ul';
                }
                output.push(`<li>${renderInline(ulMatch[2])}</li>`);
                continue;
            }

            // Ordered list
            const olMatch = line.match(/^(\s*)\d+\.\s+(.+)/);
            if (olMatch) {
                if (!inList || listType !== 'ol') {
                    if (inList) output.push(listType === 'ul' ? '</ul>' : '</ol>');
                    output.push('<ol>');
                    inList = true;
                    listType = 'ol';
                }
                output.push(`<li>${renderInline(olMatch[2])}</li>`);
                continue;
            }

            // Table (simple)
            if (line.includes('|') && line.trim().startsWith('|')) {
                // Check if next line is separator
                const nextLine = lines[i + 1] || '';
                if (nextLine.match(/^\|[\s:|-]+\|/)) {
                    // Parse table
                    output.push('<table>');
                    // Header
                    const headers = line.split('|').filter(c => c.trim()).map(c => c.trim());
                    output.push('<thead><tr>' + headers.map(h => `<th>${renderInline(h)}</th>`).join('') + '</tr></thead>');
                    i++; // Skip separator
                    output.push('<tbody>');
                    for (let j = i + 1; j < lines.length; j++) {
                        if (!lines[j].includes('|') || !lines[j].trim().startsWith('|')) break;
                        const cells = lines[j].split('|').filter(c => c.trim()).map(c => c.trim());
                        output.push('<tr>' + cells.map(c => `<td>${renderInline(c)}</td>`).join('') + '</tr>');
                        i = j;
                    }
                    output.push('</tbody></table>');
                    continue;
                }
            }

            // Default: paragraph
            output.push(`<p>${renderInline(line)}</p>`);
        }

        // Close any open list
        if (inList) {
            output.push(listType === 'ul' ? '</ul>' : '</ol>');
        }
        // Close any open code block
        if (inCodeBlock) {
            output.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
        }

        return output.join('\n');
    }

    return { render, escapeHtml };
})();

function copyCode(id) {
    const codeEl = document.getElementById(id);
    if (!codeEl) return;
    navigator.clipboard.writeText(codeEl.textContent).then(() => {
        const btn = codeEl.parentElement.querySelector('.copy-btn');
        if (btn) {
            btn.textContent = 'Copied!';
            setTimeout(() => btn.textContent = 'Copy', 2000);
        }
    });
}
