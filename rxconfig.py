import reflex as rx

config = rx.Config(
    app_name="trackforge",
    show_built_with_reflex=False,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(appearance="dark", accent_color="amber", radius="large"),
        ),
    ],
)
