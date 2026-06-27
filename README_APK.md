# Rassegna Lavoro — APK costruito nel cloud (tu non installi nessun toolchain)

GitHub compila l'APK al posto tuo e lo pubblica come file scaricabile. Sul tuo
PC/telefono non serve né Flutter né Android SDK né Termux.

## Cosa fai tu (una volta)
1. Crea un account su github.com (gratis) e un **repository PUBBLICO** chiamato
   `rassegna-apk`.
2. Carica tutti i file di questa cartella mantenendo la struttura. Per il
   workflow: *Add file → Create new file*, nome esatto
   `.github/workflows/build-apk.yml`, incolla il contenuto, *Commit*.
3. Vai sul tab **Actions**: la build parte da sola (o premi *Run workflow*).
4. Quando diventa verde (~15–25 min la prima volta), trovi l'APK in due posti:
   - tab **Actions** → run → sezione *Artifacts* → `rassegna-apk`
   - pagina **Releases** del repo → *Rassegna Lavoro — APK* → file `.apk`
5. Sul telefono apri la pagina **Releases**, scarica l'`.apk`, aprilo e installa
   (abilita "Installa da origini sconosciute" se richiesto).

## Cosa fa l'app
Come l'app desktop: elenco filtrabile per fonte (Tutte/Nessuna), ricerca,
ordinamento, titolo + breve descrizione, tap per aprire l'atto, badge NUOVO.
Aggiornamento mentre l'app è aperta.

## Note oneste
- **Non posso generare l'APK io in chat** (la filiera Android non è disponibile
  nel mio ambiente): per questo lo fa GitHub.
- **Niente notifiche/refresh in background reale**: Android li sospende; servirebbe
  un foreground service nativo (lavoro a parte).
- **La prima build potrebbe fallire** per piccole divergenze di versione della
  filiera (`flet build` evolve): il log verbose dice cosa sistemare. Se capita,
  incolla l'errore e te lo correggo.
- Se vuoi "tocca e funziona" senza alcun apk, la **PWA su GitHub Pages** che ti
  ho già dato è di fatto un'app, a zero compilazione.
