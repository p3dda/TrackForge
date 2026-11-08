"""TrackForge - forge clean GPX tracks."""

import asyncio
import re
from urllib.parse import quote

import reflex as rx

from .gpx import count_trackpoints, is_gpx, remove_waypoints, track_preview_svg
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
    track_svg_uri: str = ""

    def _reset(self):
        self.error = ""
        self.result_gpx = ""
        self.result_filename = ""
        self.source_name = ""
        self.removed_count = 0
        self.trackpoint_count = 0
        self.track_svg_uri = ""

    def _process(self, content: str, name: str):
        cleaned, removed = remove_waypoints(content)
        self.result_gpx = cleaned
        self.result_filename = _safe_filename(name)
        self.source_name = name
        self.removed_count = removed
        self.trackpoint_count = count_trackpoints(cleaned)
        svg = track_preview_svg(content)
        self.track_svg_uri = f"data:image/svg+xml;utf8,{quote(svg)}" if svg else ""

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
        if not is_gpx(content):
            self.error = "Die Datei scheint keine gültige GPX-Datei zu sein."
            return
        self._process(content, file.name or "track.gpx")

    @rx.event
    async def fetch_komoot(self):
        self._reset()
        url = self.komoot_url.strip()
        if not url:
            self.error = "Bitte einen Komoot-Link eingeben."
            return
        self.is_loading = True
        yield
        try:
            # fetch_gpx does blocking HTTP; keep it off the event loop.
            content, name = await asyncio.to_thread(fetch_gpx, url)
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
        token = self.router.session.client_token
        upload_dir = rx.get_upload_dir() / token
        upload_dir.mkdir(parents=True, exist_ok=True)
        (upload_dir / self.result_filename).write_text(
            self.result_gpx, encoding="utf-8"
        )
        return rx.download(
            url=rx.get_upload_url(f"{token}/{self.result_filename}"),
            filename=self.result_filename,
        )


MUTED = "var(--tf-muted)"
TEXT_2 = "var(--tf-text-2)"


def card_heading(title: str, subtitle: str | None = None) -> rx.Component:
    children = [rx.text(title, size="3", weight="medium", color="var(--tf-text)")]
    if subtitle:
        children.append(rx.text(subtitle, size="2", color=TEXT_2))
    return rx.vstack(*children, spacing="1", width="100%")


def legend_item(marker_class: str, label: str) -> rx.Component:
    return rx.hstack(
        rx.box(class_name=marker_class),
        rx.text(label, size="1", color=MUTED),
        spacing="2",
        align="center",
    )


def track_preview() -> rx.Component:
    return rx.cond(
        TrackForgeState.track_svg_uri != "",
        rx.box(
            rx.image(
                src=TrackForgeState.track_svg_uri,
                alt="Verlauf des bereinigten Tracks mit entfernten Wegpunkten",
            ),
            rx.hstack(
                legend_item("tf-legend-track", "Track"),
                rx.cond(
                    TrackForgeState.removed_count > 0,
                    legend_item("tf-legend-wpt", "entfernte Wegpunkte"),
                ),
                spacing="4",
                position="absolute",
                left="12px",
                bottom="8px",
            ),
            class_name="tf-track",
        ),
    )


def figure(value, label: str) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", color=TEXT_2),
        rx.text(value, class_name="tf-figure"),
        spacing="1",
    )


def result_panel() -> rx.Component:
    return rx.cond(
        TrackForgeState.result_gpx != "",
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.hstack(
                        rx.icon("circle-check", size=16, color="var(--tf-positive)"),
                        rx.text("Fertig geschmiedet", size="3", weight="medium"),
                        spacing="2",
                        align="center",
                        flex_shrink="0",
                    ),
                    rx.text(
                        TrackForgeState.result_filename,
                        size="1",
                        color=MUTED,
                        class_name="tf-mono",
                        white_space="nowrap",
                        overflow="hidden",
                        text_overflow="ellipsis",
                        min_width="0",
                        flex="1",
                        text_align="right",
                    ),
                    justify="between",
                    align="center",
                    spacing="4",
                    width="100%",
                ),
                track_preview(),
                rx.grid(
                    figure(TrackForgeState.removed_count, "Wegpunkte entfernt"),
                    figure(TrackForgeState.trackpoint_count, "Trackpunkte erhalten"),
                    columns="2",
                    spacing="4",
                    width="100%",
                ),
                rx.button(
                    rx.icon("download", size=16),
                    "GPX herunterladen",
                    on_click=TrackForgeState.download,
                    size="3",
                    width="100%",
                    margin_top="4px",
                ),
                spacing="5",
                width="100%",
            ),
            class_name="tf-card tf-enter",
        ),
    )


def upload_card() -> rx.Component:
    return rx.box(
        rx.vstack(
            card_heading(
                "GPX-Datei", "Export aus Komoot oder einem anderen Routenplaner"
            ),
            rx.upload(
                rx.vstack(
                    rx.icon("upload", size=18, color=MUTED, stroke_width=1.5),
                    rx.text("Datei ablegen oder auswählen", size="2"),
                    rx.text(".gpx", size="1", color=MUTED, class_name="tf-mono"),
                    align="center",
                    spacing="2",
                ),
                id="gpx_upload",
                accept={"application/gpx+xml": [".gpx"]},
                max_files=1,
                on_drop=TrackForgeState.handle_upload(
                    rx.upload_files(upload_id="gpx_upload")
                ),
                border="1px dashed var(--tf-line-strong)",
                border_radius="8px",
                cursor="pointer",
                transition="background-color 150ms var(--tf-ease), border-color 150ms var(--tf-ease)",
                _hover={
                    "background": "var(--tf-raised)",
                    "border_color": "rgba(237, 237, 237, 0.28)",
                },
                padding="32px 16px",
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        class_name="tf-card",
    )


def komoot_card() -> rx.Component:
    return rx.box(
        rx.vstack(
            card_heading(
                "Komoot-Tour",
                "Link zu einer öffentlichen Tour oder Share-Link einer privaten "
                "Tour (Teilen → Link kopieren)",
            ),
            rx.flex(
                rx.input(
                    placeholder="komoot.com/tour/…",
                    value=TrackForgeState.komoot_url,
                    on_change=TrackForgeState.update_komoot_url,
                    aria_label="Komoot-Link",
                    class_name="tf-mono",
                    width="100%",
                    size="3",
                ),
                rx.button(
                    "Laden",
                    on_click=TrackForgeState.fetch_komoot,
                    loading=TrackForgeState.is_loading,
                    variant="surface",
                    color_scheme="gray",
                    high_contrast=True,
                    size="3",
                ),
                direction=rx.breakpoints(initial="column", xs="row"),
                spacing="2",
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        class_name="tf-card",
    )


def error_panel() -> rx.Component:
    return rx.cond(
        TrackForgeState.error != "",
        rx.callout(
            TrackForgeState.error,
            icon="triangle-alert",
            color_scheme="red",
            variant="surface",
            width="100%",
        ),
    )


def header() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.image(src="/logo.svg", width="28px", height="28px", alt=""),
            rx.text("TrackForge", size="3", weight="medium"),
            spacing="2",
            align="center",
        ),
        rx.heading(
            "Wegpunkte raus, Track bleibt",
            as_="h1",
            size=rx.breakpoints(initial="7", sm="8"),
            weight="medium",
            margin_top="28px",
        ),
        rx.text(
            "Komoot bettet Highlights als Wegpunkte in GPX-Exporte ein. "
            "TrackForge entfernt sie, damit dein Navi nur den Track anzeigt.",
            size="3",
            color=TEXT_2,
            max_width="34rem",
        ),
        spacing="3",
        width="100%",
    )


def index() -> rx.Component:
    return rx.box(
        rx.vstack(
            header(),
            rx.vstack(
                error_panel(),
                result_panel(),
                upload_card(),
                komoot_card(),
                spacing="4",
                width="100%",
                margin_top="40px",
            ),
            rx.text(
                "Entfernt alle ",
                rx.code("<wpt>", variant="ghost", color=TEXT_2),
                "-Elemente. Trackpunkte, Routen und Metadaten bleiben erhalten.",
                size="2",
                color=MUTED,
                margin_top="32px",
            ),
            width="100%",
            max_width="648px",
            margin_x="auto",
            padding_x=rx.breakpoints(initial="16px", sm="24px"),
            padding_top=rx.breakpoints(initial="40px", sm="64px"),
            padding_bottom="48px",
            spacing="0",
        ),
        min_height="100vh",
        background="var(--tf-bg)",
        color="var(--tf-text)",
    )


app = rx.App(stylesheets=["/styles.css"])
app.add_page(index, title="TrackForge — GPX-Wegpunkte entfernen")
