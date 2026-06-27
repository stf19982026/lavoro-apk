#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rassegna Normativa Lavoro — app mobile (Flet) per APK Android
=============================================================
Riusa core_lavoro.py (fonti + scraper).
Test su desktop:  flet run
Build APK:        flet build apk   (richiede Flutter + Android SDK)

Limite onesto su Android: l'aggiornamento automatico vale mentre l'app è in
primo piano; refresh in background + notifiche richiedono un foreground
service nativo (non incluso). Verificato con Flet 0.85; se usi una versione
diversa qualche nome dell'API potrebbe cambiare.
"""

import threading
import time
import datetime as dt

import flet as ft
import core_lavoro as core

PAPER = "#f4f1ea"
CARD = "#ffffff"
INK = "#1b2233"
INK_SOFT = "#5a6276"
LINE = "#e3ddd0"
INTERVALLO_MIN = 10


def _ic(name):
    I = getattr(ft, "Icons", None) or getattr(ft, "icons", None)
    return getattr(I, name, name.lower())


def border_all(color, w=1):
    s = ft.BorderSide(w, color)
    return ft.Border(left=s, top=s, right=s, bottom=s)


def main(page: ft.Page):
    page.title = "Rassegna Normativa Lavoro"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = PAPER
    page.padding = 0

    stato = {"items": [], "off": set(), "term": "", "sort": "desc", "loading": False}
    nuovi_uid = set()

    def carica_visti():
        try:
            v = page.client_storage.get("visti")
            return set(v) if v else set()
        except Exception:
            return set()

    def salva_visti(uids):
        try:
            page.client_storage.set("visti", list(uids))
        except Exception:
            pass

    search = ft.TextField(hint_text="Cerca…", dense=True, filled=True, bgcolor=CARD,
                          border_radius=10, border_color=LINE, content_padding=12,
                          on_change=lambda e: (stato.update(term=e.control.value or ""), render()))
    sort = ft.Dropdown(width=160, dense=True, value="desc",
                       options=[ft.dropdown.Option("desc", "Più recenti"),
                                ft.dropdown.Option("asc", "Meno recenti")],
                       on_change=lambda e: (stato.update(sort=e.control.value), render()))
    chips_row = ft.Row(wrap=True, spacing=6, run_spacing=6)
    lista = ft.ListView(expand=True, spacing=9, padding=12)
    status = ft.Text("", size=11, color=INK_SOFT)
    refresh_btn = ft.IconButton(_ic("REFRESH"), tooltip="Aggiorna",
                                on_click=lambda e: refresh())

    page.appbar = ft.AppBar(
        title=ft.Text("Rassegna normativa", weight=ft.FontWeight.BOLD, color=INK),
        bgcolor="#fbfaf6", color=INK, actions=[refresh_btn])

    def enti_presenti():
        enti = []
        for it in stato["items"]:
            if it["ente"] not in [e[0] for e in enti]:
                enti.append((it["ente"], it["color"]))
        return enti

    def set_all(val):
        stato["off"] = set() if val else {e for e, _ in enti_presenti()}
        build_chips(); render()

    def toggle(ente):
        stato["off"].discard(ente) if ente in stato["off"] else stato["off"].add(ente)
        build_chips(); render()

    def build_chips():
        controls = [ft.TextButton("Tutte", on_click=lambda e: set_all(True)),
                    ft.TextButton("Nessuna", on_click=lambda e: set_all(False))]
        for ente, color in enti_presenti():
            controls.append(ft.Chip(
                label=ft.Text(ente, size=12), bgcolor=CARD, selected_color=color,
                selected=(ente not in stato["off"]), show_checkmark=False,
                on_select=lambda e, en=ente: toggle(en)))
        chips_row.controls = controls
        page.update()

    def card(it):
        badge = ft.Container(
            ft.Text(it["code"], size=10, color="white", weight=ft.FontWeight.BOLD),
            bgcolor=it["color"], padding=ft.Padding(left=6, top=2, right=6, bottom=2),
            border_radius=4)
        nuovo = ft.Container(
            ft.Text("NUOVO", size=9, color="white", weight=ft.FontWeight.BOLD),
            bgcolor="#b0306a", padding=ft.Padding(left=6, top=1, right=6, bottom=1),
            border_radius=5, visible=it["uid"] in nuovi_uid)
        top = ft.Row(
            [ft.Row([badge, ft.Text(it["categoria"], size=11, color=INK_SOFT)], spacing=6),
             ft.Row([ft.Text(it["data_label"], size=11, color=INK_SOFT), nuovo], spacing=6)],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        col = [top, ft.Text(it["titolo"], size=15, weight=ft.FontWeight.W_600, color=INK)]
        if it["summary"]:
            col.append(ft.Text(it["summary"], size=13, color=INK_SOFT))
        return ft.Container(
            content=ft.Column(col, spacing=5), bgcolor=CARD,
            border=border_all(LINE), border_radius=11, padding=14, ink=True,
            on_click=(lambda e, u=it["url"]: page.launch_url(u)) if it["url"] else None)

    def render():
        term = stato["term"].strip().lower()
        rows = []
        for it in stato["items"]:
            if it["ente"] in stato["off"]:
                continue
            if term:
                blob = (it["titolo"] + " " + it["ente"] + " " + it["categoria"] + " " + it["summary"]).lower()
                if term not in blob:
                    continue
            rows.append(it)
        rows.sort(key=lambda x: x["data_sort"], reverse=(stato["sort"] == "desc"))
        if rows:
            lista.controls = [card(it) for it in rows[:300]]
        else:
            lista.controls = [ft.Container(
                ft.Text("Nessun documento corrisponde ai filtri.", color=INK_SOFT,
                        text_align=ft.TextAlign.CENTER), padding=30)]
        status.value = "{} documenti · aggiornato {}".format(
            len(stato["items"]), dt.datetime.now().strftime("%d/%m/%Y %H:%M"))
        page.update()

    def refresh():
        if stato["loading"]:
            return
        stato["loading"] = True
        refresh_btn.icon = _ic("HOURGLASS_EMPTY")
        page.update()
        threading.Thread(target=_worker, daemon=True).start()

    def _worker():
        nonlocal nuovi_uid
        try:
            items = core.raccogli()
        except Exception:
            items = stato["items"]
        visti = carica_visti()
        nuovi_uid = {it["uid"] for it in items if it["uid"] not in visti} if visti else set()
        salva_visti({it["uid"] for it in items} | visti)
        stato["items"] = items
        stato["loading"] = False
        refresh_btn.icon = _ic("REFRESH")
        build_chips()
        render()

    def loop_auto():
        while True:
            time.sleep(INTERVALLO_MIN * 60)
            refresh()

    page.add(
        ft.Container(ft.Column([search, ft.Row([sort], spacing=8), chips_row], spacing=8),
                    padding=ft.Padding(left=12, top=8, right=12, bottom=4)),
        ft.Divider(height=1, color=LINE),
        lista,
        ft.Container(status, padding=ft.Padding(left=14, top=6, right=14, bottom=6)))

    refresh()
    threading.Thread(target=loop_auto, daemon=True).start()


if __name__ == "__main__":
    ft.app(target=main)
