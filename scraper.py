"""
Embassy Cultural Events Scraper — Brasília
Fontes: RSS feeds + Brave Search API + Instagram
Diretório de embaixadas: https://rotasbrasil.org/rotas-brasil/
"""

import os, re, json, datetime, smtplib, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from html.parser import HTMLParser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Janela de datas ───────────────────────────────────────────────────────────
TODAY     = datetime.date.today()
DATE_FROM = TODAY
DATE_TO   = TODAY + datetime.timedelta(days=30)

MONTHS_PT = {
    "janeiro":1,"fevereiro":2,"março":3,"marco":3,"abril":4,"maio":5,
    "junho":6,"julho":7,"agosto":8,"setembro":9,"outubro":10,
    "novembro":11,"dezembro":12,"jan":1,"fev":2,"mar":3,"abr":4,
    "mai":5,"jun":6,"jul":7,"ago":8,"set":9,"out":10,"nov":11,"dez":12,
}

# ── RSS Feeds (fontes mais confiáveis) ────────────────────────────────────────
RSS_FEEDS = [
    {"name":"Goethe-Institut Brasília",     "flag":"🇩🇪", "url":"https://www.goethe.de/ins/br/pt/sta/bra/ver.rss"},
    {"name":"Institut Français Brasília",   "flag":"🇫🇷", "url":"https://www.institutfrancais.com.br/brasilia/agenda/feed"},
    {"name":"Instituto Cervantes Brasília", "flag":"🇪🇸", "url":"https://brasilia.cervantes.es/pt/actividades_espanol/rss_actividades.htm"},
    {"name":"British Council Brasil",       "flag":"🇬🇧", "url":"https://www.britishcouncil.org.br/feed"},
]

# ── Buscas no DuckDuckGo (gratuito, sem cadastro) ────────────────────────────
DDG_QUERIES = [
    "eventos culturais embaixadas Brasília 2026",
    "agenda cultural consulados Brasília junho julho 2026",
    "Instituto Italiano Cultura Brasília eventos 2026",
    "Goethe-Institut Brasília eventos agenda 2026",
    "Institut Français Brasília agenda 2026",
    "Embaixada Japão EUA eventos culturais Brasília 2026",
]

# ── Perfis Instagram ──────────────────────────────────────────────────────────
INSTAGRAM_PROFILES = [
    {"name":"Institut Français Brasília",  "user":"ifbrasil",         "flag":"🇫🇷"},
    {"name":"Goethe-Institut Brasil",      "user":"goethe_brasil",    "flag":"🇩🇪"},
    {"name":"Instituto Cervantes Brasil",  "user":"cervantes_brasil", "flag":"🇪🇸"},
    {"name":"British Council Brasil",      "user":"britishcouncilbr", "flag":"🇬🇧"},
    {"name":"Embaixada EUA Brasil",        "user":"embaixadaeua",     "flag":"🇺🇸"},
    {"name":"Instituto Italiano Bsb",      "user":"iicbrasilia",      "flag":"🇮🇹"},
    {"name":"Embaixada do Japão BR",       "user":"embaixadadojapao", "flag":"🇯🇵"},
    {"name":"Embaixada da França BR",      "user":"francenobrasil",   "flag":"🇫🇷"},
    {"name":"Embaixada Alemã BR",          "user":"alemanha.brasil",  "flag":"🇩🇪"},
]

# ── Detecção de preço ─────────────────────────────────────────────────────────
FREE_RE = re.compile(r"\bgratu[ií]t[ao]s?\b|\bfree\b|\bentrada\s+franca\b|\blivre\b|\bsem\s+custo\b", re.I)
PAID_RE = re.compile(r"\bingressos?\b|\bpago\b|\btickets?\b|\br\$\s*\d|\bcomprar\b|\bcompre\b", re.I)

def classify_price(text):
    f, p = bool(FREE_RE.search(text)), bool(PAID_RE.search(text))
    if f and not p: return "✅ Gratuito"
    if p and not f: return "💰 Pago"
    if f and p:     return "🎟️ Verificar"
    return "❓ Não informado"

# ── Detecção de datas ─────────────────────────────────────────────────────────
DATE_PATS = [
    re.compile(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b"),
    re.compile(r"\b(\d{1,2})\s+(?:de\s+)?(" + "|".join(MONTHS_PT) + r")(?:\s+(?:de\s+)?(\d{2,4}))?\b", re.I),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
]

def extract_dates(text):
    found = []
    y = TODAY.year
    for pat in DATE_PATS:
        for m in pat.finditer(text):
            g = m.groups()
            try:
                if len(g) >= 3 and g[0] and len(g[0]) == 4:
                    found.append(datetime.date(int(g[0]), int(g[1]), int(g[2])))
                elif g[1] and g[1].lower() in MONTHS_PT:
                    yr = int(g[2]) if g[2] else y
                    if yr < 100: yr += 2000
                    found.append(datetime.date(yr, MONTHS_PT[g[1].lower()], int(g[0])))
                else:
                    mo = int(g[1]); dy = int(g[0])
                    if mo > 12: mo, dy = dy, mo
                    yr = int(g[2]) if g[2] else y
                    if yr < 100: yr += 2000
                    found.append(datetime.date(yr, mo, dy))
            except Exception:
                pass
    return found

def date_label(text):
    dates = extract_dates(text)
    future = [d for d in dates if d >= DATE_FROM - datetime.timedelta(days=1)]
    if not future: return "📅 A confirmar"
    return f"📅 {min(future).strftime('%d/%m/%Y')}"

# ── HTTP helper ───────────────────────────────────────────────────────────────
def fetch(url, timeout=15, headers=None):
    h = {"User-Agent": "Mozilla/5.0", "Accept-Language": "pt-BR,pt;q=0.9"}
    if headers:
        h.update(headers)
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  Erro {url}: {e}")
        return ""

TAG_RE = re.compile(r"<[^>]+>")
def strip_tags(html):
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", html)).strip()

# ── 1. RSS Feeds ──────────────────────────────────────────────────────────────
def scrape_rss():
    events = []
    for src in RSS_FEEDS:
        print(f"  RSS: {src['name']}")
        raw = fetch(src["url"])
        if not raw:
            continue
        try:
            root = ET.fromstring(raw)
            ns   = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//item") or root.findall(".//atom:entry", ns)
            found = 0
            for item in items:
                title = strip_tags(item.findtext("title") or item.findtext("atom:title", namespaces=ns) or "")
                desc  = strip_tags(item.findtext("description") or item.findtext("atom:summary", namespaces=ns) or "")
                link  = (item.findtext("link") or src["url"]).strip()
                pub   = item.findtext("pubDate") or item.findtext("atom:published", namespaces=ns) or ""
                full  = f"{title} {desc} {pub}"
                events.append({
                    "source":  f"{src['flag']} {src['name']}",
                    "title":   title[:200] or desc[:200],
                    "date":    date_label(full),
                    "price":   classify_price(full),
                    "url":     link,
                    "channel": "📡 RSS",
                })
                found += 1
                if found >= 5:
                    break
            print(f"    {found} item(s)")
        except Exception as e:
            print(f"    Erro RSS: {e}")
    return events

# ── 2. DuckDuckGo HTML Search (gratuito, sem cadastro) ───────────────────────
RESULT_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
    r'.*?<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
    re.S,
)

def scrape_ddg():
    events = []
    seen   = set()

    for query in DDG_QUERIES:
        print(f"  DuckDuckGo: {query}")
        params = urllib.parse.urlencode({"q": query, "kl": "br-pt"})
        url    = f"https://html.duckduckgo.com/html/?{params}"
        try:
            raw = fetch(url, headers={
                "User-Agent":  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept":      "text/html",
                "Referer":     "https://duckduckgo.com/",
            })
            if not raw:
                continue

            # Extrai resultados via regex na página HTML
            for m in RESULT_RE.finditer(raw):
                link    = strip_tags(m.group(1)).strip()
                title   = strip_tags(m.group(2)).strip()
                snippet = strip_tags(m.group(3)).strip()

                # Remove links de rastreamento do DDG
                if "duckduckgo.com" in link:
                    try:
                        qs   = urllib.parse.urlparse(link).query
                        link = urllib.parse.parse_qs(qs).get("uddg", [link])[0]
                    except Exception:
                        pass

                if link in seen or not title:
                    continue
                seen.add(link)

                full = f"{title} {snippet}"
                events.append({
                    "source":  "🔍 DuckDuckGo",
                    "title":   full[:200],
                    "date":    date_label(full),
                    "price":   classify_price(full),
                    "url":     link,
                    "channel": "🔍 Web",
                })

            import time
            time.sleep(2)   # pausa entre buscas para não bloquear

        except Exception as e:
            print(f"    Erro DDG: {e}")

    print(f"    {len(events)} resultado(s)")
    return events

# ── 3. Instagram ──────────────────────────────────────────────────────────────
EVENT_RE = re.compile(
    r".{0,100}(exposi[çc][ãa]o|concerto|show|palestra|workshop|semin[aá]rio|"
    r"festival|exibi[çc][ãa]o|cinema|teatro|dan[çc]a|m[úu]sica|cultura|evento|"
    r"inaugura[çc][ãa]o|leitura|sarau).{0,200}", re.I)

def scrape_instagram():
    try:
        import instaloader
    except ImportError:
        print("  instaloader não instalado")
        return []

    events = []
    L = instaloader.Instaloader(
        download_pictures=False, download_videos=False,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False, quiet=True,
    )
    cutoff = datetime.datetime.now() - datetime.timedelta(days=10)

    for p in INSTAGRAM_PROFILES:
        print(f"  Instagram: @{p['user']}")
        try:
            profile = instaloader.Profile.from_username(L.context, p["user"])
            for post in profile.get_posts():
                if post.date_local < cutoff:
                    break
                caption = post.caption or ""
                for m in EVENT_RE.finditer(caption):
                    snippet = re.sub(r"\s+", " ", m.group()).strip()
                    events.append({
                        "source":  f"{p['flag']} {p['name']}",
                        "title":   snippet[:200],
                        "date":    date_label(caption),
                        "price":   classify_price(caption),
                        "url":     f"https://www.instagram.com/{p['user']}/",
                        "channel": "📸 Instagram",
                    })
                    break
        except Exception as e:
            print(f"    Erro @{p['user']}: {e}")

    return events

# ── E-mail ────────────────────────────────────────────────────────────────────
THEAD = """<thead><tr style="background:#1a3c6e;color:#fff">
  <th style="padding:10px;text-align:left">Instituto / Embaixada</th>
  <th style="padding:10px;text-align:left">Evento</th>
  <th style="padding:10px;text-align:left">Data</th>
  <th style="padding:10px;text-align:left">Preço</th>
  <th style="padding:10px;text-align:left">Fonte</th>
</tr></thead>"""

def make_rows(items):
    if not items:
        return '<tr><td colspan="5" style="padding:16px;text-align:center;color:#888">Nenhum resultado encontrado.</td></tr>'
    rows = ""
    for ev in items:
        rows += f"""<tr>
          <td style="padding:8px;border-bottom:1px solid #eee">{ev['source']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee">{ev['title']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap">{ev['date']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap">{ev['price']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;font-size:12px">
            <a href="{ev['url']}">{ev['channel']}</a></td></tr>"""
    return rows

def section(title, items):
    return f"""
    <h3 style="color:#1a3c6e;margin-top:28px">{title}</h3>
    <table width="100%" cellspacing="0" style="border-collapse:collapse">
      {THEAD}<tbody>{make_rows(items)}</tbody>
    </table>"""

def build_html(rss, ddg, ig):
    today  = TODAY.strftime("%d/%m/%Y")
    d_from = DATE_FROM.strftime("%d/%m/%Y")
    d_to   = DATE_TO.strftime("%d/%m/%Y")

    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:auto;padding:24px">
  <h2 style="color:#1a3c6e">🌍 Eventos Culturais — Embaixadas e Consulados em Brasília</h2>
  <p style="color:#555">
    Varredura em <strong>{today}</strong> —
    eventos de <strong>{d_from}</strong> até <strong>{d_to}</strong>.
    Próxima em 5 dias.
  </p>
  <p style="font-size:12px;color:#888">
    📋 Diretório de referência:
    <a href="https://rotasbrasil.org/rotas-brasil/">rotasbrasil.org — 128 embaixadas em Brasília</a>
  </p>
  {section("📡 RSS — Institutos Culturais", rss)}
  {section("🔍 DuckDuckGo — Busca Web", ddg)}
  {section("📸 Instagram", ig)}
  <hr style="margin-top:32px">
  <p style="font-size:11px;color:#aaa">
    Fontes: Goethe-Institut · Institut Français · Instituto Cervantes · British Council ·
    Instituto Italiano · Embaixadas dos EUA · Japão · França · Alemanha · Reino Unido — Brasília/DF
  </p>
</body></html>"""

def send_email(html, total):
    sender    = os.environ["GMAIL_USER"]
    password  = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("EMAIL_TO", sender)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌍 Eventos Embaixadas Brasília — {TODAY.strftime('%d/%m/%Y')} ({total} resultado(s))"
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(sender, password)
        s.sendmail(sender, recipient, msg.as_string())
    print(f"✅ E-mail enviado para {recipient} — {total} resultado(s).")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"=== Embassy Events — {TODAY} até {DATE_TO} ===")
    print("\n[1/3] RSS feeds...")
    rss = scrape_rss()
    print(f"      {len(rss)} resultado(s)")
    print("\n[2/3] DuckDuckGo Search...")
    ddg = scrape_ddg()
    print(f"      {len(ddg)} resultado(s)")
    print("\n[3/3] Instagram...")
    ig = scrape_instagram()
    print(f"      {len(ig)} resultado(s)")
    total = len(rss) + len(ddg) + len(ig)
    print(f"\nTotal: {total}. Enviando e-mail...")
    html = build_html(rss, ddg, ig)
    send_email(html, total)
