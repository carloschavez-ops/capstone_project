from backend.app import create_app
from backend.backups import maintenance_lock, runtime_paths


if __name__ == "__main__":
    data, _, _, _ = runtime_paths()
    with maintenance_lock(data):
        create_app().run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
