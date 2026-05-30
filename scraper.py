"""
Embassy Cultural Events Scraper — Brasília
Busca eventos nos sites oficiais e Instagram das embaixadas/institutos culturais.
"""

import os
import re
import datetime
import smtplib
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Fontes: sites oficiais ────────────────────────────────────────────────────
EMBASSY_PAGES = [
    {
        "name": "Goethe-Institut Brasília",
        "url": "https://www.goethe.de/ins/br/pt/sta/bra/ver.html",
        "flag": "🇩🇪",
    },
    {
        "name": "Institut Français Brasília",
        "url": "https://www.institutfrancais.com.br/brasilia/agenda",
        "flag": "🇫🇷",
    },
    {
        "name": "Instituto Cervantes Brasília",
        "url": "https://brasilia.cervantes.es/pt/actividades_espanol/actividades_espanol.htm",
        "flag": "🇪🇸",
    },
    {
        "name": "British Council Brasil",
        "url": "https://www.britishcouncil.org.br/eventos",
        "flag": "🇬🇧",
    },
    {
        "name": "Instituto Italiano de Cultura",
        "url": "https://iicbrasilia.esteri.it/pt/gli_eventi/",
        "flag": "🇮🇹",
    },
    {
        "name": "Embaixada dos EUA — Eventos",
        "url": "https://br.usembassy.gov/pt/eventos/",
        "flag": "🇺🇸",
    },
    {
        "name": "Embaixada do Japão",
        "url": "https://www.br.emb-japan.go.jp/itpr_pt/eventinformation.html",
        "flag": "🇯🇵",
    },
    {
        "name": "Centro Cultural do Banco do Brasil (Brasília)",
        "url": "https://culturabancodobrasil.com.br/portal/brasilia/",
        "flag": "🇧🇷",
    },
]

# ── Perfis do Instagram ───────────────────────────────────────────────────────
INSTAGRAM_PROFILES = [
    {"name": "Institut Français Brasília", "user": "ifbrasil",         "flag": "🇫🇷"},
    {"name": "Goethe-Institut Brasil",     "user": "goethe_brasil",    "flag": "🇩🇪"},
    {"name": "Instituto Cervantes Bsb",    "user": "cervantes_brasil", "flag": "🇪🇸"},
    {"name": "British Council Brasil",     "user": "britishcouncilbr", "flag": "🇬🇧"},
    {"name": "Embaixada EUA Brasil",       "user": "embaixadaeua",     "flag": "🇺🇸"},
    {"name": "Instituto Italiano Bsb",     "user": "iicbrasilia",      "flag": "🇮🇹"},
    {"name": "Embaixada do Japão BR",      "user": "embaixadadojapao", "flag": "🇯🇵"},
    {"name": "Embaixada da França BR",     "user": "francenobrasil",   "flag": "🇫🇷"},
    {"name": "Embaixada Alemã BR",         "user": "alemanha.brasil",  "flag": "🇩🇪"},
    {"name": "Embaixada UK Brasil",        "user": "ukembassybrazil",  "flag": "🇬🇧"},
]

# ── Detecção de preço ─────────────────────────────────────────────────────────
FREE_RE = re.compile(
    r"\bgratu[ií]t[ao]s?\b|\bfree\b|\bentrada\s+franca\b|\bsem\s+cobran[çc]a\b|\blivre\b",
    re.IGNORECASE,
)
PAID_RE = re.compile(
    r"\bingressos?\b|\bpago\b|\bpaid\b|\btickets?\b|\br\$\s*\d|\bvalor\b|\bcompre\b|\bcomprar\b",
    re.IGNORECASE,
)

def classify_price(text: str) -> str:
    has_free = bool(FREE_RE.search(text))
    has_paid = bool(PAID_RE.search(text))
    if has_free and not has_paid:
        return "✅ Gratuito"
    if has_paid and not has_free:
        return "💰 Pago"
    if has_free and has_paid:
        return "🎟️ Verificar preço"
    return "❓ Não informado"


# ── HTML Parser simples ───────────────────────────────────────────────────────
class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "head"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "head"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self.chunks.append(text)

    def get_text(self):
        return " ".join(self.chunks)


def fetch_url(url: str, timeout: int = 15) -> str:
    """Baixa uma página e retorna o texto limpo."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        parser = TextExtractor()
        parser.feed(raw)
        return parser.get_text()
    except Exception as e:
        print(f"  Erro ao acessar {url}: {e}")
        return ""


# ── Extrai trechos com palavras-chave de eventos ──────────────────────────────
EVENT_RE = re.compile(
    r".{0,120}(exposi[çc][ãa]o|concerto|show|palestra|workshop|semin[aá]rio|"
    r"festival|exibi[çc][ãa]o|cinema|teatro|dan[çc]a|m[úu]sica|cultura|evento|"
    r"inaugura[çc][ãa]o|leitura|sarau).{0,200}",
    re.IGNORECASE,
)

def extract_event_snippets(text: str, max_snippets: int = 5) -> list[str]:
    matches = EVENT_RE.findall(text)
    seen = set()
    result = []
    for m in matches:
        clean = re.sub(r"\s+", " ", m).strip()
        key = clean[:60].lower()
        if key not in seen:
            seen.add(key)
            result.append(clean)
        if len(result) >= max_snippets:
            break
    return result


# ── Scraping dos sites oficiais ───────────────────────────────────────────────
def scrape_websites() -> list[dict]:
    events = []
    for src in EMBASSY_PAGES:
        print(f"  Acessando site: {src['name']}")
        text = fetch_url(src["url"])
        if not text:
            continue
        snippets = extract_event_snippets(text)
        if snippets:
            for snippet in snippets:
                events.append({
                    "source": f"{src['flag']} {src['name']}",
                    "title": snippet[:180],
                    "price": classify_price(snippet),
                    "url": src["url"],
                    "channel": "🌐 Site oficial",
                })
        else:
            # Mesmo sem evento explícito, registra que o site foi verificado
            events.append({
                "source": f"{src['flag']} {src['name']}",
                "title": "Sem eventos com palavras-chave encontrados — acesse o site para conferir",
                "price": "❓ Não informado",
                "url": src["url"],
                "channel": "🌐 Site oficial",
            })
    return events


# ── Scraping do Instagram (via instaloader) ───────────────────────────────────
def scrape_instagram() -> list[dict]:
    try:
        import instaloader
    except ImportError:
        print("  instaloader não instalado — pulando Instagram")
        return []

    events = []
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        quiet=True,
    )

    cutoff = datetime.datetime.now() - datetime.timedelta(days=10)

    for profile_info in INSTAGRAM_PROFILES:
        username = profile_info["user"]
        print(f"  Instagram: @{username}")
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            for post in profile.get_posts():
                if post.date_local < cutoff:
                    break
                caption = post.caption or ""
                snippets = extract_event_snippets(caption, max_snippets=2)
                if snippets:
                    for snippet in snippets:
                        events.append({
                            "source": f"{profile_info['flag']} {profile_info['name']}",
                            "title": snippet[:180],
                            "price": classify_price(caption),
                            "url": f"https://www.instagram.com/{username}/",
                            "channel": "📸 Instagram",
                        })
        except Exception as e:
            print(f"    Erro @{username}: {e}")
            continue

    return events


# ── Monta o e-mail HTML ───────────────────────────────────────────────────────
def build_html(web_events: list[dict], ig_events: list[dict]) -> str:
    today = datetime.date.today().strftime("%d/%m/%Y")

    def make_rows(items):
        if not items:
            return '<tr><td colspan="4" style="padding:16px;text-align:center;color:#888">Nenhum resultado encontrado.</td></tr>'
        rows = ""
        for ev in items:
            rows += f"""
            <tr>
              <td style="padding:8px;border-bottom:1px solid #eee">{ev['source']}</td>
              <td style="padding:8px;border-bottom:1px solid #eee">{ev['title']}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap">{ev['price']}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;font-size:12px">
                <a href="{ev['url']}">{ev['channel']}</a>
              </td>
            </tr>"""
        return rows

    table_header = """
      <thead>
        <tr style="background:#1a3c6e;color:#fff">
          <th style="padding:10px;text-align:left">Embaixada / Instituto</th>
          <th style="padding:10px;text-align:left">Evento / Descrição</th>
          <th style="padding:10px;text-align:left">Preço</th>
          <th style="padding:10px;text-align:left">Fonte</th>
        </tr>
      </thead>"""

    web_rows = make_rows(web_events)
    ig_rows  = make_rows(ig_events)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:860px;margin:auto;padding:24px">

  <h2 style="color:#1a3c6e">🌍 Eventos Culturais — Embaixadas e Consulados em Brasília</h2>
  <p style="color:#555">Varredura realizada em <strong>{today}</strong>. Próxima em 5 dias.</p>

  <h3 style="color:#1a3c6e;margin-top:28px">🌐 Sites Oficiais</h3>
  <table width="100%" cellspacing="0" style="border-collapse:collapse">
    {table_header}
    <tbody>{web_rows}</tbody>
  </table>

  <h3 style="color:#1a3c6e;margin-top:36px">📸 Instagram</h3>
  <table width="100%" cellspacing="0" style="border-collapse:collapse">
    {table_header}
    <tbody>{ig_rows}</tbody>
  </table>

  <hr style="margin-top:32px">
  <p style="font-size:11px;color:#aaa">
    Fontes monitoradas: Institut Français, Goethe-Institut, Instituto Cervantes, British Council,
    Instituto Italiano, Embaixada dos EUA, Embaixada do Japão, Embaixada do Reino Unido,
    Embaixada da França, Embaixada da Alemanha — Brasília/DF.
  </p>
</body>
</html>"""


# ── Envio do e-mail ───────────────────────────────────────────────────────────
def send_email(html: str, total: int):
    sender    = os.environ["GMAIL_USER"]
    password  = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("EMAIL_TO", sender)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌍 Eventos Culturais — Embaixadas Brasília ({datetime.date.today().strftime('%d/%m/%Y')}) — {total} resultado(s)"
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
    print(f"✅ E-mail enviado para {recipient} com {total} resultado(s).")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Embassy Events Scraper — Brasília ===")

    print("\n[1/2] Buscando nos sites oficiais...")
    web_events = scrape_websites()
    print(f"      {len(web_events)} resultado(s) nos sites.")

    print("\n[2/2] Buscando no Instagram...")
    ig_events = scrape_instagram()
    print(f"      {len(ig_events)} resultado(s) no Instagram.")

    total = len(web_events) + len(ig_events)
    print(f"\nTotal: {total} resultado(s). Enviando e-mail...")
    html = build_html(web_events, ig_events)
    send_email(html, total)
