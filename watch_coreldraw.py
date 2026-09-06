"""CorelDRAW-ний хамт MCP Server + CorelChamp (Streamlit)-ийг автоматаар асаах/унтраах.

CorelDRAW-ыг манана: CorelDRAW нээгдэхэд MCP Server (8765) болон CorelChamp (8501)-ийг
автоматаар асаана; CorelDRAW хаагдахад хоёуланг нь унтраана. Windows эхлэхэд энэ скриптийг
өөрөө ажиллуулахаар тохируулбал (Startup folder), цаашид гараар юу ч хийх шаардлагагүй.

Ажиллуулах: .venv\\Scripts\\python.exe watch_coreldraw.py
Зогсоох:    Ctrl+C
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# pythonw.exe-ээр консолгүйгээр (Startup-аас автоматаар) ажиллуулбал sys.stdout/stderr
# нь None байдаг — print() өөрөө ч None target руу бичихдээ AttributeError шиднэ,
# зөвхөн .reconfigure()-ийг хамгаалаад зогсохгүй, консол байхгүй үед лог файл руу
# бичихээр сольж өгөх ёстой (эс тэгвэл 1-р мөрөнд нь чимээгүй унана, юу болсныг
# мэдэх аргагүй болно).
if sys.stdout is None:
    _log = open(ROOT / "watch_coreldraw.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = _log
    sys.stderr = _log
else:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
STREAMLIT = ROOT / ".venv" / "Scripts" / "streamlit.exe"
POLL_SECONDS = 5

_procs: dict[str, subprocess.Popen] = {}


def _coreldraw_running() -> bool:
    # Жинхэнэ процессын нэр нь CorelDRW.exe (том үсгээр DRW) — tasklist-ийн filter өөрөө
    # том жижиг үсэг ялгахгүй ажилладаг ч Python-ий string харьцуулалт ялгадаг тул
    # .upper() болгож харьцуулна.
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq CorelDRW.exe"],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return "CORELDRW.EXE" in result.stdout.upper()


def _is_alive(name: str) -> bool:
    p = _procs.get(name)
    return p is not None and p.poll() is None


def _start_all():
    if not _is_alive("mcp"):
        print("[watch] CorelDRAW илэрлээ → MCP Server эхлүүлж байна…")
        _procs["mcp"] = subprocess.Popen(
            [str(PYTHON), str(ROOT / "server" / "server.py")],
            cwd=str(ROOT), creationflags=subprocess.CREATE_NO_WINDOW,
        )
    if not _is_alive("streamlit"):
        print("[watch] CorelChamp (Streamlit) эхлүүлж байна…")
        _procs["streamlit"] = subprocess.Popen(
            [str(STREAMLIT), "run", "server/app.py", "--server.port", "8501", "--server.headless", "true"],
            cwd=str(ROOT), creationflags=subprocess.CREATE_NO_WINDOW,
        )


def _stop_all():
    for name in ("mcp", "streamlit"):
        p = _procs.get(name)
        if p and p.poll() is None:
            print(f"[watch] CorelDRAW хаагдлаа → {name} зогсоож байна…")
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        _procs.pop(name, None)


def main() -> int:
    print(f"[watch] CorelDRAW-г ажиглаж байна (жижиг зогсолт: {POLL_SECONDS}с)… Ctrl+C дарж зогсооно.")
    was_running = False
    try:
        while True:
            now_running = _coreldraw_running()
            if now_running and not was_running:
                _start_all()
            elif not now_running and was_running:
                _stop_all()
            was_running = now_running
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\n[watch] Зогсож байна…")
        _stop_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
