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

    s = Slide()
    s.shape(0, 0, SLIDE_W, SLIDE_H, fill=COLORS["bg"], line=None)
    s.shape(0, 0, SLIDE_W, inch(1.25), fill=COLORS["navy"], line=None)
    s.textbox(
        inch(0.75),
        inch(0.38),
        inch(11.5),
        inch(0.55),
        "外接回測系統與驗證架構統整",
        size=27,
        bold=True,
        color="FFFFFF",
    )
    s.textbox(
        inch(0.78),
        inch(1.45),
        inch(11.7),
        inch(0.55),
        "vectorbt / backtrader / Nautilus：架構、參數、回測邏輯與目前驗證 Gate",
        size=17,
        color=COLORS["text"],
    )
    s.textbox(
        inch(0.78),
        inch(2.18),
        inch(7.1),
        inch(0.35),
        "Quant Strategy Repo｜2026-06-11｜報告用簡報",
        size=11,
        color=COLORS["muted"],
    )
    for i, (label, col) in enumerate(
        [("Signal Logic Gate", "blue"), ("Advisory PnL", "orange"), ("ct_val / WF / CPCV", "teal")]
    ):
        s.pill(inch(0.78 + i * 2.15), inch(2.8), inch(1.82), label, COLORS[col])
    add_card(
        s,
        inch(0.78),
        inch(3.45),
        inch(3.8),
        inch(2.1),
        "本簡報回答三件事",
        [
            "三套外接回測系統目前在 repo 中扮演的角色",
            "各引擎吃哪些 artifact / 參數，如何產生信號、交易與 equity",
            "目前驗證流程如何做 gate，以及哪些結果只能 advisory",
        ],
        "teal",
    )
    add_card(
        s,
        inch(4.85),
        inch(3.45),
        inch(3.8),
        inch(2.1),
        "最重要的界線",
        [
            "technical 指標策略只把 signal logic 當 strict gate",
            "PnL / trade / metrics mismatch 目前可被審查引用，但不是自動 gate fail",
            "Nautilus v1 是匯出/重播 evidence，尚未跑完整 matching engine",
        ],
        "orange",
    )
    add_card(
        s,
        inch(8.92),
        inch(3.45),
        inch(3.25),
        inch(2.1),
        "部署聲明",
        [
            "這份報告不宣稱任何策略可 live",
            "demo/shadow/live 仍需通過協作文件列出的所有 gate",
            "使用者明確批准前不得升級風險模式",
        ],
        "red",
    )
    slides.append(s)

    s = Slide("一頁結論", "目前外部 reference engine 的分工與可用性")
    add_card(
        s,
        inch(0.6),
        inch(1.35),
        inch(3.75),
        inch(2.0),
        "vectorbt",
        [
            "最快速的 vectorized reference / scanner",
            "technical 策略可重算 SMA/EMA/MACD crossover signal",
            "使用 Portfolio.from_signals 產生 equity，但 PnL semantics advisory",
        ],
        "blue",
    )
    add_card(
        s,
        inch(4.78),
        inch(1.35),
        inch(3.75),
        inch(2.0),
        "backtrader",
        [
            "事件驅動 reference path",
            "TechnicalStrategy.next() 逐 bar 更新指標 state",
            "Market order / broker equity 可供對照，但 v1 不作嚴格 PnL gate",
        ],
        "teal",
    )
    add_card(
        s,
        inch(8.96),
        inch(1.35),
        inch(3.75),
        inch(2.0),
        "Nautilus",
        [
            "高保真 L2 / queue-aware 目標框架",
            "目前 differential validation 只做 artifact replay/export",
            "engine_execution = not_run，無法通過 independent portable gate",
        ],
        "orange",
    )
    s.shape(inch(0.65), inch(3.85), inch(12.0), inch(1.55), fill="ECFDF5", line="99F6E4", radius=True)
    s.textbox(inch(0.85), inch(4.03), inch(11.6), inch(0.34), "目前 Gate 判讀", size=14, bold=True, color=COLORS["teal"])
    s.textbox(
        inch(0.85),
        inch(4.45),
        inch(11.35),
        inch(0.68),
        "technical_indicator 策略（ma_crossover / ema_crossover / macd_crossover）需要至少一個 vectorbt 或 backtrader 的 signal_logic PASS，且 actionable_mismatch_count = 0。其他策略與 Nautilus v1 目前多為 advisory replay/export，不能單獨作 promotion evidence。",
        size=10.5,
        color=COLORS["text"],
    )
    add_source(s, "Source: backtesting/differential_validation.py, docs/ai_collaboration.md")
    slides.append(s)

    s = Slide("三引擎定位矩陣", "相同 artifact bundle，三種 reference 行為")
    add_table(
        s,
        inch(0.55),
        inch(1.35),
        [inch(1.25), inch(2.15), inch(2.5), inch(2.55), inch(3.3)],
        inch(0.78),
        [
            ["引擎", "目前 role", "主要 mode", "Gate 影響", "主要限制"],
            [
                "vectorbt",
                "reference_signals_only\n(technical)",
                "technical_indicator_recompute\nartifact_signal_replay",
                "technical signal_logic 可 PASS\n非 technical advisory",
                "費用設 0；PnL/equity/metrics 不作嚴格 gate",
            ],
            [
                "backtrader",
                "reference_signals_only\n(technical)",
                "technical_indicator_recompute\nartifact_signal_replay",
                "technical signal_logic 可 PASS\norder/PnL advisory",
                "market order semantics 與專案撮合模型不等價",
            ],
            [
                "Nautilus",
                "advisory",
                "nautilus_artifact_replay_export",
                "不能讓 portable gate 通過",
                "v1 不跑 Nautilus matching engine；需 L2/L3 catalog",
            ],
        ],
    )
    s.shape(inch(0.8), inch(5.0), inch(11.45), inch(0.95), fill="FFF7ED", line="FDBA74", radius=True)
    s.textbox(
        inch(1.02),
        inch(5.12),
        inch(10.95),
        inch(0.58),
        "判讀規則：strict signal logic 僅涵蓋 indicator/signal 方向與時序；trade_execution、pnl_semantics、metrics 為 advisory scope，但 reviewer 仍可用非零 mismatch count 暫緩或拒絕 promotion ADR。",
        size=10.3,
        color=COLORS["text"],
    )
    add_source(s, "Source: REFERENCE_VALIDATION_CONTRACTS, compare_reference() scoped summaries")
    slides.append(s)

    s = Slide("外部差異驗證架構", "從既有回測 artifact 到 reference output 與 mismatch tables")
    y0 = inch(1.55)
    boxes = [
        (inch(0.72), y0, inch(2.25), inch(1.0), "Backtest Artifact\nBundle\nresult / price / signals\ntrades / fills / equity", "blue"),
        (inch(3.45), y0, inch(2.2), inch(1.0), "Contract\nSelection\nstrategy class\nrequired artifacts\nengine roles", "teal"),
        (inch(6.12), y0, inch(2.35), inch(1.0), "Reference\nAdapters\nvectorbt\nbacktrader\nnautilus", "orange"),
        (inch(8.92), y0, inch(2.55), inch(1.0), "Normalized\nReference Outputs\nsignals / trades\nequity / metrics", "purple"),
    ]
    for x, y, w, h, text, accent in boxes:
        s.shape(x, y, w, h, text, fill="FFFFFF", line=COLORS[accent], color=COLORS["text"], size=10.2, bold=True, radius=True)
    for x in [inch(2.98), inch(5.68), inch(8.48)]:
        s.arrow(x, y0 + inch(0.36), inch(0.32), inch(0.22), "right", COLORS["slate"])
    s.shape(inch(4.1), inch(3.15), inch(2.45), inch(0.82), "Comparator\nindicator / signal / trade / PnL / metrics", fill="EEF2FF", line="A5B4FC", size=10, bold=True, radius=True)
    s.arrow(inch(7.25), inch(2.55), inch(0.26), inch(0.62), "down", COLORS["slate"])
    s.arrow(inch(6.85), inch(3.42), inch(0.35), inch(0.18), "left", COLORS["slate"])
    outputs = [
        (inch(0.72), "source_data_validation\nOHLCV / required files\nct_val / funding / DB parity", "5EEAD4"),
        (inch(3.65), "validation_result.json\nstatus / gates / conclusion", COLORS["line"]),
        (inch(6.58), "mismatches_*.csv\nindicators / signals\ntrades / pnl / metrics", COLORS["line"]),
        (inch(9.5), "API / UI\nstrategy-validation\nview-validation.js", COLORS["line"]),
    ]
    for x, text, line in outputs:
        s.shape(x, inch(4.75), inch(2.55), inch(0.82), text, fill="F8FAFC", line=line, color=COLORS["text"], size=9.1, bold=True, radius=True)
    for x in [inch(3.28), inch(6.2), inch(9.12)]:
        s.arrow(x, inch(5.04), inch(0.28), inch(0.2), "right", COLORS["slate"])
    add_source(s, "Source: run_differential_validation(), _write_reference_artifacts(), routes_backtest.py, frontend/view-validation.js")
    slides.append(s)

    s = Slide("vectorbt：架構、參數與回測邏輯", "快速 vectorized reference；technical signal strict，PnL advisory")
    flow = [
        ("price_series.csv\nclose series", "blue"),
        ("SMA / EMA / MACD\nindicator recompute", "teal"),
        ("crossover\nbuy / sell signals", "orange"),
        ("Portfolio.from_signals\nentries / exits", "purple"),
        ("reference_* artifacts\nmetrics advisory", "green"),
    ]
    for i, (text, color) in enumerate(flow):
        x = inch(0.62 + i * 2.42)
        s.shape(x, inch(1.42), inch(1.95), inch(0.82), text, fill="FFFFFF", line=COLORS[color], color=COLORS["text"], size=8.8, bold=True, radius=True)
        if i < 4:
            s.arrow(x + inch(1.98), inch(1.72), inch(0.28), inch(0.18), "right", COLORS["slate"])
    add_card(
        s,
        inch(0.65),
        inch(2.75),
        inch(3.85),
        inch(2.1),
        "核心參數",
        [
            "strategy params: fast_window/slow_window, fast_span/slow_span, MACD 12/26/9 預設",
            "init_cash = bundle.initial_equity",
            "fees = 0.0；freq = bar 對應年化頻率",
            "required: result.json, price_series.csv, signals.csv",
        ],
        "blue",
    )
    add_card(
        s,
        inch(4.78),
        inch(2.75),
        inch(3.85),
        inch(2.1),
        "Signal 邏輯",
        [
            "warmup 後檢查 prev_fast <= prev_slow 且 cur_fast > cur_slow → buy",
            "prev_fast >= prev_slow 且 cur_fast < cur_slow → sell",
            "若 artifact trades 有 size_after，使用 execution position 判斷是否已在倉位",
        ],
        "teal",
    )
    add_card(
        s,
        inch(8.92),
        inch(2.75),
        inch(3.45),
        inch(2.1),
        "研究掃描補充",
        [
            "vectorbt_scanner.py 用於快速參數掃描",
            "Funding: APR threshold / entry fee proxy",
            "Order-book MM scanners 已移除",
        ],
        "orange",
    )
    add_source(s, "Source: VectorBTReferenceAdapter, _technical_reference_signals(), backtesting/vectorbt_scanner.py")
    slides.append(s)

    s = Slide("backtrader：架構、參數與回測邏輯", "事件驅動 technical reference；signal timing strict，order/PnL advisory")
    flow = [
        ("price_series.csv\nOHLCV → PandasData", "blue"),
        ("bt.Cerebro\nsetcash(initial_equity)", "teal"),
        ("TechnicalStrategy.next()\nupdate indicator state", "orange"),
        ("buy/sell market orders\nnotify_order/trade", "purple"),
        ("signals / trades / equity\ncompare scopes", "green"),
    ]
    for i, (text, color) in enumerate(flow):
        x = inch(0.62 + i * 2.42)
        s.shape(x, inch(1.38), inch(1.95), inch(0.9), text, fill="FFFFFF", line=COLORS[color], color=COLORS["text"], size=8.6, bold=True, radius=True)
        if i < 4:
            s.arrow(x + inch(1.98), inch(1.72), inch(0.28), inch(0.18), "right", COLORS["slate"])
    add_card(
        s,
        inch(0.65),
        inch(2.82),
        inch(3.75),
        inch(2.1),
        "核心設定",
        ["dependency: backtrader", "bt.Cerebro(stdstats=False)", "broker.setcash(bundle.initial_equity)", "PandasData: open/high/low/close/volume"],
        "teal",
    )
    add_card(
        s,
        inch(4.65),
        inch(2.82),
        inch(3.75),
        inch(2.1),
        "策略參數",
        ["MA: fast_window=20, slow_window=50", "EMA: fast_span=20, slow_span=50", "MACD: fast_span=12, slow_span=26, signal_span=9", "warmup = slow 或 slow+signal"],
        "blue",
    )
    add_card(
        s,
        inch(8.65),
        inch(2.82),
        inch(3.75),
        inch(2.1),
        "Gate 意義",
        ["reference_role = reference_signals_only for technical", "strict scope: signal_logic", "order_semantics = backtrader_market_orders", "PnL / equity / metrics 仍為 advisory"],
        "orange",
    )
    add_source(s, "Source: BacktraderReferenceAdapter, _run_backtrader_technical_reference()")
    slides.append(s)

    s = Slide("Nautilus：目前 v1 與目標高保真路徑", "Nautilus 是 queue-aware 目標框架；目前 validation adapter 尚未跑 engine")
    s.shape(inch(0.72), inch(1.42), inch(5.35), inch(2.05), fill="FFFFFF", line=COLORS["orange"], radius=True)
    s.textbox(inch(0.95), inch(1.62), inch(4.9), inch(0.3), "目前 differential validation v1", size=13, bold=True, color=COLORS["orange"])
    s.textbox(
        inch(0.95),
        inch(2.05),
        inch(4.85),
        inch(1.05),
        "artifact signals → _simulate_long_flat_trades → reference_nautilus_signals/trades/equity_curve.csv → export_manifest.json\nengine_execution = not_run；reference_role = advisory",
        size=9.7,
        color=COLORS["text"],
    )
    s.shape(inch(7.0), inch(1.42), inch(5.35), inch(2.05), fill="FFFFFF", line=COLORS["teal"], radius=True)
    s.textbox(inch(7.23), inch(1.62), inch(4.9), inch(0.3), "目標高保真路徑", size=13, bold=True, color=COLORS["teal"])
    s.textbox(
        inch(7.23),
        inch(2.05),
        inch(4.85),
        inch(1.05),
        "目前 v1：artifact / signal-point export。未來若恢復 order-book data，再規劃 Nautilus catalog + L2/L3 book + order/fill events + funding cashflows → OKX venue / matching engine",
        size=9.7,
        color=COLORS["text"],
    )
    s.arrow(inch(6.25), inch(2.2), inch(0.55), inch(0.3), "right", COLORS["slate"])
    add_card(
        s,
        inch(0.72),
        inch(4.0),
        inch(5.35),
        inch(1.58),
        "current v1 參數",
        ["strategy / fixture-run-id / engines", "artifact OHLCV + signal-point export", "order/fill and matching-engine semantics remain advisory"],
        "orange",
    )
    add_card(
        s,
        inch(7.0),
        inch(4.0),
        inch(5.35),
        inch(1.58),
        "目前限制",
        ["standalone L2 runner 已停用", "目前不維護 order-book data；queue priority / partial fill 留待下一階段", "不能作 live readiness 或 promotion evidence"],
        "red",
    )
    add_source(s, "Source: NautilusReferenceAdapter, backtesting/nautilus_backtest.py, docs/backtest_live_parity_plan.md")
    slides.append(s)

    s = Slide("策略範圍與參數摘要", "哪些策略可以 independent signal reference，哪些仍是 advisory")
    add_table(
        s,
        inch(0.55),
        inch(1.28),
        [inch(2.0), inch(2.35), inch(4.05), inch(3.35)],
        inch(0.78),
        [
            ["策略類型", "策略", "外部引擎狀態", "Gate 判讀"],
            [
                "Technical indicator",
                "ma_crossover\nema_crossover\nmacd_crossover",
                "vectorbt/backtrader: implemented reference_signals_only\nNautilus: advisory export",
                "至少 1 個 vectorbt/backtrader signal_logic PASS",
            ],
            [
                "Carry / stat arb / rotation",
                "funding_carry\npairs_trading\nohlcv_rotation",
                "三引擎多為 artifact_signal_replay / advisory",
                "不能單獨作 promotion evidence；需完整 adapter 或替代驗證",
            ],
            [
                "Validation-only",
                "daily_winner",
                "artifact replay / advisory 或 not applicable",
                "僅驗證 DB 聚合與 artifact 串接；不得 live",
            ],
            [
                "Removed order-book MM",
                "as_market_maker\nobi_market_maker",
                "已自 active UI/API/validation scope 刪除",
                "不維護 order-book data；不得作為 promotion target",
            ],
        ],
    )
    s.shape(
        inch(0.75),
        inch(5.78),
        inch(11.75),
        inch(0.55),
        "關鍵參數來源：strategy_params 來自 result/config；不得依 chat memory 改變策略假設。新增策略必須宣告 Reference portability contract，否則不得進入 review/demo/shadow。",
        fill="FEF3C7",
        line="F59E0B",
        color=COLORS["text"],
        size=9.5,
        bold=True,
        radius=True,
    )
    add_source(s, "Source: docs/ai_collaboration.md 新策略接入規範, REFERENCE_VALIDATION_CONTRACTS")
    slides.append(s)

    s = Slide("目前回測系統驗證方式", "source data checks + external reference + scoped mismatch + gate conclusion")
    steps = [
        ("1\n回測產物", "result.json\nprice_series.csv\nsignals/trades/fills/equity", "blue"),
        ("2\n資料檢查", "required artifacts\nOHLCV 結構\nct_val / funding / DB parity", "teal"),
        ("3\n外部引擎", "vectorbt\nbacktrader\nnautilus", "orange"),
        ("4\n比較 scopes", "indicator_values\nsignal_logic\ntrade / pnl / metrics", "purple"),
        ("5\nGate / 結論", "signal_logic_gate\nportable_validation_gate\nvalidation_conclusion", "green"),
    ]
    for i, (num, body, color) in enumerate(steps):
        x = inch(0.55 + i * 2.55)
        s.shape(x, inch(1.45), inch(0.55), inch(0.55), num, fill=COLORS[color], line=None, color="FFFFFF", size=12, bold=True, radius=True)
        s.shape(x + inch(0.1), inch(2.12), inch(2.05), inch(1.18), body, fill="FFFFFF", line=COLORS[color], color=COLORS["text"], size=8.7, bold=True, radius=True)
        if i < len(steps) - 1:
            s.arrow(x + inch(2.20), inch(2.55), inch(0.32), inch(0.22), "right", COLORS["slate"])
    for x, title, body in [
        (inch(0.7), "輸出檔", "validation_result.json\nreference_<engine>_*.csv\nmismatches_*.csv"),
        (inch(4.86), "CLI / API", "scripts/run_differential_validation.py\nPOST /strategy-validation/run\nPOST /{run_id}/differential-validation/run"),
        (inch(9.02), "UI", "view-validation.js\nengine role / mismatch count\nadvisory tooltips"),
    ]:
        s.shape(x, inch(4.05), inch(3.25 if title == "UI" else 3.65), inch(1.25), title, fill="F8FAFC", line=COLORS["line"], color=COLORS["text"], size=12, bold=True, radius=True)
        s.textbox(x + inch(0.28), inch(4.48), inch(2.85 if title == "UI" else 3.1), inch(0.55), body, size=8.6, color=COLORS["muted"])
    add_source(s, "Source: _source_data_validation(), compare_reference(), run_differential_validation(), routes_backtest.py")
    slides.append(s)

    s = Slide("Deployment Gate 關係圖", "Differential validation 只是其中一個必過項，不取代 WF/CPCV 或風控 gate")
    items = [
        ("Historical artifact\nvalidation_status", "gray1"),
        ("Idealized-fill\n排除", "red"),
        ("Differential validation\ntechnical signal strict", "blue"),
        ("ct_val provenance\nSWAP 必過", "teal"),
        ("Walk-forward / CPCV\nDSR & PSR ≥ 0.95", "orange"),
        ("Replay / shadow / demo\nfill/order/equity/fees/funding", "purple"),
        ("User approval\n才可升級風險模式", "green"),
    ]
    for i, (text, color) in enumerate(items):
        x = inch(0.75 + (i % 4) * 3.05)
        y = inch(1.22 + 1.75 * (i // 4))
        s.shape(x, y, inch(2.55), inch(1.05), text, fill="FFFFFF", line=COLORS[color], color=COLORS["text"], size=9.3, bold=True, radius=True)
        if i < 3 or 4 <= i < 6:
            s.arrow(x + inch(2.58), y + inch(0.39), inch(0.28), inch(0.2), "right", COLORS["slate"])
        if i == 3:
            s.arrow(inch(2.0), y + inch(1.13), inch(0.24), inch(0.44), "down", COLORS["slate"])
    s.shape(
        inch(0.8),
        inch(5.35),
        inch(11.6),
        inch(0.75),
        "硬規則：未通過這些 gate 與使用者批准前，不得宣稱策略 ready for live。Differential validation PASS 也只代表特定 reference scope，不代表成交、資金費、成本模型或實盤風險已驗證。",
        fill="FEE2E2",
        line="FCA5A5",
        color=COLORS["text"],
        size=10.2,
        bold=True,
        radius=True,
    )
    add_source(s, "Source: docs/ai_collaboration.md 回測正確性 Gate / 部署 Gate / ct_val 來源檢查")
    slides.append(s)

    s = Slide("目前操作入口與既有 artifact", "報告對應到 repo 內可查的 CLI、API、UI 與 results 目錄")
    add_card(
        s,
        inch(0.65),
        inch(1.35),
        inch(3.75),
        inch(2.0),
        "CLI",
        ["python scripts/run_differential_validation.py --run-id <id>", "--strategy <name> --fixture-run-id <id>", "--engines vectorbt,backtrader,nautilus", "--validation-id <stable_id>"],
        "blue",
    )
    add_card(
        s,
        inch(4.65),
        inch(1.35),
        inch(3.75),
        inch(2.0),
        "API",
        ["POST /strategy-validation/run", "GET /strategy-validation/contracts", "POST /{run_id}/differential-validation/run", "GET artifact endpoints for mismatch/reference files"],
        "teal",
    )
    add_card(
        s,
        inch(8.65),
        inch(1.35),
        inch(3.75),
        inch(2.0),
        "UI",
        ["Validation view exposes engine roles", "Signals strict；Indicators/Trades/PnL/Metrics advisory labels", "Reviewer guardrail explains PASS scope", "Mismatch preview reads mismatches_*.csv"],
        "orange",
    )
    s.shape(inch(0.72), inch(4.05), inch(11.65), inch(1.05), fill="FFFFFF", line=COLORS["line"], radius=True)
    s.textbox(inch(0.95), inch(4.18), inch(11.1), inch(0.25), "目前 results/strategy_validation 下可見策略目錄", size=12.5, bold=True, color=COLORS["text"])
    s.textbox(
        inch(0.95),
        inch(4.56),
        inch(11.0),
        inch(0.36),
        "daily_winner、macd_crossover、ma_crossover。既有 artifacts 可能早於最新欄位要求；若要作 promotion evidence，technical 策略需重跑並確認 validation_result.json 含必要 gate 欄位。",
        size=9.7,
        color=COLORS["muted"],
    )
    add_source(s, "Source: scripts/run_differential_validation.py, routes_backtest.py, frontend/view-validation.js, results/strategy_validation")
    slides.append(s)

    s = Slide("建議下一步", "把外部驗證從「可重播」推進到「可作 promotion evidence」")
    add_card(
        s,
        inch(0.65),
        inch(1.35),
        inch(3.75),
        inch(2.4),
        "短期：驗證產物一致化",
        ["重跑 legacy ma/macd artifacts，補齊 source_data_validation / validation_conclusion / portable_validation_gate", "把 validation_result.json 當報告附件索引", "保留 mismatch CSV 供 reviewer 快速定位"],
        "blue",
    )
    add_card(
        s,
        inch(4.65),
        inch(1.35),
        inch(3.75),
        inch(2.4),
        "中期：強化 replay-based validation",
        ["WF/CPCV 輸入改為 replay 產生的 fill/order/equity returns", "所有 SWAP artifact 必須通過 authoritative ct_val", "shadow/demo calibration 回寫 queue/latency/fill 參數"],
        "teal",
    )
    add_card(
        s,
        inch(8.65),
        inch(1.35),
        inch(3.75),
        inch(2.4),
        "長期：完整 Nautilus adapter",
        ["若 user 恢復 order-book data plan，建立 Nautilus catalog 與 OKX adapter mapping", "接 L2/L3 order book、order/fill events、funding cashflows", "讓 execution-sensitive 策略能跑 queue-aware independent reference"],
        "orange",
    )
    s.shape(
        inch(0.75),
        inch(4.5),
        inch(11.55),
        inch(0.82),
        "Claude review questions：目前 signal strict scope 是否足以支撐 technical strategy promotion？非 technical strategy 應以哪些替代證據補足 external reference gap？Nautilus full adapter 的最小可驗收資料集要到 L2 還是 L3？",
        fill="EEF2FF",
        line="C4B5FD",
        color=COLORS["text"],
        size=9.6,
        bold=True,
        radius=True,
    )
    add_source(s, "Source: docs/backtest_live_parity_plan.md, docs/ai_collaboration.md")
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
