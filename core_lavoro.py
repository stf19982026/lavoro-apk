#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core_lavoro — strato dati condiviso (nessuna GUI, nessun pip a runtime)
======================================================================
Fonti + scraper + raccogli(): riusato da app desktop, generatore web/PWA
e app mobile (Flet/Kivy). Dipendenze (puro-Python, impacchettabili in APK):
requests, beautifulsoup4 (puro-Python, con wheel).
"""

import re
import json
import datetime as dt
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import ssl
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.ssl_ import create_urllib3_context
except Exception:
    create_urllib3_context = None


def gnews(query):
    return ("https://news.google.com/rss/search?q="
            + quote_plus(query) + "&hl=it&gl=IT&ceid=IT:it")


SOURCES = [
    {"id": "inps-circolari", "ente": "INPS", "code": "INPS", "categoria": "Circolari",
     "tipo": "rss", "url": "https://www.inps.it/it/it.rss.circolari.xml", "color": "#0a7d4d"},
    {"id": "inps-messaggi", "ente": "INPS", "code": "INPS", "categoria": "Messaggi",
     "tipo": "rss", "url": "https://www.inps.it/it/it.rss.messaggi.xml", "color": "#0a7d4d"},
    {"id": "ade-prassi", "ente": "Agenzia Entrate", "code": "ADE", "categoria": "Normativa e prassi",
     "tipo": "rss",
     "url": "https://www.agenziaentrate.gov.it/portale/c/portal/rss/entrate?idrss=0753fcb1-1a42-4f8c-f40d-02793c6aefb4",
     "color": "#154a8f"},
    {"id": "ade-news", "ente": "Agenzia Entrate", "code": "ADE", "categoria": "News",
     "tipo": "rss",
     "url": "https://www.agenziaentrate.gov.it/portale/c/portal/rss/entrate?idrss=79b071d0-a537-4a3d-86cc-7a7d5a36f2a9",
     "color": "#154a8f"},
    {"id": "inl-circolari", "ente": "INL", "code": "INL", "categoria": "Circolari",
     "tipo": "scrape_inl",
     "url": "https://www.ispettorato.gov.it/documenti-e-normativa/orientamenti-giuridici-inl/circolari/",
     "color": "#6b2f8c"},
    {"id": "inl-note", "ente": "INL", "code": "INL", "categoria": "Note e pareri",
     "tipo": "scrape_inl",
     "url": "https://www.ispettorato.gov.it/documenti-e-normativa/orientamenti-giuridici-inl/note-e-pareri/",
     "color": "#6b2f8c"},
    {"id": "inail-circolari", "ente": "INAIL", "code": "INAIL", "categoria": "Circolari",
     "tipo": "scrape_inail",
     "url": "https://www.inail.it/portale/it/atti-e-documenti/note-provvedimenti-e-istruzioni-operative/normativa-circolari-inail.html",
     "color": "#b5451f"},
    {"id": "dpl-news", "ente": "Diritto del Lavoro", "code": "CCNL", "categoria": "Approfondimenti / CCNL",
     "tipo": "rss", "url": "https://www.dottrinalavoro.it/feed", "color": "#9a6a16"},
    {"id": "assimpredil-normative", "ente": "Assimpredil ANCE", "code": "ANCE",
     "categoria": "Novità normative", "tipo": "scrape_assimpredil",
     "url": "https://portale.assimpredilance.it/categorie/novita-normative", "color": "#b91c1c"},
]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"),
    "Accept-Language": "it-IT,it;q=0.9",
}
TIMEOUT = 20


class _TLSAdapter(HTTPAdapter):
    """Abbassa il security level TLS: serve per il portale INAIL, che con il
    livello di default dà 'SSLV3_ALERT_HANDSHAKE_FAILURE'."""
    def init_poolmanager(self, *args, **kwargs):
        if create_urllib3_context is not None:
            try:
                ctx = create_urllib3_context(ciphers="DEFAULT@SECLEVEL=1")
                ctx.check_hostname = True
                kwargs["ssl_context"] = ctx
            except Exception:
                pass
        return super().init_poolmanager(*args, **kwargs)


def _make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.mount("https://", _TLSAdapter())
    except Exception:
        pass
    return s


SESSION = _make_session()
MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
        "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}
MESI_ABBR = {"gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
             "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12}


def parse_data_iso(s):
    if not isinstance(s, str):
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def parse_data_estesa(testo):
    if not testo:
        return None
    t = testo.lower()
    m = re.search(r"(\d{1,2})\s+([a-zà]+)\s+(\d{4})", t)
    if m and m.group(2) in MESI:
        try:
            return dt.datetime(int(m.group(3)), MESI[m.group(2)], int(m.group(1)))
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})[/\-]([a-z]{3})[/\-](\d{4})", t)
    if m and m.group(2) in MESI_ABBR:
        try:
            return dt.datetime(int(m.group(3)), MESI_ABBR[m.group(2)], int(m.group(1)))
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", t)
    if m:
        try:
            return dt.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None



def ripulisci(testo, limite=240):
    testo = re.sub(r"<[^>]+>", "", testo or "")
    testo = re.sub(r"\s+", " ", testo).strip()
    if len(testo) > limite:
        testo = testo[:limite].rsplit(" ", 1)[0] + "…"
    return testo


ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"


def _txt(el):
    return (el.text or "").strip() if el is not None else ""


def _data_feed(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
        if d:
            return d.replace(tzinfo=None)
    except Exception:
        pass
    return parse_data_iso(s)


def fetch_rss(src):
    """Legge RSS 2.0 o Atom con la libreria standard (niente feedparser)."""
    try:
        r = SESSION.get(src["url"], timeout=TIMEOUT)
    except Exception:
        r = requests.get(src["url"], headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return []
    items = []
    rss_items = root.findall(".//item")
    if rss_items:
        for it in rss_items:
            titolo = _txt(it.find("title"))
            link = _txt(it.find("link")) or src["url"]
            desc = _txt(it.find("description"))
            pub = _txt(it.find("pubDate")) or _txt(it.find(DC + "date"))
            data = _data_feed(pub) or parse_data_estesa(titolo) or parse_data_estesa(desc)
            items.append(make_item(src, ripulisci(titolo, 200), link, data, ripulisci(desc)))
    else:
        for e in root.findall(".//" + ATOM + "entry"):
            titolo = _txt(e.find(ATOM + "title"))
            link = ""
            for l in e.findall(ATOM + "link"):
                if (l.get("rel") in (None, "alternate")) and l.get("href"):
                    link = l.get("href")
                    break
            if not link:
                le = e.find(ATOM + "link")
                link = le.get("href") if le is not None else src["url"]
            desc = _txt(e.find(ATOM + "summary")) or _txt(e.find(ATOM + "content"))
            pub = _txt(e.find(ATOM + "published")) or _txt(e.find(ATOM + "updated"))
            data = _data_feed(pub) or parse_data_estesa(titolo) or parse_data_estesa(desc)
            items.append(make_item(src, ripulisci(titolo, 200), link or src["url"], data, ripulisci(desc)))
    return items


def fetch_html(url):
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
    except Exception:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def scrape_inl(src):
    items, seen = [], set()
    soup = fetch_html(src["url"])
    main = soup.find("main") or soup
    for a in main.find_all("a", href=True):
        testo = a.get_text(" ", strip=True)
        href = a["href"]
        if not testo or len(testo) < 12:
            continue
        if not any(k in testo.lower() for k in ("circolare", "nota", "parere", "prot")):
            continue
        if href in seen:
            continue
        seen.add(href)
        data = parse_data_estesa(testo) or (parse_data_estesa(a.parent.get_text(" ", strip=True)) if a.parent else None)
        items.append(make_item(src, testo, requests.compat.urljoin(src["url"], href), data, ""))
    return items[:40]


def _oggetto_inail(a, next_a):
    """Oggetto = testo tra il link-titolo e la circolare successiva."""
    from bs4 import NavigableString, Tag
    own = {id(x) for x in a.descendants}
    parts, tot = [], 0
    for el in a.next_elements:
        if id(el) in own:
            continue
        if next_a is not None and el is next_a:
            break
        if isinstance(el, Tag) and el.name == "a" \
                and "circolare inail" in el.get_text(" ", strip=True).lower():
            break
        if isinstance(el, NavigableString):
            t = str(el).strip()
            if t:
                parts.append(t)
                tot += len(t)
                if tot > 500:
                    break
    testo = " ".join(parts)
    testo = re.sub(r"circolare inail", " ", testo, flags=re.I)
    testo = re.sub(r"\d{1,2}\s+[a-z\u00e0]+\s+\d{4}", " ", testo, flags=re.I)
    testo = re.sub(r"\d{1,2}\s+[a-z]{3}\.?\s+\d{4}", " ", testo, flags=re.I)
    testo = re.sub(r"^\W*n\.\s*\d+\W*", " ", testo)
    testo = ripulisci(testo, 280).strip(" \u00b7-\u2014.,")
    return testo if len(testo) > 12 else ""


def scrape_inail(src):
    """Circolari INAIL dalla pagina indicata (via SESSION, TLS abbassato):
    titolo, data dal titolo, link al dettaglio e breve oggetto."""
    items, seen = [], set()
    soup = fetch_html(src["url"])
    links = []
    for a in soup.find_all("a", href=True):
        t = a.get_text(" ", strip=True)
        if "circolare inail" in t.lower() and parse_data_estesa(t):
            links.append(a)
    for i, a in enumerate(links):
        titolo = ripulisci(a.get_text(" ", strip=True), 200)
        full = requests.compat.urljoin(src["url"], a["href"])
        if full in seen:
            continue
        seen.add(full)
        data = parse_data_estesa(titolo)
        next_a = links[i + 1] if i + 1 < len(links) else None
        oggetto = _oggetto_inail(a, next_a)
        items.append(make_item(src, titolo, full, data, oggetto))
    return items[:80]


def scrape_assimpredil(src):
    items, seen = [], set()
    soup = fetch_html(src["url"])
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/articoli/" not in href or "/tag/" in href:
            continue
        titolo = a.get_text(" ", strip=True)
        if not titolo or len(titolo) < 8:
            continue
        full = requests.compat.urljoin(src["url"], href)
        if full in seen:
            continue
        seen.add(full)
        blocco = a.find_parent(["li", "article", "div"])
        btxt = blocco.get_text(" ", strip=True) if blocco else titolo
        mdata = re.search(r"\d{1,2}/[a-z]{3}/\d{4}", btxt.lower())
        data = parse_data_estesa(mdata.group(0)) if mdata else parse_data_estesa(btxt)
        teaser = ""
        if blocco:
            p = blocco.find("p")
            if p:
                teaser = ripulisci(p.get_text(" ", strip=True))
        items.append(make_item(src, titolo, full, data, teaser))
    return items[:40]


def make_item(src, titolo, url, data, summary):
    titolo = ripulisci(titolo, 220) or "(senza titolo)"
    return {
        "uid": url or titolo,
        "ente": src["ente"], "code": src["code"], "categoria": src["categoria"],
        "color": src["color"], "titolo": titolo, "url": url or "",
        "data_label": data.strftime("%d/%m/%Y") if data else "—",
        "data_sort": data.strftime("%Y%m%d") if data else "00000000",
        "summary": summary or "",
    }


FETCHERS = {"rss": fetch_rss, "scrape_inl": scrape_inl, "scrape_inail": scrape_inail,
            "scrape_assimpredil": scrape_assimpredil}


def raccogli(giorni=None, on_log=None):
    tutti = []
    soglia = dt.datetime.now() - dt.timedelta(days=giorni) if giorni else None
    for src in SOURCES:
        try:
            items = FETCHERS[src["tipo"]](src)
            if soglia:
                items = [it for it in items if it["data_sort"] == "00000000"
                         or dt.datetime.strptime(it["data_sort"], "%Y%m%d") >= soglia]
            tutti.extend(items)
            if on_log:
                on_log("[OK] {} · {}: {}".format(src["ente"], src["categoria"], len(items)))
        except Exception as ex:
            if on_log:
                on_log("[SKIP] {} · {}: {}".format(src["ente"], src["categoria"], ex))
    visti, puliti = set(), []
    for it in tutti:
        if it["uid"] not in visti:
            visti.add(it["uid"])
            puliti.append(it)
    puliti.sort(key=lambda x: x["data_sort"], reverse=True)
    return puliti
