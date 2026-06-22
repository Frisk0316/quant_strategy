"""Generate a PPTX report for external backtest validation architecture.

This intentionally uses only Python's standard library. The environment used
for this repository does not always have python-pptx installed, and the report
only needs native PowerPoint shapes/text.
"""
from __future__ import annotations

import html
import zipfile
from datetime import datetime, timezone
from pathlib import Path


OUT = Path("docs/backtest_external_validation_report_zh.pptx")
EMU = 914400
SLIDE_W = 12192000
SLIDE_H = 6858000

COLORS = {
    "bg": "F7F8FA",
    "white": "FFFFFF",
    "text": "111827",
    "muted": "4B5563",
    "line": "CBD5E1",
    "navy": "1E3A8A",
    "blue": "2563EB",
    "teal": "0F766E",
    "green": "16A34A",
    "orange": "D97706",
    "red": "DC2626",
    "purple": "7C3AED",
    "slate": "334155",
    "gray1": "E5E7EB",
    "gray2": "F1F5F9",
    "yellow": "F59E0B",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def inch(value: float) -> int:
    return int(value * EMU)


def run_xml(text: str, size: float, color: str, bold: bool) -> str:
    bold_attr = ' b="1"' if bold else ""
    return (
        f'<a:r><a:rPr lang="zh-TW" sz="{int(size * 100)}"{bold_attr}>'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        '<a:latin typeface="Aptos"/><a:ea typeface="Microsoft JhengHei"/>'
        f"</a:rPr><a:t>{esc(text)}</a:t></a:r>"
    )


def text_body(
    text: object,
    *,
    size: float = 12,
    color: str = "111827",
    bold: bool = False,
    align: str = "l",
    valign: str = "top",
    margin: float = 0.05,
) -> str:
    anchor = {"top": "t", "mid": "ctr", "bottom": "b"}.get(valign, "t")
    mar = inch(margin)
    paragraphs = text if isinstance(text, list) else str(text or "").split("\n")
    pxml = "".join(
        f'<a:p><a:pPr algn="{align}"/>{run_xml(str(para), size, color, bold)}</a:p>'
        for para in paragraphs
    )
    return (
        f'<p:txBody><a:bodyPr wrap="square" anchor="{anchor}" '
        f'lIns="{mar}" tIns="{mar}" rIns="{mar}" bIns="{mar}">'
        f"<a:spAutoFit/></a:bodyPr><a:lstStyle/>{pxml}</p:txBody>"
    )


class Slide:
    def __init__(self, title: str | None = None, subtitle: str | None = None):
        self.shapes: list[str] = []
        self._id = 2
        self.bg_color = COLORS["bg"]
        if title:
            self.title(title, subtitle)

    def next_id(self) -> int:
        shape_id = self._id
        self._id += 1
        return shape_id

    def shape(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        text: object = "",
        *,
        fill: str | None = "FFFFFF",
        line: str | None = "CBD5E1",
        color: str = "111827",
        size: float = 12,
        bold: bool = False,
        radius: bool = False,
        align: str = "ctr",
        valign: str = "mid",
        name: str = "rect",
        margin: float = 0.06,
    ) -> int:
        shape_id = self.next_id()
        preset = "roundRect" if radius else name
        fill_xml = (
            "<a:noFill/>"
            if fill is None
            else f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
        )
        line_xml = (
            "<a:ln><a:noFill/></a:ln>"
            if line is None
            else f'<a:ln w="9525"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
        )
        self.shapes.append(
            f"""
        <p:sp>
          <p:nvSpPr><p:cNvPr id="{shape_id}" name="Shape {shape_id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
          <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="{preset}"><a:avLst/></a:prstGeom>{fill_xml}{line_xml}</p:spPr>
          {text_body(text, size=size, color=color, bold=bold, align=align, valign=valign, margin=margin)}
        </p:sp>"""
        )
        return shape_id

    def textbox(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        text: object = "",
        *,
        size: float = 12,
        color: str = "111827",
        bold: bool = False,
        align: str = "l",
        valign: str = "top",
        margin: float = 0.03,
    ) -> int:
        return self.shape(
            x,
            y,
            w,
            h,
            text,
            fill=None,
            line=None,
            color=color,
            size=size,
            bold=bold,
            align=align,
            valign=valign,
            margin=margin,
        )

    def line(self, x: int, y: int, w: int, h: int, color: str = "CBD5E1") -> None:
        self.shape(x, y, w, max(h, 1), fill=color, line=None, name="rect")

    def arrow(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        direction: str = "right",
        color: str = "94A3B8",
    ) -> None:
        name = {
            "right": "rightArrow",
            "down": "downArrow",
            "left": "leftArrow",
            "up": "upArrow",
        }.get(direction, "rightArrow")
        self.shape(x, y, w, h, fill=color, line=None, name=name)

    def pill(self, x: int, y: int, w: int, text: str, fill: str) -> None:
        self.shape(
            x,
            y,
            w,
            inch(0.28),
            text,
            fill=fill,
            line=None,
            color="FFFFFF",
            size=8.5,
            bold=True,
            radius=True,
        )

    def title(self, title: str, subtitle: str | None = None) -> None:
        self.textbox(
            inch(0.55),
            inch(0.28),
            inch(12.2),
            inch(0.45),
            title,
            size=24,
            bold=True,
            color=COLORS["text"],
        )
        if subtitle:
            self.textbox(
                inch(0.57),
                inch(0.76),
                inch(11.8),
                inch(0.28),
                subtitle,
                size=9.5,
                color=COLORS["muted"],
            )
        self.line(inch(0.55), inch(1.08), inch(12.25), inch(0.02), COLORS["line"])

    def xml(self) -> str:
        body = "".join(self.shapes)
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="{self.bg_color}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {body}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def add_card(
    slide: Slide,
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    bullets: list[str],
    accent: str = "blue",
) -> None:
    slide.shape(x, y, w, h, fill=COLORS["white"], line=COLORS["line"], radius=True)
    slide.shape(x, y, inch(0.08), h, fill=COLORS[accent], line=None)
    slide.textbox(
        x + inch(0.18),
        y + inch(0.12),
        w - inch(0.3),
        inch(0.25),
        title,
        size=13,
        bold=True,
        color=COLORS["text"],
    )
    slide.textbox(
        x + inch(0.18),
        y + inch(0.48),
        w - inch(0.3),
        h - inch(0.58),
        "\n".join(f"• {bullet}" for bullet in bullets),
        size=8.8,
        color=COLORS["muted"],
    )


def add_table(
    slide: Slide,
    x: int,
    y: int,
    col_ws: list[int],
    row_h: int,
    rows: list[list[str]],
    header_fill: str = "334155",
) -> None:
    for r, row in enumerate(rows):
        cx = x
        for c, cell in enumerate(row):
            fill = header_fill if r == 0 else (COLORS["white"] if r % 2 else COLORS["gray2"])
            color = COLORS["white"] if r == 0 else COLORS["text"]
            slide.shape(
                cx,
                y + row_h * r,
                col_ws[c],
                row_h,
                cell,
                fill=fill,
                line=COLORS["line"],
                color=color,
                size=7.8 if r else 8.2,
                bold=r == 0 or c == 0,
                align="ctr",
                valign="mid",
                margin=0.035,
            )
            cx += col_ws[c]


def add_source(slide: Slide, text: str) -> None:
    slide.textbox(
        inch(0.55),
        inch(7.06),
        inch(12.2),
        inch(0.25),
        text,
        size=6.4,
        color="64748B",
    )


def build_slides() -> list[Slide]:
    slides: list[Slide] = []

    # ---- 封面 -------------------------------------------------------------
    s = Slide()
    s.shape(0, 0, SLIDE_W, SLIDE_H, fill=COLORS["bg"], line=None)
    s.shape(0, 0, SLIDE_W, inch(1.35), fill=COLORS["navy"], line=None)
    s.textbox(
        inch(0.75),
        inch(0.4),
        inch(11.8),
        inch(0.6),
        "用第三方回測軟體驗證我們的回測結果",
        size=28,
        bold=True,
        color="FFFFFF",
    )
    s.textbox(
        inch(0.78),
        inch(1.55),
        inch(11.8),
        inch(0.5),
        "驗證流程、因子拆解，與 vectorbt / backtrader / Nautilus 的分工",
        size=16,
        color=COLORS["text"],
    )
    s.textbox(
        inch(0.78),
        inch(2.2),
        inch(8.0),
        inch(0.35),
        "Quant Strategy 團隊｜2026-06-23｜內部驗證說明",
        size=11,
        color=COLORS["muted"],
    )
    for i, (label, col) in enumerate(
        [("目的：交叉驗證", "blue"), ("方法：拆成因子", "teal"), ("範圍：驗回測，不是上線", "orange")]
    ):
        s.pill(inch(0.78 + i * 2.55), inch(2.82), inch(2.35), label, COLORS[col])
    add_card(
        s,
        inch(0.78),
        inch(3.5),
        inch(3.75),
        inch(2.55),
        "這份簡報講三件事",
        [
            "為什麼要用外部軟體驗證回測",
            "驗證流程怎麼把結果拆成因子",
            "三套外部工具各自能驗什麼、不能驗什麼",
        ],
        "teal",
    )
    add_card(
        s,
        inch(4.78),
        inch(3.5),
        inch(3.75),
        inch(2.55),
        "一句話結論",
        [
            "MA、EMA、MACD 三個策略的進出場訊號，",
            "已用兩套獨立外部工具重算並完全對齊；",
            "資料庫對齊與撮合保真度是下一步。",
        ],
        "blue",
    )
    add_card(
        s,
        inch(8.78),
        inch(3.5),
        inch(3.75),
        inch(2.55),
        "現階段範圍",
        [
            "目標是確認「回測結果可信、可重現」，",
            "不是宣稱策略可以上線交易。",
            "上線與否另有獨立的審核流程。",
        ],
        "orange",
    )
    slides.append(s)

    # ---- 一頁總覽 ---------------------------------------------------------
    s = Slide("一頁總覽", "一張圖看懂我們在做什麼、為什麼做、目前結論")
    overview = [
        ("在做什麼", "把我們自己跑出來的回測結果，丟給成熟的第三方回測軟體，用同一批資料重算一遍，看兩邊對不對得上。", "blue"),
        ("為什麼做", "自己寫的引擎自己驗，缺乏客觀第二意見。外部軟體獨立、開源、可重跑，等於請第二位裁判覆核。", "teal"),
        ("目前結論", "訊號層面（進出場點）已交叉驗證一致；成交品質、績效穩健度、資料庫對齊持續補齊中。", "green"),
    ]
    for i, (title, body, color) in enumerate(overview):
        x = inch(0.6 + i * 4.05)
        s.shape(x, inch(1.55), inch(3.85), inch(2.85), fill=COLORS["white"], line=COLORS["line"], radius=True)
        s.shape(x, inch(1.55), inch(3.85), inch(0.55), fill=COLORS[color], line=None, radius=True)
        s.textbox(x + inch(0.2), inch(1.62), inch(3.5), inch(0.4), title, size=15, bold=True, color="FFFFFF")
        s.textbox(x + inch(0.25), inch(2.35), inch(3.4), inch(1.9), body, size=12, color=COLORS["text"])
    s.shape(
        inch(0.65),
        inch(4.95),
        inch(12.0),
        inch(0.95),
        "重點：外部驗證不是要證明策略一定賺錢，而是證明「在相同資料、相同參數、相同規則下，計算結果一致、可以重現」。",
        fill="EEF2FF",
        line="A5B4FC",
        color=COLORS["text"],
        size=12,
        bold=True,
        radius=True,
    )
    slides.append(s)

    # ---- 為什麼要外部驗證 -------------------------------------------------
    s = Slide("為什麼要做外部驗證", "用低成本、可重跑、可審計的方式取得客觀第二意見")
    add_card(
        s,
        inch(0.6),
        inch(1.45),
        inch(3.85),
        inch(2.3),
        "問題",
        [
            "我們自己的回測結果可信嗎？",
            "自己寫的引擎、自己驗自己，",
            "缺乏客觀、獨立的第二意見。",
        ],
        "red",
    )
    add_card(
        s,
        inch(4.7),
        inch(1.45),
        inch(3.85),
        inch(2.3),
        "作法",
        [
            "拿成熟的開源回測軟體，",
            "吃同一批資料、同一組參數、同一套規則，",
            "獨立重算一次，再逐項比對差異。",
        ],
        "blue",
    )
    add_card(
        s,
        inch(8.8),
        inch(1.45),
        inch(3.75),
        inch(2.3),
        "為什麼有效",
        [
            "低成本：開源、本地就能跑",
            "可重跑：條件固定，隨時複現",
            "可審計：留下 JSON / CSV 證據",
            "交叉比對：兩套以上對齊才算數",
        ],
        "teal",
    )
    s.shape(
        inch(0.65),
        inch(4.1),
        inch(11.9),
        inch(1.05),
        "一句話定位：外部驗證回答的是「同條件下訊號點與計算結果是否一致、能否重現」，不是「策略會不會賺錢」。兩者是不同問題，不要混用。",
        fill="ECFDF5",
        line="99F6E4",
        color=COLORS["text"],
        size=12.5,
        bold=True,
        radius=True,
    )
    slides.append(s)

    # ---- 工作流程 ---------------------------------------------------------
    s = Slide("驗證工作流程", "從我們的回測產物，到拆因子、外部重算、比對、結論")
    steps = [
        ("1\n我們的回測", "產出回測產物\n價格 / 訊號\n交易 / 權益曲線", "blue"),
        ("2\n拆成因子", "訊號 / 指標\n交易 / 績效\n資料來源", "teal"),
        ("3\n外部重算", "vectorbt\nbacktrader\nNautilus", "orange"),
        ("4\n逐因子比對", "對齊或差異\n標記需修正項", "purple"),
        ("5\n結論與證據", "通過/待補\n留存比對檔案", "green"),
    ]
    for i, (num, body, color) in enumerate(steps):
        x = inch(0.55 + i * 2.55)
        s.shape(x, inch(1.7), inch(0.6), inch(0.6), num, fill=COLORS[color], line=None, color="FFFFFF", size=12, bold=True, radius=True)
        s.shape(x + inch(0.05), inch(2.45), inch(2.1), inch(1.4), body, fill="FFFFFF", line=COLORS[color], color=COLORS["text"], size=10.5, bold=True, radius=True)
        if i < len(steps) - 1:
            s.arrow(x + inch(2.22), inch(2.95), inch(0.3), inch(0.22), "right", COLORS["slate"])
    s.shape(
        inch(0.65),
        inch(4.6),
        inch(11.9),
        inch(1.1),
        "每一步都對應 repo 內可查的檔案：回測產物在 results/，比對結果與差異列在 validation_result.json 與 mismatch CSV，不依賴口頭說明或聊天記錄。",
        fill="F8FAFC",
        line=COLORS["line"],
        color=COLORS["text"],
        size=12,
        bold=True,
        radius=True,
    )
    slides.append(s)

    # ---- 把驗證拆成因子 ---------------------------------------------------
    s = Slide("把驗證拆成幾個因子", "每個因子分開驗：各自驗什麼、目前驗到哪")
    add_table(
        s,
        inch(0.55),
        inch(1.35),
        [inch(2.6), inch(5.4), inch(4.0)],
        inch(0.72),
        [
            ["因子", "驗什麼", "目前狀態"],
            ["訊號（進出場點）", "同一根 K 棒、同方向、同動作是否一致", "已交叉驗證一致（嚴格）"],
            ["指標數據", "均線、EMA、MACD 等數值是否算得相同", "隨訊號一併比對，一致"],
            ["交易（下單→成交）", "訊號變成下單與成交的過程", "參考性質（外部工具≠本專案撮合）"],
            ["績效（報酬/回撤）", "報酬率、最大回撤等績效數字", "參考性質"],
            ["資料來源", "價格結構、合約乘數來源、與資料庫是否同源", "結構與乘數已驗；資料庫對齊待補"],
        ],
    )
    s.shape(
        inch(0.75),
        inch(5.65),
        inch(11.75),
        inch(0.6),
        "判讀：訊號與指標是「嚴格關卡」，必須完全對齊；交易、績效目前是「參考」，差異會記錄供覆核，但不直接判定不通過。",
        fill="FEF3C7",
        line="F59E0B",
        color=COLORS["text"],
        size=10.5,
        bold=True,
        radius=True,
    )
    slides.append(s)

    # ---- 三套工具定位 -----------------------------------------------------
    s = Slide("三套外部工具：一句話定位", "用途不同、保真度不同，互相補位")
    add_card(
        s,
        inch(0.6),
        inch(1.45),
        inch(3.85),
        inch(2.4),
        "vectorbt",
        [
            "最快的「向量化」重算工具。",
            "一次把整段價格丟進去算指標與訊號，",
            "適合大量、快速地比對訊號點。",
        ],
        "blue",
    )
    add_card(
        s,
        inch(4.7),
        inch(1.45),
        inch(3.85),
        inch(2.4),
        "backtrader",
        [
            "「逐根 K 棒」事件驅動工具。",
            "模擬時間一根一根往前走，",
            "比較貼近真實下單與決策流程。",
        ],
        "teal",
    )
    add_card(
        s,
        inch(8.8),
        inch(1.45),
        inch(3.75),
        inch(2.4),
        "Nautilus",
        [
            "目標是「高保真撮合」工具，",
            "含排隊、部分成交、資金費。",
            "目前只做產物重播/匯出，撮合引擎尚未啟用。",
        ],
        "orange",
    )
    s.shape(
        inch(0.65),
        inch(4.2),
        inch(11.9),
        inch(0.95),
        "提醒：本專案自己的回測重播（replay）引擎是「被驗證的對象」，不是外部工具。外部三套工具的角色是覆核它算得對不對。",
        fill="F8FAFC",
        line=COLORS["line"],
        color=COLORS["text"],
        size=12,
        bold=True,
        radius=True,
    )
    slides.append(s)

    # ---- 功能 vs 限制對比 -------------------------------------------------
    s = Slide("工具能驗什麼、不能驗什麼", "每套工具的強項與限制一目了然")
    add_table(
        s,
        inch(0.55),
        inch(1.35),
        [inch(2.3), inch(5.5), inch(4.2)],
        inch(0.85),
        [
            ["工具", "能驗什麼（強項）", "限制 / 不能驗"],
            ["vectorbt", "指標數值、進出場訊號點；速度快、可大量比對", "不驗成交與撮合；費用設 0，績效僅供參考"],
            ["backtrader", "訊號時間點與方向；逐根 K 棒模擬，貼近流程", "用市價單，撮合語意與本專案不同；績效僅供參考"],
            ["Nautilus", "（目標）撮合保真度、排隊、部分成交、資金費", "現況只做重播/匯出，尚未啟用撮合引擎，不能單獨當通過依據"],
            ["本專案 replay", "真實走風控、下單、成交、出場（被驗證對象）", "需要外部工具當第二意見才客觀"],
        ],
    )
    s.shape(
        inch(0.75),
        inch(5.7),
        inch(11.75),
        inch(0.55),
        "結論：vectorbt 與 backtrader 目前負責「訊號」這個最關鍵因子；Nautilus 負責未來的「成交保真度」；本專案 replay 是被覆核的對象。",
        fill="ECFDF5",
        line="99F6E4",
        color=COLORS["text"],
        size=10.5,
        bold=True,
        radius=True,
    )
    slides.append(s)

    # ---- 目前成果 ---------------------------------------------------------
    s = Slide("目前驗證成果", "三個技術策略的進出場訊號，已被兩套外部工具獨立重算並對齊")
    add_table(
        s,
        inch(0.85),
        inch(1.45),
        [inch(2.7), inch(1.7), inch(2.6), inch(2.6), inch(1.9)],
        inch(0.7),
        [
            ["策略", "訊號數", "vectorbt", "backtrader", "比對結果"],
            ["MA（10/200）", "228", "重算一致", "重算一致", "✓ 通過"],
            ["EMA（10/200）", "252", "重算一致", "重算一致", "✓ 通過"],
            ["MACD（12/26/9）", "1558", "重算一致", "重算一致", "✓ 通過"],
        ],
    )
    add_card(
        s,
        inch(0.85),
        inch(4.35),
        inch(5.7),
        inch(1.55),
        "測試條件",
        [
            "標的：Binance BTC 永續、1 小時 K 棒",
            "區間：2024-01-01 ~ 2026-04-30，共 20,400 根",
            "資料覆蓋率 100%（20,400 / 20,400）",
        ],
        "blue",
    )
    add_card(
        s,
        inch(6.75),
        inch(4.35),
        inch(5.8),
        inch(1.55),
        "代表的意義",
        [
            "在相同資料、參數、規則下，",
            "我們的訊號邏輯可以被外部工具完整重現，",
            "沒有任何需要修正的差異。",
        ],
        "green",
    )
    slides.append(s)

    # ---- 還沒驗到的部分（下一步） -----------------------------------------
    s = Slide("還沒驗到的部分，與下一步", "把「回測可信」從訊號層，延伸到執行層與績效層")
    add_card(
        s,
        inch(0.6),
        inch(1.45),
        inch(3.85),
        inch(2.55),
        "資料庫對齊",
        [
            "目前資料庫缺 Binance 1 小時標準 K 棒，",
            "價格與資料庫的逐筆對齊暫時略過。",
            "下一步：補資料後重跑對齊檢查。",
        ],
        "blue",
    )
    add_card(
        s,
        inch(4.7),
        inch(1.45),
        inch(3.85),
        inch(2.55),
        "撮合保真度",
        [
            "Nautilus 完整撮合引擎尚未啟用。",
            "實際成交率、排隊、部分成交",
            "目前還沒驗到。",
        ],
        "orange",
    )
    add_card(
        s,
        inch(8.8),
        inch(1.45),
        inch(3.75),
        inch(2.55),
        "績效穩健度",
        [
            "尚未做樣本外 / walk-forward",
            "等穩健度檢查。",
            "屬於後續工作。",
        ],
        "purple",
    )
    s.shape(
        inch(0.65),
        inch(4.35),
        inch(11.9),
        inch(0.9),
        "這些是「往後延伸」的工作，不影響目前訊號層已驗證的結論。它們是下一步路線圖，不是現在的失敗項。",
        fill="F8FAFC",
        line=COLORS["line"],
        color=COLORS["text"],
        size=12,
        bold=True,
        radius=True,
    )
    slides.append(s)

    # ---- 結論 -------------------------------------------------------------
    s = Slide("結論", "這套驗證能說什麼、不能說什麼，一次講清楚")
    add_card(
        s,
        inch(0.6),
        inch(1.45),
        inch(5.9),
        inch(2.7),
        "能說什麼",
        [
            "三個技術策略的訊號與指標，",
            "已用兩套獨立外部工具交叉驗證一致、",
            "可重現，且留有比對證據。",
            "代表回測的「訊號邏輯」是可信、可覆核的。",
        ],
        "green",
    )
    add_card(
        s,
        inch(6.7),
        inch(1.45),
        inch(5.85),
        inch(2.7),
        "還不能說什麼",
        [
            "尚未驗證實際成交品質與績效穩健度，",
            "資料庫逐筆對齊仍待補。",
            "因此這是「回測可信度」的證據，",
            "不是上線決策依據；上線另有獨立流程。",
        ],
        "orange",
    )
    s.shape(
        inch(0.65),
        inch(4.45),
        inch(11.9),
        inch(0.85),
        "下一步順序：補資料庫對齊 → 提升撮合保真度（Nautilus）→ 補績效穩健度檢查。",
        fill="EEF2FF",
        line="A5B4FC",
        color=COLORS["text"],
        size=13,
        bold=True,
        radius=True,
    )
    slides.append(s)

    # ===================== 技術附錄 =======================================
    s = Slide("附錄 A1：比對範圍與判讀欄位", "技術細節｜哪些是嚴格關卡、哪些是參考")
    add_table(
        s,
        inch(0.55),
        inch(1.35),
        [inch(3.2), inch(4.4), inch(4.3)],
        inch(0.7),
        [
            ["比對範圍", "內容", "判定"],
            ["indicator_values", "指標數值（SMA/EMA/MACD）", "嚴格（隨訊號）"],
            ["signal_logic", "訊號時間點 / 方向 / 動作", "嚴格關卡"],
            ["trade_execution", "下單與成交過程", "參考（advisory）"],
            ["pnl_semantics", "PnL / 權益計算語意", "參考（advisory）"],
            ["metrics", "報酬、回撤等績效指標", "參考（advisory）"],
        ],
    )
    s.shape(
        inch(0.75),
        inch(5.6),
        inch(11.75),
        inch(0.62),
        "Gate 欄位：signal_logic_gate 需至少一個 vectorbt/backtrader 的 signal_logic PASS 且 actionable_mismatch_count = 0；portable_validation_gate 為是否具備可攜 reference path。source_data_validation 檢查必要產物、OHLCV 結構、ct_val 來源與選用的 DB parity。",
        fill="F1F5F9",
        line=COLORS["line"],
        color=COLORS["text"],
        size=8.8,
        bold=False,
        radius=True,
    )
    add_source(s, "Source: backtesting/differential_validation.py, docs/ai_collaboration.md")
    slides.append(s)

    s = Slide("附錄 A2：vectorbt 技術細節", "向量化 reference；訊號嚴格、績效參考")
    flow = [
        ("price_series.csv\nclose 序列", "blue"),
        ("重算 SMA/EMA/MACD\n指標", "teal"),
        ("crossover\n買/賣訊號", "orange"),
        ("Portfolio.from_signals\nentries / exits", "purple"),
        ("reference_* 產物\nmetrics advisory", "green"),
    ]
    for i, (text, color) in enumerate(flow):
        x = inch(0.62 + i * 2.42)
        s.shape(x, inch(1.45), inch(1.95), inch(0.85), text, fill="FFFFFF", line=COLORS[color], color=COLORS["text"], size=8.8, bold=True, radius=True)
        if i < 4:
            s.arrow(x + inch(1.98), inch(1.78), inch(0.28), inch(0.18), "right", COLORS["slate"])
    add_card(
        s,
        inch(0.65),
        inch(2.8),
        inch(5.85),
        inch(2.3),
        "核心參數與輸入",
        [
            "strategy params：fast/slow window、MACD 12/26/9 預設",
            "init_cash = bundle.initial_equity；fees = 0",
            "freq 依 bar 對應年化頻率",
            "required artifacts：result.json、price_series.csv、signals.csv",
        ],
        "blue",
    )
    add_card(
        s,
        inch(6.7),
        inch(2.8),
        inch(5.85),
        inch(2.3),
        "訊號邏輯與角色",
        [
            "warmup 後：prev_fast≤prev_slow 且 cur_fast>cur_slow → buy",
            "prev_fast≥prev_slow 且 cur_fast<cur_slow → sell",
            "reference_role = reference_signals_only（technical）",
            "strict scope = signal_logic；PnL/equity/metrics 為 advisory",
        ],
        "teal",
    )
    add_source(s, "Source: VectorBTReferenceAdapter, _technical_reference_signals()")
    slides.append(s)

    s = Slide("附錄 A3：backtrader 技術細節", "事件驅動 reference；訊號時序嚴格、下單/績效參考")
    flow = [
        ("price_series.csv\nOHLCV → PandasData", "blue"),
        ("bt.Cerebro\nsetcash(initial_equity)", "teal"),
        ("TechnicalStrategy.next()\n逐根更新指標", "orange"),
        ("market orders\nnotify_order / trade", "purple"),
        ("signals / trades / equity\n比對 scopes", "green"),
    ]
    for i, (text, color) in enumerate(flow):
        x = inch(0.62 + i * 2.42)
        s.shape(x, inch(1.42), inch(1.95), inch(0.92), text, fill="FFFFFF", line=COLORS[color], color=COLORS["text"], size=8.4, bold=True, radius=True)
        if i < 4:
            s.arrow(x + inch(1.98), inch(1.78), inch(0.28), inch(0.18), "right", COLORS["slate"])
    add_card(
        s,
        inch(0.65),
        inch(2.85),
        inch(5.85),
        inch(2.3),
        "核心設定與參數",
        [
            "dependency：backtrader；bt.Cerebro(stdstats=False)",
            "broker.setcash(bundle.initial_equity)",
            "PandasData：open/high/low/close/volume",
            "MA 20/50、EMA 20/50、MACD 12/26/9；warmup = slow（或 slow+signal）",
        ],
        "teal",
    )
    add_card(
        s,
        inch(6.7),
        inch(2.85),
        inch(5.85),
        inch(2.3),
        "角色與 Gate 意義",
        [
            "reference_role = reference_signals_only（technical）",
            "strict scope = signal_logic",
            "order_semantics = backtrader market orders",
            "PnL / equity / metrics 仍為 advisory",
        ],
        "orange",
    )
    add_source(s, "Source: BacktraderReferenceAdapter, _run_backtrader_technical_reference()")
    slides.append(s)

    s = Slide("附錄 A4：Nautilus 現況與目標", "目前只做產物重播/匯出；完整撮合是未來路徑")
    s.shape(inch(0.7), inch(1.5), inch(5.85), inch(2.1), fill="FFFFFF", line=COLORS["orange"], radius=True)
    s.textbox(inch(0.95), inch(1.7), inch(5.4), inch(0.3), "目前 v1（advisory）", size=13, bold=True, color=COLORS["orange"])
    s.textbox(
        inch(0.95),
        inch(2.15),
        inch(5.35),
        inch(1.3),
        "artifact signals → 模擬 long/flat trades → reference_nautilus_*.csv + export_manifest.json。\nengine_execution = not_run；reference_role = advisory；不能讓 portable gate 單獨通過。",
        size=10,
        color=COLORS["text"],
    )
    s.shape(inch(6.75), inch(1.5), inch(5.8), inch(2.1), fill="FFFFFF", line=COLORS["teal"], radius=True)
    s.textbox(inch(7.0), inch(1.7), inch(5.3), inch(0.3), "目標高保真路徑", size=13, bold=True, color=COLORS["teal"])
    s.textbox(
        inch(7.0),
        inch(2.15),
        inch(5.3),
        inch(1.3),
        "若恢復 order-book 資料：建立 Nautilus catalog + L2/L3 order book + order/fill events + funding cashflows，對接 venue / 撮合引擎，達成可獨立驗證的成交保真度。",
        size=10,
        color=COLORS["text"],
    )
    s.arrow(inch(6.25), inch(2.4), inch(0.5), inch(0.3), "right", COLORS["slate"])
    s.shape(
        inch(0.7),
        inch(3.95),
        inch(11.85),
        inch(1.25),
        "現況限制：standalone L2 runner 已停用，目前不維護 order-book 資料；排隊優先權與部分成交留待下一階段。Nautilus 在本輪驗證中不作為通過依據。",
        fill="FEF3C7",
        line="F59E0B",
        color=COLORS["text"],
        size=11,
        bold=True,
        radius=True,
    )
    add_source(s, "Source: NautilusReferenceAdapter, backtesting/nautilus_backtest.py, docs/backtest_live_parity_plan.md")
    slides.append(s)

    s = Slide("附錄 A5：實測數據", "2026-06-22 訊號到下單 + 2026-06-23 長區間引擎一致性")
    add_table(
        s,
        inch(0.55),
        inch(1.3),
        [inch(1.7), inch(1.7), inch(1.6), inch(1.6), inch(1.6), inch(1.6), inch(1.85)],
        inch(0.6),
        [
            ["策略", "參數", "訊號", "下單", "成交", "拒絕", "主要拒絕原因"],
            ["MA", "10/200", "117", "5", "31", "112", "fat_finger"],
            ["EMA", "10/200", "127", "4", "22", "123", "fat_finger"],
            ["MACD", "12/26/9", "779", "779", "15", "0", "—"],
        ],
    )
    add_card(
        s,
        inch(0.6),
        inch(3.55),
        inch(5.95),
        inch(1.75),
        "250/1.0 風控重跑（含 bounded reduce-only bypass）",
        [
            "MA 117/117/30/0、EMA 126/126/10/0、MACD 779/779/13/0",
            "MA/EMA 的出場拒絕清零（原因：出場套用進場 fat-finger 上限）",
            "剩餘低成交率來自 realistic 成交模型，非訊號錯誤",
        ],
        "blue",
    )
    add_card(
        s,
        inch(6.75),
        inch(3.55),
        inch(5.8),
        inch(1.75),
        "Dual Output（MACD 全期，診斷用）",
        [
            "strategy_fill：1558 訊號全成交，報酬 0.39%，回撤 -6.99%",
            "realistic：779 訊號僅 3 成交，報酬 0.66%，回撤 -2.52%",
            "兩者皆為診斷比較，不是績效排名或上線證據",
        ],
        "purple",
    )
    s.shape(
        inch(0.6),
        inch(5.5),
        inch(11.95),
        inch(0.55),
        "Claude 2026-06-23 長區間（strategy_fill）：MA/EMA/MACD 在 vectorbt 與 backtrader 的 signal_logic 皆 PASS、actionable mismatch = 0、portable gate = true；DB parity = SKIP、admissibility = advisory_only。ct_val（BTC-USDT-SWAP）來源 DB、值 1.0、venue binance、authoritative。",
        fill="F1F5F9",
        line=COLORS["line"],
        color=COLORS["text"],
        size=8.4,
        bold=False,
        radius=True,
    )
    add_source(s, "Source: results/validation_lab_signal_order_check_20260622*.json, ..._dual_fullperiod_execution_comparison.json, claude_engine_consistency_20260623/validation_result.json")
    slides.append(s)

    s = Slide("附錄 A6：操作入口與證據位置", "報告對應到 repo 內可查的 CLI、API、UI 與檔案")
    add_card(
        s,
        inch(0.6),
        inch(1.45),
        inch(3.85),
        inch(2.3),
        "CLI",
        [
            "python scripts/run_differential_validation.py --run-id <id>",
            "--strategy <name> --fixture-run-id <id>",
            "--engines vectorbt,backtrader,nautilus",
            "--validation-id <stable_id>",
        ],
        "blue",
    )
    add_card(
        s,
        inch(4.7),
        inch(1.45),
        inch(3.85),
        inch(2.3),
        "API",
        [
            "POST /strategy-validation/run",
            "GET /strategy-validation/contracts",
            "POST /{run_id}/differential-validation/run",
            "GET artifact endpoints（mismatch/reference 檔）",
        ],
        "teal",
    )
    add_card(
        s,
        inch(8.8),
        inch(1.45),
        inch(3.75),
        inch(2.3),
        "UI",
        [
            "Validation view 顯示各引擎角色",
            "訊號嚴格；指標/交易/績效標示 advisory",
            "覆核者提示 PASS 的適用範圍",
            "可預覽 mismatches_*.csv",
        ],
        "orange",
    )
    s.shape(inch(0.65), inch(4.1), inch(11.9), inch(1.15), fill="FFFFFF", line=COLORS["line"], radius=True)
    s.textbox(inch(0.9), inch(4.25), inch(11.4), inch(0.3), "證據檔案位置", size=13, bold=True, color=COLORS["text"])
    s.textbox(
        inch(0.9),
        inch(4.7),
        inch(11.3),
        inch(0.45),
        "results/validation_lab_*（各策略 run）、validation/.../validation_result.json、mismatches_*.csv、results/engine_consistency_fixture/fixture_manifest.json（離線 smoke）。",
        size=10,
        color=COLORS["muted"],
    )
    add_source(s, "Source: scripts/run_differential_validation.py, routes_backtest.py, frontend/view-validation.js, results/")
    slides.append(s)

    return slides


def content_types(slide_count: int) -> str:
    overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  {overrides}
</Types>"""


def root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def presentation_xml(slide_count: int) -> str:
    slide_ids = "\n".join(
        f'<p:sldId id="{255 + i}" r:id="rId{1 + i}"/>' for i in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:defaultTextStyle/>
</p:presentation>"""


def presentation_rels(slide_count: int) -> str:
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]
    rels.extend(
        f'<Relationship Id="rId{1 + i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, slide_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    )


def slide_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""


def slide_master() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>"""


def slide_master_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""


def slide_layout() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def slide_layout_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""


def theme() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Codex Report Theme">
  <a:themeElements>
    <a:clrScheme name="Codex"><a:dk1><a:srgbClr val="111827"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="334155"/></a:dk2><a:lt2><a:srgbClr val="F7F8FA"/></a:lt2><a:accent1><a:srgbClr val="2563EB"/></a:accent1><a:accent2><a:srgbClr val="0F766E"/></a:accent2><a:accent3><a:srgbClr val="D97706"/></a:accent3><a:accent4><a:srgbClr val="7C3AED"/></a:accent4><a:accent5><a:srgbClr val="16A34A"/></a:accent5><a:accent6><a:srgbClr val="DC2626"/></a:accent6><a:hlink><a:srgbClr val="2563EB"/></a:hlink><a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink></a:clrScheme>
    <a:fontScheme name="Codex"><a:majorFont><a:latin typeface="Aptos Display"/><a:ea typeface="Microsoft JhengHei"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/><a:ea typeface="Microsoft JhengHei"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="Codex"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
  </a:themeElements>
</a:theme>"""


def app_props(slide_count: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Codex OpenXML Generator</Application><PresentationFormat>On-screen Show (16:9)</PresentationFormat><Slides>{slide_count}</Slides><Notes>0</Notes><HiddenSlides>0</HiddenSlides><ScaleCrop>false</ScaleCrop><Company>quant_strategy</Company><LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged><AppVersion>16.0000</AppVersion></Properties>"""


def core_props() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>外接回測系統與驗證架構統整</dc:title><dc:creator>Codex</dc:creator><cp:lastModifiedBy>Codex</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>"""


def write_pptx(out: Path = OUT) -> Path:
    slides = build_slides()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        slide_count = len(slides)
        zf.writestr("[Content_Types].xml", content_types(slide_count))
        zf.writestr("_rels/.rels", root_rels())
        zf.writestr("docProps/app.xml", app_props(slide_count))
        zf.writestr("docProps/core.xml", core_props())
        zf.writestr("ppt/presentation.xml", presentation_xml(slide_count))
        zf.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(slide_count))
        zf.writestr("ppt/slideMasters/slideMaster1.xml", slide_master())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels())
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels())
        zf.writestr("ppt/theme/theme1.xml", theme())
        for idx, slide in enumerate(slides, start=1):
            zf.writestr(f"ppt/slides/slide{idx}.xml", slide.xml())
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", slide_rels())
    return out


if __name__ == "__main__":
    path = write_pptx()
    print(f"Wrote {path} ({path.stat().st_size} bytes)")
