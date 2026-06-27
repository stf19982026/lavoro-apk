#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notifiche push via ntfy.sh — gira nel cloud (GitHub Actions), non sul telefono.
Controlla le fonti, e per ogni NOVITÀ manda una notifica push al tuo telefono
(app ntfy). Funziona anche con telefono bloccato e app della rassegna chiusa.

Variabile d'ambiente richiesta: NTFY_TOPIC (il nome del tuo "canale" ntfy).
"""

import os
import json
import urllib.request

import core_lavoro as core

TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
STATE = "ntfy_state.json"


def carica():
    try:
        return set(json.load(open(STATE, encoding="utf-8")))
    except Exception:
        return None


def salva(uids):
    json.dump(sorted(uids), open(STATE, "w", encoding="utf-8"))


def push(item):
    url = "https://ntfy.sh/" + TOPIC
    body = item["titolo"].encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    # Title header deve essere ASCII: uso il codice fonte (INPS/ADE/…)
    req.add_header("Title", "{} · {}".format(item["code"], item["data_label"]))
    if item.get("url"):
        req.add_header("Click", item["url"])
    req.add_header("Tags", "page_facing_up")
    urllib.request.urlopen(req, timeout=20)


def main():
    if not TOPIC:
        print("NTFY_TOPIC non impostato: salto.")
        return
    items = core.raccogli()
    seen = carica()
    uids = {it["uid"] for it in items}
    if seen is None:
        salva(uids)
        print("Baseline creata ({} doc). Nessuna notifica al primo giro.".format(len(items)))
        return
    nuovi = [it for it in items if it["uid"] not in seen]
    inviate = 0
    for it in nuovi[:25]:
        try:
            push(it)
            inviate += 1
        except Exception as ex:
            print("push KO:", ex)
    salva(uids | seen)
    print("Novità: {} · push inviate: {}".format(len(nuovi), inviate))


if __name__ == "__main__":
    main()
