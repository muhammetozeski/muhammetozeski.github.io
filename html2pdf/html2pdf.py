#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
html2pdf - HTML dosyalarini gercek, tek-sayfa, kucuk boyutlu PDF'e cevirir.

- Gercek PDF: metin secilebilir, linkler tiklanabilir (resim/yalanci PDF degil).
- Tek sayfa: cikti, icerigin tam boyutunda tek bir sayfadir; sayfa bolunmesi yoktur.
- Tarayicidaki gorunum: senin Chrome'unda gordugun haliyle (ekran stili) basilir.
- Kucuk dosya: gomulu gorseller ekrandaki gosterim boyutunun ~3 katina indirilir,
  fotograflar JPEG'e cevrilir -> 20+ MB yerine 2-3 MB.

Kullanim:
    python html2pdf.py "cv.html"
    python html2pdf.py "cv.html" -o "cikti.pdf"
    python html2pdf.py "klasor"            # klasordeki tum .html dosyalari
    python html2pdf.py *.html
Onemli secenekler asagida --help ile gorulebilir.

Gereksinimler (ilk calistirmada otomatik kurulur): playwright, pymupdf, pillow
ve makinede kurulu Google Chrome (yoksa Edge'e duser).
"""

import sys, os, io, glob, argparse, subprocess

# ------------------------------------------------------------------ deps
def _ensure(pkg, import_name=None):
    try:
        __import__(import_name or pkg)
    except ImportError:
        print(f"[kurulum] {pkg} kuruluyor...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", pkg])

_ensure("playwright")
_ensure("pymupdf", "fitz")
_ensure("pillow", "PIL")

import fitz
from PIL import Image
from playwright.sync_api import sync_playwright

PX2PT = 72 / 96.0   # CSS px -> PDF pt

# ------------------------------------------------------------------ render
def render_pdf_bytes(page, width_px, height_px):
    return page.pdf(
        width=f"{width_px}px",
        height=f"{height_px}px",
        print_background=True,
        page_ranges="1",
        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        prefer_css_page_size=False,
    )

def content_bottom_px(pdf_bytes):
    """En alttaki gercek icerigin (metin + gorsel + arka plan) y'si, css px."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    ti = 0.0
    for b in page.get_text("rawdict")["blocks"]:
        ti = max(ti, b["bbox"][3])
    draw = ti
    for dr in page.get_drawings():
        y1 = dr["rect"].y1
        if y1 <= ti + 220:           # normal padding mesafesi -> gercek; cok asagisi = artik
            draw = max(draw, y1)
    doc.close()
    return max(ti, draw) / PX2PT

def measure(page, selector):
    """Kok elemanin boyutu + tum tiklanabilir linklerin (koke gore) px konumlari."""
    js = """
    (sel) => {
      const root = document.querySelector(sel) || document.body;
      const rr = root.getBoundingClientRect();
      const ox = rr.left + window.scrollX, oy = rr.top + window.scrollY;
      const links = Array.from(document.querySelectorAll('a[href]')).map(a => {
        const b = a.getBoundingClientRect();
        return { href: a.href,
                 x: b.left + window.scrollX - ox, y: b.top + window.scrollY - oy,
                 w: b.width, h: b.height };
      }).filter(l => l.w > 0 && l.h > 0 && /^(https?:|mailto:|tel:)/i.test(l.href));
      return { w: rr.width, h: rr.height, links };
    }
    """
    return page.evaluate(js, selector)

# ------------------------------------------------------------------ post-process
def optimize_images(doc, scale, quality):
    page = doc[0]
    disp = {}
    for img in doc.get_page_images(0, full=True):
        xref = img[0]
        for r in page.get_image_rects(xref):
            disp[xref] = max(disp.get(xref, 0), r.width / PX2PT, r.height / PX2PT)
    saved = changed = 0
    for img in doc.get_page_images(0, full=True):
        xref, nw, nh = img[0], img[2], img[3]
        d = disp.get(xref, 0)
        if d <= 0:
            continue
        target = d * scale
        native_max = max(nw, nh)
        if native_max <= target * 1.15 or native_max <= 130:
            continue
        info = doc.extract_image(xref)
        has_alpha = info.get("smask", 0) != 0
        try:
            im = Image.open(io.BytesIO(info["image"])); im.load()
        except Exception:
            continue
        ratio = target / native_max
        new_size = (max(1, round(nw * ratio)), max(1, round(nh * ratio)))
        out = io.BytesIO()
        if has_alpha:
            im.convert("RGBA").resize(new_size, Image.LANCZOS).save(out, format="PNG", optimize=True)
        else:
            im.convert("RGB").resize(new_size, Image.LANCZOS).save(
                out, format="JPEG", quality=quality, optimize=True, progressive=True)
        nb = out.getvalue()
        if len(nb) < len(info["image"]):
            page.replace_image(xref, stream=nb)
            saved += len(info["image"]) - len(nb); changed += 1
    return changed, saved

def inject_links(doc, links):
    page = doc[0]
    for l in page.get_links():       # Chrome'un (eksik) eklediklerini temizle
        page.delete_link(l)
    added = 0
    for l in links:
        r = fitz.Rect(l["x"]*PX2PT, l["y"]*PX2PT, (l["x"]+l["w"])*PX2PT, (l["y"]+l["h"])*PX2PT) & page.rect
        if r.is_empty:
            continue
        page.insert_link({"kind": fitz.LINK_URI, "from": r, "uri": l["href"]})
        added += 1
    return added

# ------------------------------------------------------------------ one file
def convert(page, in_html, out_pdf, opt):
    url = "file:///" + os.path.abspath(in_html).replace("\\", "/")
    page.set_viewport_size({"width": opt.viewport, "height": 1700})
    page.emulate_media(media=opt.media)
    page.goto(url, wait_until="networkidle", timeout=120000)
    page.evaluate("() => document.fonts ? document.fonts.ready : true")
    page.evaluate("""() => Promise.all(Array.from(document.images).map(i =>
        (i.complete && i.naturalWidth) ? 0 : new Promise(r => { i.onload = i.onerror = r; })))""")

    # Sayfayi gri govde cercevesinden ayir -> PDF tam kok eleman boyutunda.
    # min-height:0 sart: orijinal min-height:297mm, Chrome'un tek-uzun-sayfa
    # baski yolunu 1 sayfadan sonrasini kirpmaya zorluyor.
    page.add_style_tag(content=f"""
        @page {{ size: auto; margin: 0; }}
        html, body {{ background: {opt.background} !important; margin: 0 !important; padding: 0 !important; }}
        {opt.selector} {{ margin: 0 !important; box-shadow: none !important; min-height: 0 !important; }}
    """)

    broken = page.evaluate("""() => Array.from(document.images)
        .filter(i => !i.complete || i.naturalWidth === 0).map(i => i.currentSrc || i.src)""")
    if broken:
        print("  ! yuklenemeyen gorsel:", *broken, sep="\n    ")

    info = measure(page, opt.selector)
    Wpx = info["w"]

    # PASS 1: cok-uzun sayfa -> her sey TEK sayfada (bolunme/kirpilma yok).
    pass1 = render_pdf_bytes(page, Wpx, info["h"] + 1600)
    realH = content_bottom_px(pass1)
    # PASS 2: tam o yukseklikte -> sikica tek sayfa.
    finalH = int(realH) + opt.pad
    pass2 = render_pdf_bytes(page, Wpx, finalH)

    doc = fitz.open(stream=pass2, filetype="pdf")
    nimg, saved = optimize_images(doc, opt.scale, opt.quality)
    nlink = inject_links(doc, info["links"])
    doc.save(out_pdf, garbage=4, deflate=True, clean=True)
    p = doc[0].rect
    mb = os.path.getsize(out_pdf) / 1024 / 1024
    doc.close()
    print(f"  -> {os.path.basename(out_pdf)}  {p.width/72*25.4:.0f}x{p.height/72*25.4:.0f}mm  "
          f"linkler={nlink}  gorsel optimize={nimg} (-{saved/1024/1024:.1f}MB)  boyut={mb:.2f}MB")

# ------------------------------------------------------------------ cli
def gather_inputs(items):
    out = []
    for it in items:
        if os.path.isdir(it):
            out += sorted(glob.glob(os.path.join(it, "*.html")) + glob.glob(os.path.join(it, "*.htm")))
        elif any(c in it for c in "*?["):
            out += sorted(glob.glob(it))
        else:
            out.append(it)
    # tekille, .html olanlari tut
    seen, res = set(), []
    for f in out:
        af = os.path.abspath(f)
        if af not in seen and f.lower().endswith((".html", ".htm")) and os.path.isfile(f):
            seen.add(af); res.append(f)
    return res

def main():
    ap = argparse.ArgumentParser(description="HTML -> gercek tek-sayfa kucuk PDF.")
    ap.add_argument("inputs", nargs="*", help="html dosyasi / klasor / glob")
    ap.add_argument("-o", "--output", help="cikti pdf (yalniz tek girdi icin)")
    ap.add_argument("--selector", default=".page",
                    help="sayfa boyutunu belirleyen kok eleman (varsayilan .page; yoksa body kullanilir)")
    ap.add_argument("--media", default="screen", choices=["screen", "print"],
                    help="screen = tarayicidaki gorunum (varsayilan), print = @media print")
    ap.add_argument("--scale", type=float, default=3.0, help="gorsel ust-ornekleme kati (varsayilan 3)")
    ap.add_argument("--quality", type=int, default=92, help="JPEG kalitesi (varsayilan 92)")
    ap.add_argument("--background", default="#ffffff", help="govde arka plani (varsayilan beyaz)")
    ap.add_argument("--viewport", type=int, default=1200, help="render genisligi px (varsayilan 1200)")
    ap.add_argument("--pad", type=int, default=3, help="alt bosluk px (varsayilan 3)")
    opt = ap.parse_args()

    files = gather_inputs(opt.inputs)
    if not files:
        ap.print_help()
        print("\nHic .html bulunamadi.")
        return 1
    if opt.output and len(files) > 1:
        print("-o yalniz tek girdi ile kullanilabilir."); return 1

    # .page yoksa body'ye dus
    sel = opt.selector

    with sync_playwright() as p:
        browser = None
        for ch in ("chrome", "msedge"):
            try:
                browser = p.chromium.launch(channel=ch, headless=True)
                break
            except Exception:
                continue
        if browser is None:
            browser = p.chromium.launch(headless=True)  # son care: paketli chromium
        page = browser.new_page()

        for f in files:
            out_pdf = opt.output if opt.output else os.path.splitext(f)[0] + ".pdf"
            print(f"* {os.path.basename(f)}")
            # secili selector yoksa body'ye dus
            opt.selector = sel
            try:
                page.goto("file:///" + os.path.abspath(f).replace("\\", "/"))
                has = page.evaluate("(s) => !!document.querySelector(s)", sel)
                if not has:
                    opt.selector = "body"
            except Exception:
                pass
            convert(page, f, out_pdf, opt)
        browser.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
