"""
question_filters.py
自訂 Django template filter：
  format_content  — 自動偵測程式碼區塊，以 <pre><code> 呈現
  format_code     — 強制整段當作程式碼顯示
"""
import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# ── 程式碼行偵測 ──────────────────────────────────────────────────────────────
_C_KW = re.compile(
    r'\b(int|float|char|void|double|long|short|unsigned|struct|enum|typedef'
    r'|for|while|if|else|switch|case|break|continue|return'
    r'|printf|scanf|malloc|free|sizeof|NULL|true|false)\b'
)
_PY_KW = re.compile(
    r'\b(def|class|import|from|elif|except|with|pass|lambda|yield|async|await'
    r'|print|input|len|range|append|pop|sorted|enumerate|zip|True|False|None)\b'
)
_CODE_PUNCT = re.compile(r'[{};]|->|\+\+|--|[+\-*/%]=|==|!=|<=|>=')
_INDENT     = re.compile(r'^\s{2,}')      # 縮排（2空白以上）
_ASSIGN     = re.compile(r'\w\s*=\s*\w')  # 賦值
_FUNC_CALL  = re.compile(r'\w+\s*\(')     # 函式呼叫

def _code_score(line: str) -> int:
    """
    正分 → 程式碼；負分 → 中文說明文字。
    """
    s = line.strip()
    if not s:
        return 0

    # 中文比例高 → 文字
    zh = sum(1 for c in s if '一' <= c <= '鿿')
    if zh and zh / len(s) > 0.35:
        return -5
    if zh == len(s):
        return -10

    score = 0
    if _C_KW.search(s):      score += 3
    if _PY_KW.search(s):     score += 3
    if _CODE_PUNCT.search(s):score += 2
    if _INDENT.match(line):   score += 2
    if _ASSIGN.search(s):     score += 1
    if _FUNC_CALL.search(s):  score += 1
    if s.endswith((':',)):    score += 2   # Python block start
    if s.endswith((';',)):    score += 2   # C statement
    if s.startswith('#'):     score += 1   # comment / preprocessor
    return score


def _detect_lang(code_text: str) -> str:
    c_score  = len(_C_KW.findall(code_text))
    py_score = len(_PY_KW.findall(code_text))
    if c_score > py_score:
        return 'c'
    elif py_score > c_score:
        return 'python'
    return 'plaintext'


def _lang_from_title(title: str) -> str:
    t = (title or '').strip()
    if t.startswith('C Q.') or t.startswith('C '):
        return 'c'
    if t.startswith('Python Q.') or t.startswith('Python '):
        return 'python'
    return 'auto'


# ── 核心渲染 ──────────────────────────────────────────────────────────────────
def _render(content: str, forced_lang: str = 'auto') -> str:
    if not content:
        return ''

    # ── 1. 支援 Markdown ``` 顯式程式碼圍欄 ────────────────────────────────
    if '```' in content:
        return _render_fences(content, forced_lang)

    # ── 2. 自動偵測 ─────────────────────────────────────────────────────────
    lines = content.split('\n')

    # 建立 (type, line) 序列，type 為 'code' | 'text'
    typed = []
    for line in lines:
        typed.append(('code' if _code_score(line) > 0 else 'text', line))

    # 分組：連續同類型合併
    segments = []   # list of (type, [lines])
    for kind, line in typed:
        if not line.strip():
            # 空行：延續當前段落
            if segments:
                segments[-1][1].append(line)
            continue
        if segments and segments[-1][0] == kind:
            segments[-1][1].append(line)
        else:
            segments.append([kind, [line]])

    # 決定語言
    if forced_lang == 'auto':
        code_blob = '\n'.join(
            '\n'.join(ls) for k, ls in segments if k == 'code'
        )
        lang = _detect_lang(code_blob)
    else:
        lang = forced_lang

    # 渲染
    parts = []
    for kind, seg_lines in segments:
        text = '\n'.join(seg_lines).strip()
        if not text:
            continue
        if kind == 'code':
            parts.append(
                f'<pre class="code-block"><code class="language-{lang}">'
                f'{escape(text)}</code></pre>'
            )
        else:
            for ln in seg_lines:
                ln = ln.strip()
                if ln:
                    parts.append(f'<p class="mb-1">{escape(ln)}</p>')
    return '\n'.join(parts)


def _render_fences(content: str, forced_lang: str = 'auto') -> str:
    """處理 ``` lang \\n code ``` 顯式圍欄。"""
    fence_re = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
    result = []
    last = 0
    for m in fence_re.finditer(content):
        # 圍欄前的文字
        before = content[last:m.start()].strip()
        if before:
            for ln in before.split('\n'):
                ln = ln.strip()
                if ln:
                    result.append(f'<p class="mb-1">{escape(ln)}</p>')
        # 程式碼
        lang = m.group(1).lower() or (forced_lang if forced_lang != 'auto' else 'plaintext')
        code = m.group(2).strip()
        result.append(
            f'<pre class="code-block"><code class="language-{lang}">'
            f'{escape(code)}</code></pre>'
        )
        last = m.end()
    # 圍欄後的文字
    after = content[last:].strip()
    if after:
        for ln in after.split('\n'):
            ln = ln.strip()
            if ln:
                result.append(f'<p class="mb-1">{escape(ln)}</p>')
    return '\n'.join(result)


# ── 公開 filter ───────────────────────────────────────────────────────────────
@register.filter(name='format_content', is_safe=True)
def format_content(content, lang='auto'):
    """
    自動偵測並格式化題目內容。
    用法：{{ question.content|format_content }}
          {{ question.content|format_content:"c" }}
          {{ question.content|format_content:"python" }}
    """
    return mark_safe(_render(str(content or ''), str(lang)))


@register.simple_tag
def format_question(question):
    """
    從題目標題自動判斷語言後格式化。
    用法：{% format_question question %}
    """
    lang = _lang_from_title(question.title)
    return mark_safe(_render(str(question.content or ''), lang))
