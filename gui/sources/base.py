"""What a streaming portal must provide to be usable by the app.

Until now the app talked to one site directly, so "the client" and "AnimeSaturn" were the
same thing. To add a second portal that assumption has to go: the rest of the app should
ask *a source* for results and not care which site answered.

Only four operations are genuinely portal-specific — searching, suggesting, listing an
anime's episodes and turning an episode into a playable URL. Everything else (downloading
bytes, writing files) is plain HTTP and stays shared.

Every record a source returns carries its ``source_id``. Without it the app would find an
anime but not know who to ask for the video.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AnimeSource(ABC):
    """A streaming portal the app can search and play from."""

    #: Short stable identifier stored alongside results, e.g. ``"animesaturn"``.
    id: str = ""
    #: Name shown to the user, e.g. ``"AnimeSaturn"``.
    label: str = ""

    @abstractmethod
    def search(
        self,
        title: str | None = None,
        *,
        sort: str = "standard",
        page: int = 1,
        dub: str = "",
        filters: dict | None = None,
    ) -> list[dict]:
        """Return catalogue records, each tagged with this source's id."""

    @abstractmethod
    def suggest(self, query: str) -> list[dict]:
        """Return as-you-type title suggestions (empty list if unsupported)."""

    @abstractmethod
    def fetch_anime_detail(self, slug: str) -> dict:
        """Return ``{"episodes": [...], "plot": str, "genres": [str]}``."""

    @abstractmethod
    def resolve_download_url(self, watch_path: str, quality: str = "") -> str:
        """Turn an episode path into a direct, playable media URL.

        ``quality`` (``"1080p"``, ``"720p"``, ``"480p"``, oppure ``""`` per «quella che
        c'e'») e' una **preferenza**, non un ordine: un portale che non offre scelta la
        ignora, e un portale che la offre ripiega su cio' che ha quando la risoluzione
        chiesta non esiste per quell'episodio. Nessun episodio deve restare non
        riproducibile per via di una preferenza.
        """

    def fetch_genres(self) -> list[dict]:
        """Browsable genres. Optional: a portal without a genre page returns nothing."""
        return []

    def quality_options(self) -> dict[str, str]:
        """Le qualita' fra cui si puo' scegliere su questo portale, etichetta -> valore.

        Vuoto quando non c'e' scelta, ed e' il caso normale: la maggior parte dei
        portali serve un file solo per episodio. Dichiararlo qui evita all'interfaccia
        di sapere quale portale puo' cosa — come per i filtri che un portale non sa
        esprimere, il comando si disegna da cio' che le sorgenti dicono di se'.

        Un elenco vuoto non vuol dire «non si puo' scaricare»: vuol dire «non c'e' da
        scegliere», e il comando va spento, non nascosto, o sembrera' un pezzo di app
        perduto invece di una possibilita' che quel portale non offre.
        """
        return {}

    def expressible_filters(self) -> dict[str, set[str] | None]:
        """Quali filtri questo portale sa esprimere, dove non li sa esprimere tutti.

        Una chiave **assente** vuol dire «nessun limite»: e' il caso normale, ed e' il
        caso del portale da cui il pannello dei filtri ha preso il suo vocabolario. Una
        chiave che vale ``None`` e' una dimensione che qui non esiste affatto. Una chiave
        che vale un insieme elenca i soli valori traducibili.

        Serve all'interfaccia **prima** della ricerca. Un portale che non puo' tradurre
        un filtro torna una lista vuota di proposito -- mostrare risultati non filtrati
        sarebbe peggio -- ma quel vuoto arriva identico a «nessuna corrispondenza», e si
        legge come la risposta a una domanda che non e' stata posta. Dichiarandolo qui,
        il comando si spegne prima che tu possa usarlo: un avviso spiega l'errore, un
        comando spento non te lo fa fare.
        """
        return {}

    def close(self) -> None:
        """Release network resources. Optional."""

    # ------------------------------------------------------------------ #
    def tag(self, records: list[dict]) -> list[dict]:
        """Stamp records with this source's id, so the app knows who to ask later."""
        for record in records:
            record.setdefault("source_id", self.id)
            record.setdefault("source_label", self.label)
        return records
