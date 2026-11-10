"""Background workers (``QRunnable``) that keep the UI responsive.

Every network call runs on a Qt thread pool and reports back through signals, so the
main thread only ever touches ready-to-display data.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from .models import Anime, Episode
from .net import AnimeSaturnClient, DownloadCancelled, build_filename
from .portal_domains import resolve_animeunity_domain
from .sources.registry import SourcesUnavailable


class SearchSignals(QObject):
    # token, schede, e se un portale ha consegnato una pagina piena. Il terzo non si
    # ricava dal secondo: la fusione dei duplicati accorcia l'elenco di proposito, e
    # quel calo veniva letto come «non c'e' altro» -- il catalogo oltre la prima
    # pagina diventava irraggiungibile.
    results = Signal(object, list, bool)
    error = Signal(object, str)
    # Nessun portale attivo ha risposto: token, messaggio, identificativi dei portali
    # che hanno taciuto. Distinto da ``error`` perche' chi riceve deve poter curare il
    # dominio di quei portali, e non lo puo' fare da una stringa.
    unreachable = Signal(object, str, list)


class SearchWorker(QRunnable):
    """Run a search/browse query off the UI thread.

    ``client`` e' il registro delle sorgenti: interroga ogni portale e combina le
    risposte. Prende anche ``meta``, da cui si legge se la pagina era piena.
    """

    def __init__(
        self,
        client: AnimeSaturnClient,
        token: object,
        *,
        title: str | None,
        sort: str,
        page: int,
        dub: str,
        filters: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.client = client
        self.token = token
        self.title = title
        self.sort = sort
        self.page = page
        self.dub = dub
        self.filters = filters
        self.signals = SearchSignals()

    def run(self) -> None:
        try:
            meta: dict = {}
            records = self.client.search(
                self.title,
                sort=self.sort,
                page=self.page,
                dub=self.dub,
                filters=self.filters,
                meta=meta,
            )
            animes = [Anime.from_record(record) for record in records]
            self.signals.results.emit(
                self.token, animes, bool(meta.get("page_full"))
            )
        except SourcesUnavailable as exc:
            # Fuori dal ramo generico: «non ho potuto chiedere» va raccontato in modo
            # diverso da «la richiesta e' andata male», e porta con se' a chi chiedere
            # di nuovo dopo aver cercato il dominio nuovo.
            self.signals.unreachable.emit(
                self.token, str(exc), list(exc.errors.keys())
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self.signals.error.emit(self.token, str(exc))


class AnimeUnityDomainSignals(QObject):
    resolved = Signal(str)  # a domain that answers and really is AnimeUnity


class AnimeUnityDomainWorker(QRunnable):
    """Find a working AnimeUnity domain, off the UI thread.

    Run at start-up and after the portal has failed. It stays quiet unless it
    has something better to offer: when no candidate answers there is no way to
    tell a moved portal from a missing network, and replacing a good address
    with a guess would make things worse.
    """

    def __init__(self, current: str) -> None:
        super().__init__()
        self.current = current
        self.signals = AnimeUnityDomainSignals()

    def run(self) -> None:
        try:
            found = resolve_animeunity_domain(self.current)
        except Exception:  # noqa: BLE001 - best effort, never fatal
            return
        if found and found != self.current:
            self.signals.resolved.emit(found)


class GenresSignals(QObject):
    results = Signal(list)  # list[dict] of genres
    error = Signal(str)


class GenresWorker(QRunnable):
    """Fetch the genre catalogue (from /genres) off the UI thread."""

    def __init__(self, client: AnimeSaturnClient) -> None:
        super().__init__()
        self.client = client
        self.signals = GenresSignals()

    def run(self) -> None:
        try:
            self.signals.results.emit(self.client.fetch_genres())
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self.signals.error.emit(str(exc))


class EpisodesSignals(QObject):
    results = Signal(object, list, str)  # anime_key, list[Episode], plot
    error = Signal(object, str)


class EpisodesWorker(QRunnable):
    """Fetch the episode list (and synopsis) for an anime."""

    def __init__(self, client: AnimeSaturnClient, anime: Anime) -> None:
        super().__init__()
        self.client = client
        self.anime = anime
        self.signals = EpisodesSignals()

    def run(self) -> None:
        try:
            # Con piu' portali collegati, gli episodi vanno chiesti a quello da cui
            # arriva questo anime, non al primo della lista.
            if hasattr(self.client, "fetch_anime_detail_for"):
                detail = self.client.fetch_anime_detail_for(self.anime)
            else:
                detail = self.client.fetch_anime_detail(self.anime.slug)
            episodes = [Episode.from_record(rec) for rec in detail["episodes"]]
            self.signals.results.emit(self.anime.key, episodes, detail.get("plot", ""))
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(self.anime.key, str(exc))


class PosterSignals(QObject):
    done = Signal(str, bytes)  # url, image bytes
    error = Signal(str)


class PosterWorker(QRunnable):
    """Download a poster image."""

    def __init__(self, client: AnimeSaturnClient, url: str) -> None:
        super().__init__()
        self.client = client
        self.url = url
        self.signals = PosterSignals()

    def run(self) -> None:
        try:
            data = self.client.fetch_bytes(self.url)
            self.signals.done.emit(self.url, data)
        except Exception:  # noqa: BLE001 - a missing poster is non-fatal
            self.signals.error.emit(self.url)


class SuggestSignals(QObject):
    results = Signal(object, list)  # token, list[dict]
    error = Signal(object, str)


class SuggestWorker(QRunnable):
    """Fetch search-as-you-type suggestions off the UI thread (debounced by caller)."""

    def __init__(self, client: AnimeSaturnClient, token: object, query: str) -> None:
        super().__init__()
        self.client = client
        self.token = token
        self.query = query
        self.signals = SuggestSignals()

    def run(self) -> None:
        try:
            self.signals.results.emit(self.token, self.client.suggest(self.query))
        except Exception as exc:  # noqa: BLE001 - suggestions are best-effort
            self.signals.error.emit(self.token, str(exc))


class ResolveSignals(QObject):
    done = Signal(object, str)   # token, media_url
    error = Signal(object, str)  # token, message


class ResolveWorker(QRunnable):
    """Resolve an episode's watch page to a direct media URL, off the UI thread.

    Used by the in-app preview player so the UI never blocks while the embed/playlist
    round-trip runs.
    """

    def __init__(
        self,
        client: AnimeSaturnClient,
        token: object,
        watch_path: str,
        *,
        source_id: str = "",
        title: str = "",
        episode_number: str = "",
        quality: str = "",
    ) -> None:
        super().__init__()
        self.client = client
        self.token = token
        self.watch_path = watch_path
        self.source_id = source_id
        self.title = title
        self.episode_number = episode_number
        self.quality = quality
        self.signals = ResolveSignals()

    def run(self) -> None:
        try:
            # With the registry, a portal that cannot serve this episode is not the end:
            # the others are tried before giving up.
            if hasattr(self.client, "resolve_with_fallback") and self.title:
                url, _used = self.client.resolve_with_fallback(
                    self.watch_path,
                    self.source_id,
                    self.title,
                    self.episode_number,
                    self.quality,
                )
            else:
                url = self.client.resolve_download_url(self.watch_path)
            self.signals.done.emit(self.token, url)
        except Exception as exc:  # noqa: BLE001 - surfaced in the player
            self.signals.error.emit(self.token, str(exc))


class DownloadSignals(QObject):
    # task_id, downloaded_bytes, total_bytes, speed_bytes_per_sec
    progress = Signal(int, int, int, float)
    status = Signal(int, str)               # task_id, status text
    finished = Signal(int, bool, str)       # task_id, success, message


class DownloadTask(QRunnable):
    """Resolve an episode's direct link and stream it to disk with progress."""

    def __init__(
        self,
        client: AnimeSaturnClient,
        sources,
        task_id: int,
        anime_title: str,
        episode: Episode,
        dest_dir: Path,
        *,
        source_id: str = "",
        quality: str = "",
    ) -> None:
        """Due oggetti e non uno, perche' le due meta' del lavoro non sono uguali.

        ``sources`` e' il registro dei portali e serve a **risolvere** l'indirizzo:
        quello dipende da dove vive l'episodio. ``client`` serve a **scaricare i
        byte**, e quello non dipende da niente -- ``download_file`` manda solo uno
        User-Agent e un eventuale ``Range``, nessun riferimento al dominio -- quindi
        resta condiviso come e' sempre stato.

        Finche' qui arrivava il solo client di AnimeSaturn, un episodio di AnimeUnity
        veniva composto col dominio sbagliato e il download non poteva che fallire.
        """
        super().__init__()
        self.client = client
        self.sources = sources
        self.task_id = task_id
        self.anime_title = anime_title
        self.episode = episode
        self.dest_dir = dest_dir
        self.source_id = source_id
        self.quality = quality
        self.signals = DownloadSignals()
        self._cancel = threading.Event()
        self._response = None
        self._base: int | None = None
        self._last_emit = 0.0
        self._start_time = 0.0

    def cancel(self) -> None:
        self._cancel.set()
        # Close the live stream (if any) so a blocked read unblocks immediately
        # instead of waiting for the read timeout.
        response = self._response
        if response is not None:
            try:
                response.close()
            except Exception:  # noqa: BLE001 - best-effort interruption
                pass

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def _set_response(self, response) -> None:
        self._response = response

    def _on_progress(self, downloaded: int, total: int) -> None:
        now = time.monotonic()
        # On a resumed download the first callback already includes the bytes that were
        # present on disk; use them as the baseline so the speed reflects this session.
        if self._base is None:
            self._base = downloaded
        # Throttle UI updates to ~12 per second. Always emit the final chunk, but only
        # when the total is known (otherwise the guard must still throttle).
        is_final = total > 0 and downloaded >= total
        if now - self._last_emit < 0.08 and not is_final:
            return
        self._last_emit = now
        elapsed = max(now - self._start_time, 1e-6)
        speed = max(downloaded - self._base, 0) / elapsed
        self.signals.progress.emit(self.task_id, downloaded, total, speed)

    def run(self) -> None:
        if self._cancel.is_set():
            self.signals.finished.emit(self.task_id, False, "Annullato")
            return
        try:
            self.signals.status.emit(self.task_id, "Risoluzione link…")
            # Al portale da cui viene l'episodio, non al primo che capita: l'indirizzo
            # di una puntata di AnimeUnity e' un numero, e composto col dominio di
            # AnimeSaturn non sbaglia a volte, sbaglia sempre. Si usa lo stesso ripiego
            # della riproduzione -- se il suo portale non ce la fa, l'episodio si cerca
            # sugli altri per titolo -- cosi' le due cose non si contraddicono piu':
            # prima lo stesso episodio si riproduceva e non si scaricava, e sembrava un
            # guasto a caso.
            download_url, _used = self.sources.resolve_with_fallback(
                self.episode.watch_path,
                self.source_id,
                self.anime_title,
                self.episode.number,
                self.quality,
            )

            filename = build_filename(self.anime_title, self.episode, download_url)
            dest_path = self.dest_dir / filename

            if dest_path.exists():
                self.signals.finished.emit(self.task_id, True, "Già presente")
                return

            # Resuming when a leftover partial file exists.
            partial = dest_path.with_suffix(dest_path.suffix + ".part")
            resuming = partial.exists() and partial.stat().st_size > 0
            self.signals.status.emit(
                self.task_id, "Ripresa…" if resuming else "Download…"
            )
            self._start_time = time.monotonic()
            self.client.download_file(
                download_url,
                dest_path,
                progress=self._on_progress,
                should_cancel=self._cancel.is_set,
                on_response=self._set_response,
            )
            self.signals.finished.emit(self.task_id, True, str(dest_path))
        except DownloadCancelled:
            self.signals.finished.emit(self.task_id, False, "Annullato")
        except Exception as exc:  # noqa: BLE001
            # Closing the stream to cancel surfaces as a read/stream error here.
            if self._cancel.is_set():
                self.signals.finished.emit(self.task_id, False, "Annullato")
            else:
                self.signals.finished.emit(self.task_id, False, f"Errore: {exc}")
