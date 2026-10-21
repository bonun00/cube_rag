"""
위키 parse HTML → 순수 텍스트 + 공식 목록. 문서 순서대로 한 번 훑는다.

- <h2> = 케이스 이름 (예: "H Permutation"), <h3> = 그룹 ("Speedsolving Algorithms" / "Optimal Algorithms")
  제목 안의 <span class="mw-editsection">([edit])은 버린다. 공식이 하나도 없는 h2(예: "CPLL Algorithms")는 케이스가 아니다
- 공식 = http(s)://alg.cubing.net 링크. 쿼리 alg = 공식, stage = "PLL" 또는 "HTM 9" 같은 표기 (+는 공백)
- 같은 표(<table>) 안에서 뒤따르는 youtube.com 링크 = 직전 공식의 시연 영상
- 각 공식의 pos = 그 공식이 텍스트에 나타나는 문자 위치 → 청크 구간별 공식 매핑에 쓴다
- NewPP 주석 등 HTML 주석, <style>/<script>, 편집 링크, "[1]" 같은 외부 링크 번호는 텍스트에서 뺀다
"""
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

ALG_HOST = re.compile(r"^https?://alg\.cubing\.net/", re.I)
YOUTUBE = re.compile(r"^https?://(www\.)?(youtube\.com|youtu\.be)/", re.I)
VOID = {"br", "img", "hr", "meta", "link", "input", "wbr", "source", "area", "col"}
BLOCK = {"p", "div", "table", "tr", "li", "ul", "ol", "dl", "dd", "dt", "pre", "blockquote", "h1", "h4", "h5", "h6"}
SKIP_TAGS = {"style", "script"}
SKIP_CLASSES = {"mw-editsection", "external autonumber"}


@dataclass
class Alg:
    case: str | None
    group: str | None
    alg: str
    stage: str | None
    video: str | None
    pos: int                 # 텍스트 내 문자 위치
    order: int               # 문서 내 등장 순서 (0부터)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Alg":
        return cls(**d)


@dataclass
class PageContent:
    text: str
    algs: list[Alg]


class _Walker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.length = 0
        self.skip_depth = 0              # 버리는 요소 안에 있으면 > 0
        self.heading: str | None = None  # 지금 읽는 제목 태그 (h2/h3)
        self.heading_text: list[str] = []
        self.case: str | None = None
        self.group: str | None = None
        self.table_no = 0
        self.table_stack: list[int] = []
        self.algs: list[Alg] = []
        self.alg_table: int | None = None   # 마지막 공식이 있던 표 번호

    # ── 텍스트 출력 ──
    def _emit(self, s: str):
        s = re.sub(r"\s+", " ", s)
        if not s.strip():
            if self.parts and not self.parts[-1].endswith((" ", "\n")):
                self._push(" ")
            return
        if not self.parts or self.parts[-1].endswith("\n"):
            s = s.lstrip()
        self._push(s)

    def _newline(self, n: int = 1):
        if not self.parts:
            return
        tail = "".join(self.parts[-3:])
        have = len(tail) - len(tail.rstrip("\n"))
        if self.parts[-1].endswith(" "):          # 줄 끝 공백 정리
            trimmed = self.parts[-1].rstrip(" ")
            self.length -= len(self.parts[-1]) - len(trimmed)
            self.parts[-1] = trimmed
        if have < n:
            self._push("\n" * (n - have))

    def _push(self, s: str):
        self.parts.append(s)
        self.length += len(s)

    # ── 태그 처리 ──
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.skip_depth:
            if tag not in VOID:
                self.skip_depth += 1
            return
        if tag in SKIP_TAGS or (a.get("class") or "") in SKIP_CLASSES or "mw-editsection" in (a.get("class") or ""):
            if tag not in VOID:
                self.skip_depth = 1
            return

        if tag in ("h2", "h3"):
            self._newline(2)
            self.heading, self.heading_text = tag, []
        elif tag == "table":
            self.table_no += 1
            self.table_stack.append(self.table_no)
            self._newline()
        elif tag == "br":
            self._newline()
        elif tag in BLOCK:
            self._newline()
        elif tag in ("td", "th"):
            self._emit(" ")
        elif tag == "a":
            self._link(a.get("href") or "")

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.skip_depth:
            self._newline()

    def handle_endtag(self, tag):
        if self.skip_depth:
            if tag not in VOID:
                self.skip_depth -= 1
            return
        if tag in ("h2", "h3") and self.heading == tag:
            title = re.sub(r"\s+", " ", "".join(self.heading_text)).strip()
            if tag == "h2":
                self.case, self.group = title, None
            else:
                self.group = title
            self.heading = None
            self.alg_table = None
            self._emit(title)
            self._newline()
        elif tag == "table":
            if self.table_stack:
                self.table_stack.pop()
            self._newline()
        elif tag in BLOCK:
            self._newline()

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.heading:
            self.heading_text.append(data)
            return
        self._emit(data)

    def _link(self, href: str):
        table = self.table_stack[-1] if self.table_stack else None
        if ALG_HOST.match(href):
            q = parse_qs(urlparse(href).query)
            alg = (q.get("alg") or [""])[0].strip()
            if not alg:
                return
            self.algs.append(Alg(
                case=self.case, group=self.group, alg=alg,
                stage=(q.get("stage") or [None])[0], video=None,
                pos=self.length, order=len(self.algs),
            ))
            self.alg_table = table
        elif YOUTUBE.match(href) and self.algs and self.alg_table is not None and self.alg_table == table:
            if self.algs[-1].video is None:
                self.algs[-1].video = href


def extract(html: str) -> PageContent:
    w = _Walker()
    w.feed(html)
    w.close()
    raw = "".join(w.parts)
    text = raw.strip()
    lead = len(raw) - len(raw.lstrip())           # strip()으로 빠진 앞부분만큼 위치를 당긴다
    for a in w.algs:
        a.pos = max(0, a.pos - lead)
    return PageContent(text=text, algs=w.algs)


def extract_algs(html: str) -> list[Alg]:
    return extract(html).algs
