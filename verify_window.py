# -*- coding: utf-8 -*-
"""Costruisce la finestra vera e conta le righe che finiscono negli elenchi.

Nasce da un difetto arrivato fino all'utente: ``recent()`` chiamava ``_to_float`` senza
averlo importato, quindi sollevava un ``NameError`` a ogni chiamata e la scheda
«Continua» restava vuota per sempre. Nessuna voce era andata perduta -- l'elenco non
veniva mai costruito.

Nessuna delle prove esistenti lo vide, e la ragione merita di stare scritta qui: tutte
giravano **accanto** al codice invece che attraverso. Quelle sull'ordinamento importavano
``_to_float`` da ``merge`` per conto proprio, cioe' esercitavano la funzione giusta per la
via sbagliata, e ``history.recent()`` non venne chiamata una volta. Restarono verdi
mentre la scheda era morta.

Questa invece passa dove passa l'utente: costruisce ``MainWindow``, chiede un
aggiornamento degli elenchi e **conta i widget**. Non i record, i widget: la differenza
fra i due e' esattamente il difetto che e' sfuggito.

Due isolamenti, entrambi necessari:

* **I dati** vanno in una cartella di prova (``setTestModeEnabled``), mai in quella
  dell'utente. La guardia qui sotto e' la riga piu' importante del file: se un giorno Qt
  cambiasse comportamento, senza quel controllo questa prova sovrascriverebbe la
  cronologia vera con dati finti.
* **Le preferenze** no: su Windows il modo prova di Qt **non** le reindirizza, restano nel
  registro vero (misurato). Si cambia percio' l'organizzazione in una di prova, o la
  prova leggerebbe -- e potrebbe scrivere -- le impostazioni dell'utente.

La rete viene spenta: la ricerca d'avvio e la cura del dominio hanno i loro controlli
altrove, e qui servirebbero solo a rendere lento e incerto cio' che dev'essere
deterministico.

Uso: python verify_window.py
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# I dati in una cartella di prova.
QStandardPaths.setTestModeEnabled(True)

# Le preferenze in una chiave di prova: va fatto prima che ``AppSettings`` nasca.
import gui.settings as impostazioni  # noqa: E402

impostazioni._ORG = "AnimeSaturnDownloader-verify-window"

app = QApplication(sys.argv)
app.setApplicationName("AnimeSaturn Downloader")
app.setOrganizationName("AnimeSaturnDownloader")

CARTELLA = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))

# La guardia. Non e' una formalita': e' cio' che impedisce a questa prova di distruggere
# i dati che esiste per proteggere.
if "qttest" not in CARTELLA.as_posix().lower():
    sys.exit(
        "FERMO: la cartella dei dati non sembra una cartella di prova.\n"
        f"  {CARTELLA}\n"
        "  Senza isolamento questa prova sovrascriverebbe i dati veri."
    )

ORA = time.time()
guai = 0


def sicuro(testo: str) -> str:
    """Il testo reso stampabile sulla console di questa macchina.

    Serve perche' i dettagli riportano le scritte dell'interfaccia, che contengono
    frecce e accenti: su una console cp1252 il verificatore moriva **mentre raccontava
    il fallimento**, e un controllo che non riesce a dire cos'e' andato male non serve.
    """
    codifica = getattr(sys.stdout, "encoding", None) or "ascii"
    return testo.encode(codifica, "replace").decode(codifica, "replace")


def prova(nome: str, ok: bool, dettaglio: str = "") -> None:
    global guai
    if not ok:
        guai += 1
    print("  %s %s" % ("ok  " if ok else "NO  ", sicuro(nome)))
    if not ok and dettaglio:
        print("       " + sicuro(dettaglio))


def aggiorna(finestra, metodo: str) -> bool:
    """Chiede un aggiornamento; un'eccezione diventa una prova fallita, non una morte.

    Il difetto che ha generato questo file si presentava esattamente cosi': un'eccezione
    dentro l'aggiornamento di un elenco. Riportarla come fallimento invece di morire alla
    prima permette di vedere in una sola esecuzione anche tutto il resto -- e la traccia
    resta stampata, perche' e' lei la diagnosi.
    """
    try:
        getattr(finestra, metodo)()
        return True
    except Exception:
        prova(
            "%s() non e' crollata" % metodo,
            False,
            traceback.format_exc(limit=6).strip(),
        )
        return False


def chiedi(nome: str, funzione, ripiego):
    """Legge un dato dagli archivi; un'eccezione diventa una prova fallita.

    Gemello di :func:`aggiorna` per le letture dirette. Senza questo, un archivio che
    solleva -- il caso da cui nasce il file -- interrompeva la prova a metà, e i
    controlli successivi non venivano nemmeno eseguiti.
    """
    try:
        return funzione()
    except Exception:
        prova(nome, False, traceback.format_exc(limit=6).strip())
        return ripiego


def visibile(widget) -> bool:
    """Se il codice ha mostrato questo widget, a prescindere dalla finestra.

    Non si usa ``isVisible()``: su una finestra che nessuno ha mostrato restituisce
    ``False`` per ogni figlio, quindi un controllo tipo «l'etichetta del vuoto non si
    vede» passerebbe sempre, per il motivo sbagliato -- la prima stesura di questa prova
    lo faceva. ``isHidden()`` invece riflette proprio le chiamate a ``setVisible`` che si
    vogliono misurare.
    """
    return not widget.isHidden()


def voce(chiave: str, titolo: str, portale: str | None, quando: float, **extra):
    """Un record della forma che la cronologia salva davvero."""
    record = {
        "title": titolo,
        "slug": chiave,
        "poster": "",  # vuoto di proposito: un poster vero sarebbe una richiesta di rete
        "episode_number": "3",
        "total_episodes": 12,
        "position_ms": 90_000,
        "duration_ms": 1_440_000,
        "completed": False,
        "watch_path": f"/ep/{chiave}",
        "file_path": "",
        "updated_at": quando,
    }
    if portale is not None:
        record["source_id"] = portale
    record.update(extra)
    return record


STORIA = {
    "alfa": voce("alfa", "Alfa su Saturn", "animesaturn", ORA - 10),
    "beta": voce("beta", "Beta su Saturn", "animesaturn", ORA - 20),
    # Senza ``source_id``: una voce d'epoca, di quando il portale era uno solo.
    "gamma": voce("gamma", "Gamma senza marchio", None, ORA - 30),
    "delta": voce("delta", "Delta su Unity", "animeunity", ORA - 15),
    # Una lapide: rimossa, non nascosta. Non deve comparire in nessun elenco.
    "epsilon": voce(
        "epsilon", "Epsilon rimossa", "animesaturn", ORA - 40, removed_at=ORA - 5
    ),
    # Una riga che non e' un record: un file scritto a mano non deve impedire l'avvio.
    "rotta": "non sono un dizionario",
}

PREFERITI = {
    "uno": {
        "title": "Uno su Saturn", "slug": "uno", "poster": "",
        "source_id": "animesaturn", "is_favourite": True, "toggled_at": ORA - 10,
    },
    "due": {
        "title": "Due su Unity", "slug": "due", "poster": "",
        "source_id": "animeunity", "is_favourite": True, "toggled_at": ORA - 20,
    },
    # Togliato: resta nel file per raccontarlo agli altri dispositivi, non in elenco.
    "tre": {
        "title": "Tre non piu", "slug": "tre", "poster": "",
        "source_id": "animesaturn", "is_favourite": False, "toggled_at": ORA - 5,
    },
    "rotta": 42,
}


def semina() -> None:
    if CARTELLA.exists():
        shutil.rmtree(CARTELLA, ignore_errors=True)
    CARTELLA.mkdir(parents=True, exist_ok=True)
    for nome, dati in (("history.json", STORIA), ("favorites.json", PREFERITI)):
        io.open(CARTELLA / nome, "w", encoding="utf-8").write(
            json.dumps(dati, ensure_ascii=False, indent=1)
        )


def righe_continua(finestra) -> int:
    """Le righe disegnate, senza lo spaziatore in coda."""
    return finestra.continue_layout.count() - 1


def main() -> int:
    global guai
    semina()
    print("cartella di prova: %s" % CARTELLA)

    import gui.main_window as mw
    from gui.main_window import MainWindow

    # La rete non serve a questa prova, e la renderebbe lenta e incerta.
    MainWindow._browse = lambda self, value: None
    MainWindow._heal_animeunity_domain = lambda self: None

    finestra = MainWindow(portal="animesaturn")
    # Niente nei Download dell'utente, qualunque cosa decida di scrivere.
    finestra.settings.download_dir = str(CARTELLA / "download")

    print()
    print("la scheda «Continua», su AnimeSaturn:")
    aggiorna(finestra, "_refresh_continue")
    prova(
        "tre righe disegnate: due marcate piu' la voce d'epoca",
        righe_continua(finestra) == 3,
        "righe = %d" % righe_continua(finestra),
    )
    prova(
        "l'etichetta «non stai guardando nulla» non compare",
        not visibile(finestra.continue_empty),
    )
    prova(
        "e l'avviso dice che una voce e' sull'altro portale",
        visibile(finestra.continue_outside)
        and "altro portale" in finestra.continue_outside.text(),
        "avviso = %r (mostrato=%s)"
        % (finestra.continue_outside.text()[:60], visibile(finestra.continue_outside)),
    )
    ordine = chiedi(
        "recent() risponde senza sollevare",
        lambda: [
            e.get("title") for e in finestra.history.recent(40, portal="animesaturn")
        ],
        [],
    )
    prova(
        "in ordine, la piu' recente in testa",
        ordine == ["Alfa su Saturn", "Beta su Saturn", "Gamma senza marchio"],
        "ordine = %r" % (ordine,),
    )
    prova("la lapide non compare", "Epsilon rimossa" not in ordine)

    print()
    print("passando ad AnimeUnity:")
    finestra.portal = "animeunity"
    finestra.sources.only_portal = "animeunity"
    aggiorna(finestra, "_refresh_continue")
    prova("una riga sola", righe_continua(finestra) == 1,
          "righe = %d" % righe_continua(finestra))
    prova(
        "e l'avviso ne conta tre sull'altro portale",
        "3" in finestra.continue_outside.text(),
        "avviso = %r" % finestra.continue_outside.text()[:60],
    )

    print()
    print("senza scelta di portale:")
    finestra.portal = None
    finestra.sources.only_portal = None
    aggiorna(finestra, "_refresh_continue")
    prova("tutte e quattro", righe_continua(finestra) == 4,
          "righe = %d" % righe_continua(finestra))
    prova("e nessun avviso, perche' non c'e' niente fuori",
          not visibile(finestra.continue_outside))

    print()
    print("un portale rimasto senza voci:")
    finestra.portal = "animeunity"
    finestra.sources.only_portal = "animeunity"
    chiedi(
        "clear() svuota senza sollevare",
        lambda: finestra.history.clear(portal="animeunity"),
        None,
    )
    aggiorna(finestra, "_refresh_continue")
    prova("nessuna riga", righe_continua(finestra) == 0,
          "righe = %d" % righe_continua(finestra))
    prova("l'etichetta del vuoto compare", visibile(finestra.continue_empty))
    # La distinzione che conta: «non hai mai guardato niente» e «niente QUI» sono
    # affermazioni diverse, e dire la prima quando vale la seconda si legge come dati
    # perduti. E' la paura che questa prova esiste per non far tornare.
    prova(
        "e dice «niente su questo portale», non «non stai guardando nulla»",
        "Niente da riprendere" in finestra.continue_empty.text(),
        "testo = %r" % finestra.continue_empty.text()[:70],
    )

    print()
    print("i preferiti, su AnimeSaturn:")
    finestra.portal = "animesaturn"
    finestra.sources.only_portal = "animesaturn"
    aggiorna(finestra, "_refresh_favorites")
    prova(
        "una scheda: il togliato non e' in elenco",
        finestra.favorites_grid.count() == 1,
        "schede = %d" % finestra.favorites_grid.count(),
    )
    prova("l'etichetta del vuoto non compare",
          not visibile(finestra.favorites_empty))
    prova(
        "e l'avviso conta quello sull'altro portale",
        visibile(finestra.favorites_outside),
        "avviso = %r" % finestra.favorites_outside.text()[:60],
    )

    print()
    print("la griglia quando il portale cambia mentre guardi altro:")
    # Si intercetta ``_spawn_search`` e non ``_start_query``: così la logica vera gira
    # tutta — compreso l'azzeramento della bandiera — e si ferma solo un passo prima
    # della rete. Fermare ``_start_query`` avrebbe provato lo spegnimento, non il codice.
    cercate: list[dict] = []
    finestra._spawn_search = lambda: cercate.append(dict(finestra._query))
    finestra.portal = "animesaturn"
    finestra.sources.only_portal = "animesaturn"
    finestra._catalog_stale = False

    # Da un'altra scheda: non si strappa niente, ma si prende nota.
    mw.choose_portal = lambda *a, **k: "animeunity"
    finestra.tabs.setCurrentIndex(finestra._library_tab_index)
    cercate.clear()
    finestra._change_portal()
    prova("da un'altra scheda la ricerca non si rifà subito", not cercate,
          "ricerche = %d" % len(cercate))
    prova("ma la griglia resta segnata come vecchia", finestra._catalog_stale)

    finestra._on_tab_changed(0)
    prova("tornando al catalogo si rifà, una volta", len(cercate) == 1,
          "ricerche = %d" % len(cercate))
    prova("e non è più vecchia", not finestra._catalog_stale)
    finestra._on_tab_changed(0)
    prova("e non si rifà di nuovo senza motivo", len(cercate) == 1,
          "ricerche = %d" % len(cercate))

    # Dentro la scheda di un anime: nemmeno lì si strappa.
    mw.choose_portal = lambda *a, **k: "animesaturn"
    finestra.tabs.setCurrentIndex(0)
    finestra.catalog_stack.setCurrentIndex(1)
    cercate.clear()
    finestra._change_portal()
    prova("leggendo la scheda di un anime non si rifà", not cercate,
          "ricerche = %d" % len(cercate))
    prova("la griglia sotto si segna vecchia", finestra._catalog_stale)
    finestra._go_back()
    prova("uscendo dalla scheda la griglia si rifà", len(cercate) == 1,
          "ricerche = %d" % len(cercate))
    prova("e si torna davvero sulla griglia",
          finestra.catalog_stack.currentIndex() == 0)

    # Guardando la griglia: si rifà subito, come faceva già.
    mw.choose_portal = lambda *a, **k: "animeunity"
    finestra.tabs.setCurrentIndex(0)
    finestra.catalog_stack.setCurrentIndex(0)
    cercate.clear()
    finestra._change_portal()
    prova("guardando la griglia il cambio la rifà subito", len(cercate) == 1,
          "ricerche = %d" % len(cercate))
    prova("e non resta nulla di vecchio da rifare",
          not finestra._catalog_stale)

    print()
    print("la scelta della qualità:")
    combo = finestra.quality_combo
    prova("la tendina offre le qualità che l'app può servire",
          combo.count() == 4, "voci = %d" % combo.count())
    prova("e la prima vale «nessun vincolo», cioè la migliore disponibile",
          combo.itemData(0) == "", "itemData(0) = %r" % combo.itemData(0))

    # Su AnimeSaturn un episodio è un file solo: niente fra cui scegliere.
    mw.choose_portal = lambda *a, **k: "animesaturn"
    finestra._change_portal()
    prova("su AnimeSaturn la tendina è spenta", not combo.isEnabled())
    prova("e dice perché, invece di sparire",
          "un file solo" in combo.toolTip(),
          "tooltip = %r" % combo.toolTip()[:80])

    # Su AnimeUnity si sceglie, e la scelta si salva.
    mw.choose_portal = lambda *a, **k: "animeunity"
    finestra._change_portal()
    prova("su AnimeUnity è accesa", combo.isEnabled())
    for i in range(combo.count()):
        if combo.itemData(i) == "720p":
            combo.setCurrentIndex(i)
            break
    prova("scegliere 720p lo salva: la tendina È la preferenza, non una copia",
          finestra.settings.preferred_quality == "720p",
          "vale %r" % finestra.settings.preferred_quality)

    # E tornando dove non si può scegliere, la scelta non si perde: spegnere un
    # comando riguarda cosa si può scegliere, non cosa resta scelto.
    mw.choose_portal = lambda *a, **k: "animesaturn"
    finestra._change_portal()
    prova("tornando su AnimeSaturn si rispegne", not combo.isEnabled())
    prova("ma la scelta NON viene cancellata: vale per quando si torna",
          finestra.settings.preferred_quality == "720p",
          "vale %r" % finestra.settings.preferred_quality)

    print()
    print("il sondaggio delle qualità disponibili:")
    from gui.models import Anime

    mw.choose_portal = lambda *a, **k: "animeunity"
    finestra._change_portal()

    def nascosta(riga):
        return combo.view().isRowHidden(riga)

    def voce(valore):
        for i in range(combo.count()):
            if combo.itemData(i) == valore:
                return i, combo.model().item(i)
        raise AssertionError("manca la voce %r" % valore)

    finestra._detail_anime = Anime(
        slug="akame-ga-kill", title="Akame ga Kill!", poster="", anime_type="TV",
        dubbed=False, episodes_count=24, year="2014", score="8",
        source_id="animeunity",
    )

    # «Akame ga Kill!» ha 720p e 480p, e non ha il 1080p: misurato con un 404
    # sull'indirizzo fratello, con e senza intestazioni da browser.
    finestra._apply_quality_availability(["720p", "480p"])
    i1080, v1080 = voce("1080p")
    i720, v720 = voce("720p")
    prova("il 1080p che questo anime non ha sparisce dalla lista", nascosta(i1080))
    prova("e la tastiera non ci può atterrare comunque", not v1080.isEnabled())
    prova("il 720p che c'è resta nella lista", not nascosta(i720))
    prova("e scegliibile", v720.isEnabled())
    prova("e col nome pulito", combo.itemText(i720) == "720p",
          "testo = %r" % combo.itemText(i720))
    imigliore, vmigliore = voce("")
    prova("«migliore disponibile» non sparisce mai: non promette una risoluzione",
          not nascosta(imigliore) and vmigliore.isEnabled())
    prova("e la preferenza salvata non viene toccata",
          finestra.settings.preferred_quality == "720p",
          "vale %r" % finestra.settings.preferred_quality)

    print()
    print("  e la lista corta si spiega, invece di sembrare un'app che ha perso roba:")
    prova("l'etichetta porta la ⓘ, perché un consiglio invisibile non spiega niente",
          "ⓘ" in finestra.quality_label.text(),
          "etichetta = %r" % finestra.quality_label.text())
    prova("e il consiglio dice che il menu elenca solo quelle che l'anime ha",
          "solo le qualità" in finestra.quality_label.toolTip(),
          "tooltip = %r" % finestra.quality_label.toolTip()[:90])
    prova("dicendo anche quali sono",
          "720p" in finestra.quality_label.toolTip()
          and "480p" in finestra.quality_label.toolTip())
    prova("e sta anche sulla tendina, non solo sull'etichetta",
          finestra.quality_label.toolTip() == combo.toolTip())

    # Il caso che conta: la preferenza È proprio quella che manca.
    combo.setCurrentIndex(i1080)
    finestra._apply_quality_availability(["720p", "480p"])
    prova("scegliendo il 1080p la preferenza diventa 1080p",
          finestra.settings.preferred_quality == "1080p",
          "vale %r" % finestra.settings.preferred_quality)
    prova("la tendina chiusa continua a mostrare la scelta, che è ciò che verrà "
          "chiesto, e avvisa che qui non c'è",
          "1080p" in combo.currentText() and "non c'è" in combo.currentText(),
          "si legge %r" % combo.currentText())
    prova("la sua riga però non è nella lista", nascosta(i1080))
    prova("il consiglio dice cosa c'è al suo posto",
          "720p" in combo.toolTip() and "480p" in combo.toolTip(),
          "tooltip = %r" % combo.toolTip()[:100])
    prova("e che la scelta resta salvata per gli altri anime",
          "resta salvata" in combo.toolTip(),
          "tooltip = %r" % combo.toolTip()[-120:])
    prova("e la preferenza NON viene riscritta su una che esiste qui: "
          "scaricare la legge da lì, e due stati si contraddicono",
          finestra.settings.preferred_quality == "1080p",
          "vale %r" % finestra.settings.preferred_quality)

    # Cambiando anime il sondaggio precedente non vale più.
    finestra._reset_quality_availability()
    prova("aprendo un altro anime il 1080p torna nella lista",
          not nascosta(i1080) and v1080.isEnabled())
    prova("e il suo nome torna pulito", combo.itemText(i1080) == "1080p",
          "testo = %r" % combo.itemText(i1080))

    # Un sondaggio che non riesce è un «non lo so», non un «niente».
    finestra._apply_quality_availability([])
    prova("un sondaggio senza risposta lascia offerto tutto",
          not nascosta(i1080) and v1080.isEnabled())

    # La risposta si ricorda per (portale, anime): costa richieste vere.
    finestra._on_qualities_probed(("animeunity", "akame-ga-kill"), ["720p", "480p"])
    prova("la risposta si ricorda per questo anime",
          finestra._quality_seen.get(("animeunity", "akame-ga-kill"))
          == ["720p", "480p"],
          "ricordato = %r" % (finestra._quality_seen,))

    # Una risposta in ritardo per l'anime di prima non deve parlare di questo.
    finestra._reset_quality_availability()
    finestra._on_qualities_probed(("animeunity", "un-altro-anime"), ["480p"])
    prova("una risposta in ritardo per un altro anime non restringe questo menu",
          not nascosta(i1080) and not nascosta(i720))
    # E una per lo STESSO slug su un altro portale non si confonde con questa: lo
    # stesso anime su due portali non ha le stesse risoluzioni.
    finestra._on_qualities_probed(("animesaturn", "akame-ga-kill"), ["480p"])
    prova("lo stesso slug su un altro portale è un'altra cosa, e non restringe qui",
          not nascosta(i1080) and not nascosta(i720))
    prova("e si ricorda separato, non sovrascrive l'altro portale",
          finestra._quality_seen.get(("animesaturn", "akame-ga-kill")) == ["480p"]
          and finestra._quality_seen.get(("animeunity", "akame-ga-kill"))
          == ["720p", "480p"],
          "ricordato = %r" % (finestra._quality_seen,))
    prova("ma si ricorda comunque, per quando ci si torna",
          finestra._quality_seen.get(("animeunity", "un-altro-anime")) == ["480p"],
          "ricordato = %r" % (finestra._quality_seen,))

    print()
    print("  con «Tutti i portali», che è lo stato di partenza:")
    mw.choose_portal = lambda *a, **k: None
    finestra._change_portal()
    prova("si cerca davvero su tutti", len(finestra.sources.browsing) > 1,
          "portali = %r" % [x.id for x in finestra.sources.browsing])

    # Il portale che conta è quello della scheda aperta, non quelli su cui si cerca.
    finestra._detail_anime = Anime(
        slug="qualcosa", title="Qualcosa", poster="", anime_type="TV",
        dubbed=False, episodes_count=12, year="2020", score="7",
        source_id="animesaturn",
    )
    finestra._reset_quality_availability()
    prova("sulla scheda di un anime di AnimeSaturn la tendina è spenta, "
          "anche se si sta cercando anche su AnimeUnity",
          not combo.isEnabled())
    prova("e dice che è quel portale a servire un file solo",
          "un file solo" in combo.toolTip()
          and "AnimeSaturn" in combo.toolTip(),
          "tooltip = %r" % combo.toolTip()[:110])

    finestra._detail_anime = Anime(
        slug="akame-ga-kill", title="Akame ga Kill!", poster="", anime_type="TV",
        dubbed=False, episodes_count=24, year="2014", score="8",
        source_id="animeunity",
    )
    finestra._reset_quality_availability()
    prova("sulla scheda di un anime di AnimeUnity è accesa", combo.isEnabled())
    prova("e NON promette una lista già ristretta: qui il sondaggio non ha "
          "ancora risposto, e il menu le offre tutte",
          "elenca solo" not in combo.toolTip(),
          "tooltip = %r" % combo.toolTip()[:140])
    prova("dice invece cosa succederà, che è vero",
          "Appena il sondaggio risponde" in combo.toolTip(),
          "tooltip = %r" % combo.toolTip()[:140])

    finestra._detail_anime = None

    finestra.close()
    return 1 if guai else 0


def pulisci() -> None:
    """Via la cartella di prova, i suoi gusci vuoti e la chiave di prova.

    Un verificatore che lascia rifiuti nel profilo dell'utente a ogni esecuzione si fa
    odiare, e questo ne lasciava tre: due cartelle vuote e una chiave di registro.
    """
    if "qttest" not in CARTELLA.as_posix().lower():
        return  # la guardia ha gia' fermato tutto: non c'e' niente di nostro da togliere
    shutil.rmtree(CARTELLA, ignore_errors=True)
    # I gusci sopra: si risale finche' le cartelle sono vuote e sono ancora dentro
    # ``qttest``, cosi' non si tocca mai nulla che non appartenga alla prova.
    genitore = CARTELLA.parent
    while "qttest" in genitore.as_posix().lower():
        try:
            genitore.rmdir()  # solleva, e si smette, se dentro c'e' qualcosa d'altro
        except OSError:
            break
        genitore = genitore.parent

    prefs = QSettings(impostazioni._ORG, impostazioni._APP)
    prefs.clear()
    prefs.sync()
    # ``clear()`` svuota i valori e lascia la chiave. Su Windows va rimossa a mano, o il
    # registro si riempie di chiavi vuote; le foglie prima dei rami, che e' l'unico
    # ordine che ``DeleteKey`` accetta.
    try:
        import winreg

        for ramo in (
            rf"Software\{impostazioni._ORG}\{impostazioni._APP}",
            rf"Software\{impostazioni._ORG}",
        ):
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, ramo)
    except (ImportError, OSError):
        pass  # niente registro, o qualcuno la sta usando: non e' un motivo per fallire


if __name__ == "__main__":
    try:
        esito = main()
    finally:
        pulisci()
    print()
    print("tutto a posto" if esito == 0 else "%d prove fallite" % guai)
    sys.exit(esito)
