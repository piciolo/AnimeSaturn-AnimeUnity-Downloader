# -*- coding: utf-8 -*-
"""La sonda delle risoluzioni: tre risposte, e il corpo del file mai letto.

Nasce da una revisione, non da un difetto arrivato all'utente, e i due difetti che
cercava non si vedevano guardando il codice una volta sola:

* ``Range: bytes=0-1`` e' una **richiesta**, non un obbligo. Un server che la ignorasse
  risponde 200 col file intero, e ``httpx.Client.get`` bufferizza: centinaia di megabyte
  tirati giu' per sapere se un file esiste. Il commento diceva «due byte bastano», e per
  questo portale era vero -- ma era vero per gentilezza del server, non per costruzione.

* Ogni risposta diversa da 200/206 veniva letta come «questa risoluzione non esiste». Un
  403, un 429, un server momentaneamente giu': lo stesso verdetto di un 404. E quel
  verdetto viene **ricordato**, quindi una qualita' che c'era sparisce dal menu per tutta
  la sessione.

Qui la rete non si tocca: il client e' finto, cosi' ogni codice di stato si puo' chiedere
a comando -- e il finto registra se qualcuno ha provato a leggere il corpo, che e'
esattamente il difetto da impedire.

Uso: python verify_probe.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, r"F:\AnimeSaturnDownloader\Windows APP")

import httpx  # noqa: E402

from gui.sources.animeunity_client import AnimeUnityClient  # noqa: E402

guai = 0


def prova(nome: str, ok: bool, dettaglio: str = "") -> None:
    global guai
    if not ok:
        guai += 1
    print("  %s %s" % ("ok  " if ok else "NO  ", nome))
    if not ok and dettaglio:
        print("       " + dettaglio)


class Risposta:
    """Quel tanto di risposta che serve: l'esito e le intestazioni."""

    def __init__(self, status_code: int, content_type: str, registro: list) -> None:
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._registro = registro

    # Se qualcuno chiama uno di questi, il corpo sta arrivando: e' il difetto.
    def read(self) -> bytes:
        self._registro.append("read")
        return b""

    def iter_bytes(self, *a, **k):
        self._registro.append("iter_bytes")
        return iter(())

    @property
    def content(self) -> bytes:
        self._registro.append("content")
        return b""


class Flusso:
    def __init__(self, risposta: Risposta) -> None:
        self._risposta = risposta

    def __enter__(self) -> Risposta:
        return self._risposta

    def __exit__(self, *a) -> bool:
        return False


class ClienteFinto:
    """Risponde quello che gli si dice, e si ricorda come gliel'hanno chiesto."""

    def __init__(self, risposte: dict) -> None:
        self.risposte = risposte  # url -> (status, content-type) oppure un'eccezione
        self.letture: list[str] = []
        self.chiesti: list[str] = []
        self.bufferizzati: list[str] = []

    def stream(self, method: str, url: str, headers: dict | None = None) -> Flusso:
        self.chiesti.append(url)
        esito = self.risposte.get(url, (404, "text/html"))
        if isinstance(esito, Exception):
            raise esito
        stato, tipo = esito
        return Flusso(Risposta(stato, tipo, self.letture))

    def get(self, url: str, **kw):
        # Con ``get`` il corpo arriva tutto: la sonda non deve piu' passare da qui.
        self.bufferizzati.append(url)
        raise AssertionError("la sonda ha bufferizzato %s invece di leggere l'esito" % url)


VIDEO = "video/mp4"
BASE = "https://cdn.esempio/x/720p.mp4"


def client_con(risposte: dict) -> tuple[AnimeUnityClient, ClienteFinto]:
    c = AnimeUnityClient()
    finto = ClienteFinto(risposte)
    c._client = finto
    # Il risolvere ha i suoi controlli altrove: qui interessa solo cosa succede DOPO.
    c.resolve_download_url = lambda episode_id, quality="": BASE  # type: ignore[method-assign]
    return c, finto


def u(n: str) -> str:
    return "https://cdn.esempio/x/%sp.mp4" % n


# ===================================================================== #
print("un file c'è, non c'è, o non si è capito — e sono tre cose diverse:")
CASI = [
    ("206 con l'intervallo servito: c'è", (206, VIDEO), True),
    ("200 con un video: c'è (il server ignora Range, ma il file esiste)",
     (200, VIDEO), True),
    ("200 con una pagina: NON c'è — è un errore servito come se andasse bene",
     (200, "text/html; charset=utf-8"), False),
    ("404: non c'è", (404, "text/html"), False),
    ("410: non c'è", (410, "text/html"), False),
    ("403: non si è capito, non «non c'è»", (403, "text/html"), None),
    ("429 (troppe richieste): non si è capito", (429, "text/html"), None),
    ("503 (server giù): non si è capito", (503, "text/html"), None),
]
for nome, risposta, atteso in CASI:
    c, finto = client_con({u("1080"): risposta})
    avuto = c._file_esiste(u("1080"))
    prova(nome, avuto is atteso, "atteso %r, avuto %r" % (atteso, avuto))

c, finto = client_con({u("1080"): httpx.HTTPError("rete caduta")})
prova("rete caduta: non si è capito", c._file_esiste(u("1080")) is None)

# ===================================================================== #
print()
print("e il corpo del file non viene MAI letto:")
c, finto = client_con({u("1080"): (200, VIDEO), u("480"): (206, VIDEO)})
elenco = c.available_qualities(42)
prova("la sonda non passa da `get`, che bufferizza", not finto.bufferizzati)
prova("e nessuno tocca il corpo della risposta", not finto.letture,
      "letture = %r" % finto.letture)
prova("legge solo le due che non conosce già, non tre",
      sorted(finto.chiesti) == sorted([u("1080"), u("480")]),
      "chiesti = %r" % finto.chiesti)

# ===================================================================== #
print()
print("il sondaggio mette insieme le risposte:")
c, _ = client_con({u("1080"): (206, VIDEO), u("480"): (206, VIDEO)})
prova("tutte e tre, dalla più alta",
      c.available_qualities(42) == ["1080p", "720p", "480p"],
      "%r" % c.available_qualities(42))

c, _ = client_con({u("1080"): (404, "text/html"), u("480"): (206, VIDEO)})
prova("senza il 1080p che non c'è",
      c.available_qualities(42) == ["720p", "480p"])

c, _ = client_con({u("1080"): (404, "text/html"), u("480"): (404, "text/html")})
prova("quella che il portale consegna c'è per definizione, e resta sempre",
      c.available_qualities(42) == ["720p"])

# ===================================================================== #
print()
print("una risposta a metà non diventa una risposta:")
c, _ = client_con({u("1080"): (429, "text/html"), u("480"): (206, VIDEO)})
prova("un 429 sul 1080p annulla tutto il sondaggio, invece di nasconderlo",
      c.available_qualities(42) == [],
      "%r — un elenco parziale verrebbe ricordato, e il 1080p sparirebbe"
      % c.available_qualities(42))
c, _ = client_con({u("1080"): (206, VIDEO), u("480"): httpx.HTTPError("giù")})
prova("e lo stesso se è l'ultima a non rispondere",
      c.available_qualities(42) == [])

print()
print("e dove non c'è una risoluzione nell'indirizzo non c'è scelta da offrire:")
c, _ = client_con({})
c.resolve_download_url = lambda episode_id, quality="": (  # type: ignore[method-assign]
    "https://srv/DDL/A/A_Ep_001.mp4?t=k"
)
prova("elenco vuoto, e nessuna richiesta sprecata", c.available_qualities(42) == [])

print()
print("tutto a posto" if guai == 0 else "%d prove fallite" % guai)
sys.exit(1 if guai else 0)
