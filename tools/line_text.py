# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Turn a mail.message HTML body into LINE plain text.

Pure Python (no Odoo import) so it can be unit-tested on its own.

LINE text messages cannot carry markup, and a bare tag-strip loses what
the reader needs: the address of every link (``<a href="URL">name</a>``
became just "name"), the boundaries between table cells, and line breaks.
Rules:

- ``<br>`` and the end of a block (p, div, li, h1-h6, blockquote, ...) are
  line breaks; a list item starts with "• " ("– " when nested, "1. " in
  an ordered list).
- A link keeps its address: an absolute http(s) link whose text is not
  already the address is written "text URL" (spaces around the URL so
  LINE's auto-linking stops at the URL). Relative links and Odoo mention
  links (internal back-office pages a customer cannot open) keep only
  their text.
- A table becomes one line per row, cells joined by "｜"; body rows start
  with "・". Addresses of links inside a row follow on their own lines.
- Entities are unescaped exactly once; script and style content is dropped.
"""

from html.parser import HTMLParser
from urllib.parse import urlsplit

# LINE text message limit is 5,000 characters.
LINE_TEXT_LIMIT = 5000

_BLOCK_TAGS = frozenset((
    'p', 'div', 'li', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'section', 'article', 'pre', 'header', 'footer',
))
_SKIP_TAGS = frozenset(('script', 'style', 'template'))
_CELL_SEP = '｜'
_ROW_BULLET = '・'


def _comparable_url(value):
    value = (value or '').strip().lower()
    for prefix in ('https://', 'http://'):
        if value.startswith(prefix):
            value = value[len(prefix):]
    if value.startswith('www.'):
        value = value[4:]
    return value.rstrip('/')


def _external_url(href, attrs):
    """The address to show for a link, or None to show only its text."""
    href = (href or '').strip()
    if urlsplit(href).scheme.lower() not in ('http', 'https'):
        return None
    classes = (attrs.get('class') or '').split()
    if 'o_mail_redirect' in classes or attrs.get('data-oe-model'):
        return None  # @mention / record link: back-office page
    return href


class _LineTextParser(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._skip = 0
        self._links = []        # stack of (url, label parts)
        self._rows = None       # inside a table: finished rows
        self._row = None        # cells of the current row
        self._row_header = False
        self._row_urls = None
        self._cell = None       # parts of the current cell
        self._eat_space = False  # drop leading spaces after an inserted URL
        self._lists = []        # stack of [kind, item counter]

    # -- where text goes ---------------------------------------------------
    def _target(self):
        if self._links:
            return self._links[-1][1]
        if self._cell is not None:
            return self._cell
        return self.out

    def _write(self, text):
        if not text:
            return
        if self._eat_space:
            text = text.lstrip(' ')
            if not text:
                return
            self._eat_space = False
        self._target().append(text)

    def _break(self):
        """Line break, or a space inside a table cell (rows are one line)."""
        if self._in_cell():
            self._write(' ')
        else:
            self._write('\n')

    def _in_cell(self):
        return self._cell is not None

    def _at_line_start(self):
        for part in reversed(self._target()):
            if part:
                return part.endswith('\n')
        return True

    def _item_marker(self):
        """"• " (nested: "– "), or "1. " in an ordered list."""
        if not self._lists:
            return '• '
        current = self._lists[-1]
        current[1] += 1
        if current[0] == 'ol':
            return '%d. ' % current[1]
        return '• ' if len(self._lists) == 1 else '– '

    # -- parser callbacks --------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
            return
        if self._skip:
            return
        attrs = dict(attrs)
        if tag == 'br':
            self._break()
        elif tag == 'li':
            if self._in_cell():
                self._write(' ')
            elif not self._at_line_start():
                self._write('\n')
            self._write(self._item_marker())
        elif tag in ('ul', 'ol'):
            self._lists.append([tag, 0])
        elif tag == 'a':
            self._links.append((_external_url(attrs.get('href'), attrs), []))
        elif tag == 'table':
            self._write('\n')
            self._rows = []
        elif tag == 'tr' and self._rows is not None:
            self._row, self._row_header, self._row_urls = [], True, []
        elif tag in ('td', 'th') and self._row is not None:
            self._cell = []
            if tag == 'td':
                self._row_header = False

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in ('br',):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag == 'a' and self._links:
            url, parts = self._links.pop()
            label = ''.join(parts)
            self._write(label)
            if url and _comparable_url(url) not in _comparable_url(label):
                if self._in_cell():
                    if url not in self._row_urls:
                        self._row_urls.append(url)
                else:
                    last = ''.join(self._target()[-1:])
                    sep = '' if not last or last[-1].isspace() else ' '
                    self._write('%s%s ' % (sep, url))
                    self._eat_space = True
        elif tag in ('td', 'th') and self._cell is not None:
            self._row.append(' '.join(''.join(self._cell).split()))
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            self._finish_row()
        elif tag == 'table' and self._rows is not None:
            if self._row is not None:
                self._finish_row()
            self._rows = None
            self._write('\n')
        elif tag in ('ul', 'ol') and self._lists:
            self._lists.pop()
            if not self._in_cell() and not self._at_line_start():
                self._write('\n')
        elif tag == 'li' and not self._in_cell() and self._at_line_start():
            pass  # list structure: one line per item, no blank lines
        elif tag in _BLOCK_TAGS:
            self._break()

    def handle_data(self, data):
        if not self._skip:
            self._write(data)

    # -- tables ------------------------------------------------------------
    def _finish_row(self):
        if self._cell is not None:
            self._row.append(' '.join(''.join(self._cell).split()))
            self._cell = None
        cells, urls, header = self._row, self._row_urls, self._row_header
        self._row = self._row_urls = None
        if not any(cells):
            return
        line = _CELL_SEP.join(cells)
        if not self._at_line_start():
            self.out.append('\n')
        self.out.append('%s%s\n' % ('' if header else _ROW_BULLET, line))
        for url in urls:
            self.out.append('%s\n' % url)


def html_to_line_text(body):
    """Plain text for a LINE text message from an HTML body (str or Markup)."""
    if not body:
        return ''
    parser = _LineTextParser()
    parser.feed(str(body))
    parser.close()
    # a link left open by broken HTML still shows its text
    while parser._links:
        parser.handle_endtag('a')
    text = ''.join(parser.out)
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    return text.strip()


def _utf16_len(text):
    return len(text.encode('utf-16-le')) // 2


def split_line_text(text, limit=LINE_TEXT_LIMIT):
    """Split text into chunks LINE accepts (at most ``limit`` UTF-16 units),
    breaking at line ends when possible, otherwise inside the line."""
    if not text:
        return []
    chunks, current = [], ''
    for line in text.split('\n'):
        candidate = line if not current else current + '\n' + line
        if _utf16_len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ''
        while _utf16_len(line) > limit:
            cut = limit
            while _utf16_len(line[:cut]) > limit:
                cut -= 1
            chunks.append(line[:cut])
            line = line[cut:]
        current = line
    if current:
        chunks.append(current)
    return [chunk.strip() for chunk in chunks if chunk.strip()]
