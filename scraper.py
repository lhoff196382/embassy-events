"""
Embassy Cultural Events Scraper — Brasília
Busca eventos culturais em embaixadas e consulados via DuckDuckGo Search API.
"""

import os
import re
import json
import datetime
import smtplib
import urllib.request
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Embaixadas e fontes conhecidas ────────────────────────────────────────────
EMBASSY_SITES = [
    {"name": "Instituto Francês do Brasil", "url": "https://www.institutfrancais.com.br/brasilia"},
    {"name": "Goethe-Institut Brasília",    "url": "https://www.goethe.de/ins/br/pt/sta/bra.html"},
    {"name": "Instituto Cervantes Brasília", "url": "https://brasilia.cervantes.es"},
    {"name": "British Council Brasil",       "url": "https://www.britishcouncil.org.br"},
    {"name": "Instituto Italiano de Cultura","url": "https://iicbrasilia.esteri.it"},
    {"name": "Instituto Camões Brasília",    "url": "https://www.instituto-camoes.pt"},
    {"name": "Centro Cultural do Japão",     "url": "https://www.br.emb-japan.go.jp"},
    {"name": "Embaixada dos EUA Brasília",   "url": "https://br.usembassy.gov"},
]

SEARCH_QUERIES = [
    "eventos culturais embaixadas consulados Brasília 2025 grátis",
    "agenda cultural embaixadas Brasília shows exposições 2025",
    "eventos embaixada francesa alemã italiana Brasília 2025",
    "cultura diplomática agenda Brasília embaixadas 2025",
]


def search_duckduckgo(query: str, max_results: int = 10) -> list[dict]:
    """Busca via DuckDuckGo Instant Answer API (sem chave)."""
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1",
    })
    url = f"https://api.duckduckgo.com/?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EmbassyEventsBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        results = []
        for topic in data.get("RelatedTopics", [])[:max_results]:
            text = topic.get("Text", "")
            link = topic.get("FirstURL", "")
            if text:
                results.append({"text": text, "url": link})
        return results
    except Exception as e:
        print(f"  Erro DuckDuckGo: {e}")
        return []


def search_serpapi(query: str) -> list[dict]:
    """Busca via SerpAPI (requer SERPAPI_KEY no env). Fallback opcional."""
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return []
    params = urllib.parse.urlencode({
        "q": query,
        "location": "Brasília, Brazil",
        "hl": "pt",
        "gl": "br",
        "api_key": api_key,
        "engine": "google",
        "num": "10",
    })
    url = f"https://serpapi.com/search?{params}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        results = []
        for r in data.get("organic_results", [])[:10]:
            results.append({
                "text": f"{r.get('title','')} — {r.get('snippet','')}",
                "url": r.get("link", ""),
            })
        return results
    except Exception as e:
        print(f"  Erro SerpAPI: {e}")
        return []


# ── Detecção de preço ─────────────────────────────────────────────────────────
FREE_KEYWORDS = re.compile(
    r"\bgratu[ií]t[ao]s?\b|\bfree\b|\bentrada\s+franca\b|\bsem\s+cobran[çc]a\b",
    re.IGNORECASE,
)
PAID_KEYWORDS = re.compile(
    r"\bingressos?\b|\bpago\b|\bpaid\b|\bticket\b|\br\$\s*\d|\bvalor\b|\bcobran[çc]a\b",
    re.IGNORECASE,
)

def classify_price(text: str) -> str:
    has_free = bool(FREE_KEYWORDS.search(text))
    has_paid = bool(PAID_KEYWORDS.search(text))
    if has_free and not has_paid:
        return "✅ Gratuito"
    if has_paid and not has_free:
        return "💰 Pago"
    if has_free and has_paid:
        return "🎟️ Parcialmente pago / verificar"
    return "❓ Não informado"


# ── Coleta de eventos ─────────────────────────────────────────────────────────
def collect_events() -> list[dict]:
    events = []
    seen_urls = set()

    for query in SEARCH_QUERIES:
        print(f"Buscando: {query}")
        # Tenta SerpAPI primeiro; senão DuckDuckGo
        results = search_serpapi(query) or search_duckduckgo(query)
        for r in results:
            url = r.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            text = r.get("text", "")
            events.append({
                "title": text[:120],
                "url": url,
                "price": classify_price(text),
                "source": query,
            })

    return events


# ── E-mail ─────────────────────────────────────────────────────────────────────
def build_html(events: list[dict]) -> str:
    today = datetime.date.today().strftime("%d/%m/%Y")
    rows = ""
    for ev in events:
        url = ev["url"]
        link = f'<a href="{url}">{url[:60]}…</a>' if url else "—"
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee">{ev['title']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap">{ev['price']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;font-size:12px">{link}</td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="3" style="padding:16px;text-align:center;color:#888">Nenhum evento encontrado nesta varredura.</td></tr>'

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:800px;margin:auto;padding:24px">
  <h2 style="color:#1a3c6e">🌍 Eventos Culturais — Embaixadas e Consulados em Brasília</h2>
  <p style="color:#555">Varredura realizada em <strong>{today}</strong>. Próxima em 5 dias.</p>
  <table width="100%" cellspacing="0" style="border-collapse:collapse;margin-top:16px">
    <thead>
      <tr style="background:#1a3c6e;color:#fff">
        <th style="padding:10px;text-align:left">Evento / Descrição</th>
        <th style="padding:10px;text-align:left">Preço</th>
        <th style="padding:10px;text-align:left">Link</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <hr style="margin-top:32px">
  <p style="font-size:11px;color:#aaa">
    Fontes monitoradas: Instituto Francês, Goethe-Institut, Instituto Cervantes, British Council,
    Instituto Italiano, Instituto Camões, Embaixada do Japão, Embaixada dos EUA — Brasília.<br>
    Para remover este e-mail, exclua o workflow no GitHub Actions.
  </p>
</body>
</html>"""


def send_email(html: str, events: list[dict]):
    sender    = os.environ["GMAIL_USER"]
    password  = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("EMAIL_TO", sender)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌍 Eventos Culturais — Embaixadas Brasília ({datetime.date.today().strftime('%d/%m/%Y')})"
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
    print(f"E-mail enviado para {recipient} com {len(events)} evento(s).")


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Embassy Events Scraper ===")
    events = collect_events()
    print(f"Total de resultados: {len(events)}")
    html = build_html(events)
    send_email(html, events)
