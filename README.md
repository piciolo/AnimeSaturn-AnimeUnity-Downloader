<p align="center">
  <img src="assets/logo.png" width="110" alt="AnimeSaturn · AnimeUnity Downloader">
</p>

<h1 align="center">AnimeSaturn · AnimeUnity Downloader</h1>

<p align="center">
  App <b>desktop</b> per cercare, guardare e scaricare anime da
  <a href="https://www.animesaturn.net">AnimeSaturn</a> e
  <a href="https://www.animeunity.co">AnimeUnity</a> — tutto a click,
  <b>senza terminale e senza comandi Python</b>.
</p>

<p align="center">
  <sub><i>A desktop GUI to search, stream and download anime episodes from AnimeSaturn and AnimeUnity — no command line, Windows <code>.exe</code> included.</i></sub>
</p>

<p align="center">
  <sub>
    <b>I due progetti separati sono stati unificati qui.</b> L'app dedicata ad AnimeUnity
    (<a href="https://github.com/piciolo/AnimeUnityDownloader">AnimeUnityDownloader</a>,
    ora in sola lettura) vive dentro questa: un programma solo, due portali.<br>
    Esiste anche la <a href="https://github.com/piciolo/animesaturn-apk-">versione per
    Android e Android TV</a>, che condivide con questa i preferiti e il punto di ripresa.
  </sub>
</p>

---

## 📸 Anteprima

<p align="center">
  <img src="assets/screenshot-catalogo.png" width="100%" alt="Catalogo, ricerca e navigazione">
</p>

<p align="center">
  <img src="assets/screenshot-suggerimenti.png" width="100%" alt="Suggerimenti dei titoli mentre scrivi">
</p>

<p align="center">
  <img src="assets/screenshot-filtri.png" width="49%" alt="Filtro avanzato a selezione multipla">
  &nbsp;
  <img src="assets/screenshot-episodi.png" width="49%" alt="Scheda anime con lista episodi">
</p>

<p align="center">
  <img src="assets/screenshot-player.png" width="82%" alt="Anteprima in streaming integrata">
</p>

<p align="center">
  <img src="assets/screenshot-continua.png" width="100%" alt="Continua a guardare: riprendi da dove eri rimasto">
</p>

## ✨ Caratteristiche

- 🌐 **Due portali, un'app sola.** All'avvio scegli dove guardare — **AnimeSaturn** o
  **AnimeUnity**. Puoi ricordare la scelta e cambiarla quando vuoi dal pulsante 🌐 in
  alto, senza riavviare. Catalogo, ricerca, preferiti e *continua a guardare* mostrano
  il portale scelto; le voci dell'altro **non vengono toccate** e tornano in elenco
  appena ci torni.
- 🧭 **Se un portale cambia indirizzo, l'app lo segue da sola.** L'elenco dei domini è
  pubblicato online e viene letto all'avvio; se non si raggiunge valgono gli indirizzi
  di ricambio inclusi nell'app. Un trasloco del sito non richiede un aggiornamento.
- 🔁 **Ripiego fra portali**: un episodio che il suo portale non riesce a servire viene
  cercato sull'altro per titolo, senza chiedere nulla.
- ⭐ **Preferiti** e **cronologia** sincronizzabili con l'app Android: quello che guardi
  sul telefono lo riprendi sul PC, e viceversa.
- 🔎 **Ricerca** anime per titolo, collegata direttamente al sito.
- 💡 **Suggerimenti mentre scrivi**: la barra propone i titoli man mano che digiti;
  clicca un suggerimento per aprire **subito** la scheda dell'anime.
- 🗂️ **Navigazione** come sul sito: *Archivio*, *Anime in corso*, *Ultimi aggiunti*.
- 🎛️ **Filtro avanzato a selezione multipla** (come sul sito): combina più **generi**,
  **tipi** (Serie TV / Film / OVA / Special / ONA), **stati**, **stagioni**, **lingue**
  e **anni**, con **ordinamento** (rilevanza, ultime aggiunte, A–Z, Z–A, meno recenti).
- 🇮🇹 Filtro **Sub/Dub**: tutti, solo **doppiati (ITA)** o solo **sottotitolati**.
- 📺 Scheda anime con **trama, copertina e lista episodi**.
- ▶️ **Anteprima in streaming**: guarda l'episodio **dentro l'app** (player integrato con
  play/pausa, avanzamento, volume, schermo intero) per capire se ti piace **prima** di
  scaricarlo — *doppio clic* su un episodio o pulsante **👁 Anteprima**; dal player puoi
  anche scaricarlo con un clic.
- ⏯️ **Continua a guardare**: l'app ricorda dove eri arrivato — anime, *episodio 2 di 5*
  e il **minuto** — e **riprende da lì**, sia in streaming sia dai file scaricati; a fine
  episodio passa automaticamente al successivo.
- 📁 **Libreria con player interno**: vedi tutti gli episodi che hai **scaricato** e li
  riproduci nell'app, riprendendo dal punto in cui eri.
- ✅ Selezione episodi: **singoli**, **tutti** o **intervallo** (es. dal 5 al 12).
- 📥 **Coda di download** con barra di avanzamento, velocità, download **simultanei**
  regolabili, **annulla** immediato e **cartella personalizzabile**.
- ⏯️ **Ripresa dei download interrotti**: se un download viene interrotto, riparte da
  dove si era fermato invece che da capo. Nella lista episodi vedi quali sono già
  scaricati (✓) e quali sono da completare (⏸).
- 💾 File salvati in modo ordinato: `Nome Anime - Ep 01.mp4`.

## ⬇️ Installazione e avvio

### Modo più semplice — eseguibile (consigliato)

1. Vai alla pagina **[Releases](https://github.com/piciolo/AnimeSaturn-AnimeUnity-Downloader/releases/latest)**
   e scarica il file `.exe`.
2. **Doppio clic**. Fine: non serve installare Python.

> Essendo un eseguibile non firmato, Windows SmartScreen potrebbe mostrare un avviso:
> clicca **Ulteriori informazioni → Esegui comunque**. Al primo avvio l'app impiega
> qualche secondo a partire.

### Avvio con doppio clic (dal codice)

Fai doppio clic su **`Avvia AnimeSaturn.bat`** (avvia l'app senza finestra del
terminale). Richiede Python con le dipendenze installate (vedi sotto).

### Da sorgente

```bash
pip install -r requirements.txt
python app.py
```

## 🕹️ Come si usa

1. Al primo avvio **scegli il portale**: AnimeSaturn o AnimeUnity. Spunta *ricorda
   questa scelta* se non vuoi che te lo chieda ogni volta; il pulsante 🌐 in alto la
   cambia in qualsiasi momento.
2. Vedi già gli anime **In corso** del portale scelto.
3. Scrivi un titolo nella barra e premi **Invio** (o **Cerca**). Puoi cambiare
   l'ordinamento e il **Sub/Dub**, oppure aprire **🎛 Filtri** per filtrare per
   **genere, tipo, stato, stagione, lingua e anno**.
4. Clicca su una copertina per aprire la **scheda dell'anime**.
5. Spunta gli episodi desiderati. Per fare presto usa **Seleziona tutti** oppure imposta
   **Dal … al …** e premi **Seleziona intervallo**.
6. Premi **⬇ Scarica selezionati**: passi automaticamente alla scheda **Download**.
7. Nella scheda **Download** segui l'avanzamento; puoi **annullare** un download in corso
   o **rimuovere** quelli finiti, e regolare i download **simultanei**.

> I filtri sono quelli di AnimeSaturn. AnimeUnity non sa esprimerli tutti (per esempio la
> lingua originale): in quel caso l'app te lo dice, invece di mostrarti un elenco vuoto
> come se non ci fossero risultati.

## 💾 Dove finiscono i file

I video vengono salvati nella cartella di download scelta (modificabile dall'app),
dentro una sottocartella con il nome dell'anime, ad esempio:

```
<cartella scelta>/
└── The Promised Neverland/
    ├── The Promised Neverland - Ep 01.mp4
    └── The Promised Neverland - Ep 02.mp4
```

Riavviando un download già presente, l'episodio viene riconosciuto e saltato.

## 🔨 Creare l'eseguibile

Per generare tu stesso il `.exe` (serve solo la prima volta):

```bash
pip install pyinstaller
python build_exe.py
```

Al termine trovi **`dist/AnimeSaturn Downloader.exe`**: un singolo file portabile,
lanciabile con un doppio clic anche su PC senza Python.

> Per un'icona personalizzata, metti un file `assets/logo.ico` prima di lanciare
> `build_exe.py`.

## ⚙️ Come funziona (in breve)

L'app è autonoma (pacchetto `gui/` + `app.py`) e parla direttamente con i due portali.
Ognuno sta dietro la stessa interfaccia (`gui/sources/`): il resto del programma chiede i
risultati *a una sorgente*, senza sapere quale sito abbia risposto, ed è questo che ha
permesso di unire i due progetti invece di tenerne due.

**AnimeSaturn** — scraping delle pagine (il sito non espone un'API pubblica):

- ricerca/catalogo tramite la pagina `/filter` (e `/ongoing`, `/newest`);
- lista episodi estratta dalla pagina dell'anime;
- link diretto al file `.mp4` risolto dalla pagina di visione: la pagina espone un
  player firmato `play.saturncdn.net/embed/<id>`, la cui *playlist* restituisce la
  sorgente offuscata (base64 + XOR con il token) che viene decodificata nel `.mp4`.

**AnimeUnity** — endpoint JSON del sito:

- ricerca/catalogo tramite `POST /archivio/get-animes` con il token CSRF della pagina;
- lista episodi tramite `info_api`, che risponde a blocchi;
- link diretto al `.mp4` estratto dalla pagina video dell'episodio.

I download vengono eseguiti in thread separati per non bloccare l'interfaccia, con
ripresa automatica tramite richieste HTTP `Range`.

L'app Android è il **gemello** di questa: le regole che devono dare lo stesso risultato
nei due programmi (quando due risultati di portali diversi sono lo stesso anime, chi
vince fra due punti di ripresa, quali voci mostrare per un portale) stanno in file di
casi condivisi — `gui/*_vectors.json` — che entrambe eseguono nei propri test. Se una
delle due si comportasse diversamente anche su un solo caso, il test fallisce subito
invece di far divergere in silenzio i dati dell'utente.

## 📦 Requisiti

- Per l'**eseguibile**: nessuno (Windows 64 bit).
- Per l'**avvio da sorgente**: Python 3.10+ con `PySide6` e `httpx`
  (`pip install -r requirements.txt`).

## ⚠️ Note

Strumento pensato per **uso personale**. Rispetta le leggi sul diritto d'autore e i
termini di servizio del sito: scarica solo contenuti per cui hai i relativi diritti.
