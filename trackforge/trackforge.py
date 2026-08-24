"""TrackForge - forge clean GPX tracks."""

import re

import reflex as rx

from .gpx import count_trackpoints, remove_waypoints
from .komoot import KomootError, fetch_gpx


def _safe_filename(name: str) -> str:
    name = re.sub(r"\.gpx$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[^\w\-. ]+", "_", name).strip() or "track"
    return f"{name}_clean.gpx"


class TrackForgeState(rx.State):
    komoot_url: str = ""
    is_loading: bool = False
    error: str = ""
    result_gpx: str = ""
    result_filename: str = ""
    source_name: str = ""
    removed_count: int = 0
    trackpoint_count: int = 0

    def _reset(self):
        self.error = ""
        self.result_gpx = ""
        self.result_filename = ""
        self.source_name = ""
        self.removed_count = 0
        self.trackpoint_count = 0

    def _process(self, content: str, name: str):
        cleaned, removed = remove_waypoints(content)
        self.result_gpx = cleaned
        self.result_filename = _safe_filename(name)
        self.source_name = name
        self.removed_count = removed
        self.trackpoint_count = count_trackpoints(cleaned)

    @rx.event
    def update_komoot_url(self, value: str):
        self.komoot_url = value

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        self._reset()
        if not files:
            return
        file = files[0]
        data = await file.read()
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            content = data.decode("latin-1")
        if "<gpx" not in content:
            self.error = "Die Datei scheint keine gültige GPX-Datei zu sein."
            return
        self._process(content, file.name or "track.gpx")

    @rx.event
    def fetch_komoot(self):
        self._reset()
        if not self.komoot_url.strip():
            self.error = "Bitte einen Komoot-Link eingeben."
            return
        self.is_loading = True
        yield
        try:
            content, name = fetch_gpx(self.komoot_url.strip())
            self._process(content, name)
        except KomootError as exc:
            self.error = str(exc)
        except Exception:
            self.error = "Die Tour konnte nicht geladen werden. Bitte Link prüfen."
        finally:
            self.is_loading = False

    @rx.event
    def download(self):
        # iOS Safari refuses to save `data:` URI downloads (it just renders
        # them inline), so write the file to the upload dir and download it
        # via a real URL with a proper Content-Disposition header instead.
        upload_dir = rx.get_upload_dir() / self.router.session.client_token
        upload_dir.mkdir(parents=True, exist_ok=True)
        (upload_dir / self.result_filename).write_text(
            self.result_gpx, encoding="utf-8"
        )
        return rx.download(
            url=rx.get_upload_url(
                f"{self.router.session.client_token}/{self.result_filename}"
            ),
            filename=self.result_filename,
        )


def upload_card() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("file-up", size=20, color=rx.color("amber", 9)),
                rx.heading("GPX-Datei", size="4"),
                align="center",
            ),
            rx.upload(
                rx.vstack(
                    rx.icon("upload", size=32, color=rx.color("amber", 8)),
                    rx.text("GPX-Datei hierher ziehen oder klicken"),
                    rx.text(".gpx", size="1", color_scheme="gray"),
                    align="center",
                    spacing="2",
                ),
                id="gpx_upload",
                accept={"application/gpx+xml": [".gpx"]},
                max_files=1,
                on_drop=TrackForgeState.handle_upload(
                    rx.upload_files(upload_id="gpx_upload")
                ),
                border=f"2px dashed {rx.color('amber', 7)}",
                border_radius="12px",
                padding="2em",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def komoot_card() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("link", size=20, color=rx.color("amber", 9)),
                rx.heading("Komoot-Tour", size="4"),
                align="center",
            ),
            rx.text(
                "Link zu einer öffentlichen Tour oder einen Komoot-Share-Link "
                "(private Tour) einfügen.",
                size="2",
                color_scheme="gray",
            ),
            rx.hstack(
                rx.input(
                    placeholder="https://www.komoot.com/tour/123456789",
                    value=TrackForgeState.komoot_url,
                    on_change=TrackForgeState.update_komoot_url,
                    width="100%",
                    size="3",
                ),
                rx.button(
                    rx.icon("hammer", size=16),
                    "Laden",
                    on_click=TrackForgeState.fetch_komoot,
                    loading=TrackForgeState.is_loading,
                    size="3",
                ),
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def result_panel() -> rx.Component:
    return rx.cond(
        TrackForgeState.result_gpx != "",
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.icon("circle-check", size=20, color=rx.color("grass", 9)),
                    rx.heading("Fertig geschmiedet", size="4"),
                    align="center",
                ),
                rx.text(TrackForgeState.source_name, weight="medium"),
                rx.hstack(
                    rx.badge(
                        TrackForgeState.removed_count.to_string()
                        + " Wegpunkte entfernt",
                        color_scheme="amber",
                        size="2",
                    ),
                    rx.badge(
                        TrackForgeState.trackpoint_count.to_string()
                        + " Trackpunkte erhalten",
                        color_scheme="grass",
                        size="2",
                    ),
                ),
                rx.button(
                    rx.icon("download", size=16),
                    "GPX herunterladen",
                    on_click=TrackForgeState.download,
                    size="3",
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            width="100%",
        ),
    )


def error_panel() -> rx.Component:
    return rx.cond(
        TrackForgeState.error != "",
        rx.callout(
            TrackForgeState.error,
            icon="triangle-alert",
            color_scheme="red",
            width="100%",
        ),
    )


def header() -> rx.Component:
    return rx.vstack(
        rx.image(src="/logo.svg", width="96px", height="96px"),
        rx.heading("TrackForge", size="8"),
        rx.text(
            "Forge clean GPX tracks — Wegpunkte raus, Track bleibt.",
            color_scheme="gray",
        ),
        align="center",
        spacing="2",
    )


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            header(),
            error_panel(),
            result_panel(),
            upload_card(),
            komoot_card(),
            rx.text(
                "TrackForge entfernt alle <wpt>-Wegpunkte aus GPX-Dateien.",
                size="1",
                color_scheme="gray",
            ),
            spacing="5",
            width="100%",
            max_width="560px",
            padding_y="3em",
            align="center",
        ),
        padding_x="1em",
        min_height="100vh",
    )


app = rx.App()
app.add_page(index, title="TrackForge — Forge clean GPX tracks")
