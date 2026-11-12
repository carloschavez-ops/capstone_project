"""HU17: servidor WSGI de un proceso, sin depurador y con persistencia SQLite."""

import os

from backend.backups import maintenance_lock, runtime_paths


def main():
    from waitress import serve
    from backend.app import create_app

    on_render = os.environ.get("RENDER") == "true"
    if on_render:
        os.environ.setdefault("PIZZA_PRONTO_ENV", "production")
    host = "0.0.0.0" if on_render else "127.0.0.1"
    port = int(os.environ.get("PORT", "10000" if on_render else "5000"))
    data, _, _, _ = runtime_paths()
    with maintenance_lock(data):
        app = create_app()
        serve(app, host=host, port=port, threads=4,
              max_request_body_size=5 * 1024 * 1024, expose_tracebacks=False)


if __name__ == "__main__":
    main()
