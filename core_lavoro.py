#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core_lavoro — strato dati condiviso (nessuna GUI, nessun pip a runtime)
======================================================================
Fonti + scraper + raccogli(): riusato da app desktop, generatore web/PWA
e app mobile (Flet/Kivy). Dipendenze (puro-Python, impacchettabili in APK):
feedparser, requests, beautifulsoup4.
"""

import re
import json
import datetime as dt
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup


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
    {"id": "ntplus-lavoro", "ente": "NT+ Lavoro", "code": "NT+", "categoria": "Prima pagina",
     "tipo": "scrape_ntplus", "url": "https://ntpluslavoro.ilsole24ore.com/", "color": "#b0306a"},
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


def da_struct_time(st):
    if not st:
        return None
    try:
        return dt.datetime(*st[:6])
    except (TypeError, ValueError):
        return None


def ripulisci(testo, limite=240):
    testo = re.sub(r"<[^>]+>", "", testo or "")
    testo = re.sub(r"\s+", " ", testo).strip()
    if len(testo) > limite:
        testo = testo[:limite].rsplit(" ", 1)[0] + "…"
    return testo


def fetch_rss(src):
    items = []
    feed = feedparser.parse(src["url"], request_headers=HEADERS)
    if not feed.entries and getattr(feed, "status", 200) >= 400:
        raise RuntimeError("HTTP {}".format(feed.status))
    for e in feed.entries:
        data = da_struct_time(getattr(e, "published_parsed", None)) \
            or da_struct_time(getattr(e, "updated_parsed", None)) \
            or parse_data_estesa(getattr(e, "title", "")) \
            or parse_data_estesa(getattr(e, "summary", ""))
        items.append(make_item(src, ripulisci(getattr(e, "title", ""), 200),
                               getattr(e, "link", src["url"]), data,
                               ripulisci(getattr(e, "summary", ""))))
    return items


def fetch_html(url):
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


def scrape_inail(src):
    items, seen = [], set()
    soup = fetch_html(src["url"])
    main = soup.find("main") or soup
    blocchi = main.find_all(["article", "li"]) or main.find_all("div")
    for b in blocchi:
        testo = b.get_text(" ", strip=True)
        if "circolare" not in testo.lower():
            continue
        data = parse_data_estesa(testo)
        a = b.find("a", href=True)
        link = requests.compat.urljoin(src["url"], a["href"]) if a else src["url"]
        oggetto = re.sub(r"circolare inail", "", testo, flags=re.I)
        oggetto = re.sub(r"\d{1,2}\s+[a-zà]+\s+\d{4}", "", oggetto, flags=re.I).strip(" ·-")
        oggetto = ripulisci(oggetto, 280) or "Circolare INAIL"
        if oggetto[:60] in seen:
            continue
        seen.add(oggetto[:60])
        items.append(make_item(src, oggetto, link, data, ""))
    return items[:40]


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


def _next_data_articoli(obj, out):
    if isinstance(obj, dict):
        titolo = obj.get("title") or obj.get("titolo") or obj.get("headline")
        slug = (obj.get("url") or obj.get("urlId") or obj.get("slug")
                or obj.get("link") or obj.get("permalink") or obj.get("id"))
        if isinstance(titolo, str) and isinstance(slug, str) and len(titolo) > 8:
            url = slug if slug.startswith("http") else \
                "https://ntpluslavoro.ilsole24ore.com/art/" + slug.strip("/").split("/")[-1]
            data = None
            for k in ("datePublished", "dataPub", "date", "data", "pubDate", "dataPubblicazione", "publishedAt"):
                data = parse_data_iso(obj.get(k)) or parse_data_estesa(str(obj.get(k) or ""))
                if data:
                    break
            summ = (obj.get("abstract") or obj.get("summary") or obj.get("sommario")
                    or obj.get("occhiello") or obj.get("description") or obj.get("strillo") or "")
            out.append((titolo.strip(), url, data, ripulisci(str(summ))))
        for v in obj.values():
            _next_data_articoli(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _next_data_articoli(v, out)


def scrape_ntplus(src):
    r = requests.get(src["url"], headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    testo = r.text
    trovati = []
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', testo, re.S)
    if m:
        try:
            _next_data_articoli(json.loads(m.group(1)), trovati)
        except Exception:
            pass
    if not trovati:
        soup = BeautifulSoup(testo, "html.parser")
        for a in soup.find_all("a", href=True):
            if "/art/" not in a["href"]:
                continue
            titolo = a.get_text(" ", strip=True)
            if titolo and len(titolo) > 10:
                trovati.append((titolo, requests.compat.urljoin(src["url"], a["href"]), None, ""))
    items, seen = [], set()
    for titolo, url, data, summ in trovati:
        if url in seen:
            continue
        seen.add(url)
        items.append(make_item(src, titolo, url, data, summ))
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
            "scrape_assimpredil": scrape_assimpredil, "scrape_ntplus": scrape_ntplus}


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
