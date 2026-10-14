"""Local native runner: OCR state, click OCR text by ID, press controller buttons, screenshot."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from ocr import recognize

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("command", choices=["status", "press", "shot", "state", "click", "settings", "controller"])
p.add_argument("value", nargs="?")
p.add_argument("--socket", default=f"/tmp/nsp-dawrin-{os.getuid()}.sock")
p.add_argument("--game-dir", type=Path, default=Path(os.environ.get("GAME_DIR", "../work/session")))
p.add_argument("--json", action="store_true", help="Print structured OCR state")
p.add_argument("--settle", type=float, default=1.0, help="Seconds after input before OCR")
p.add_argument("--ocr", choices=["auto", "vision", "tesseract"], default="auto")
args = p.parse_args()
root = Path(__file__).resolve().parents[2]
ui_dir = args.game_dir.resolve()
ui_dir.mkdir(parents=True, exist_ok=True)
state_file = ui_dir / "ui-state.json"

def send(command):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(3)
        s.connect(args.socket)
        s.sendall((command + "\n").encode())
        data = bytearray()
        while b"\n" not in data:
            part = s.recv(4096)
            if not part or len(data)+len(part)>65536:
                raise RuntimeError("Invalid control response")
            data.extend(part)
        reply = json.loads(data)
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return reply

def screenshot(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    before = path.stat().st_mtime_ns if path.exists() else 0
    send("shot " + str(path))
    deadline = time.monotonic() + 5
    while not path.exists() or path.stat().st_mtime_ns == before:
        if time.monotonic() > deadline:
            raise TimeoutError("GPU screenshot was queued but not written")
        time.sleep(0.05)
    return path

def state():
    started = time.monotonic()
    image = screenshot(ui_dir / "ui-current.png")
    data = recognize(image, args.ocr)
    data["runtime"] = send("status")
    data["captured_at"] = time.time()
    data["elapsed_ms"] = round((time.monotonic()-started)*1000)
    data["elements"].sort(key=lambda e: (round(e["bounds"][1]/20), e["bounds"][0]))
    for i, e in enumerate(data["elements"], 1):
        e["id"] = i
        e["interaction"] = "touch target, not yet verified"
        x,y,w,h=e["bounds"]
        e["touch"] = [min(1279,round((x+w/2)*1280/data["width"])),min(719,round((y+h/2)*720/data["height"]))]
    state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    with (ui_dir / "ui-history.jsonl").open("a") as log:
        log.write(json.dumps(data, ensure_ascii=False) + "\n")
    if args.json:
        print(json.dumps(data, ensure_ascii=False))
    else:
        print(f"frame={data['runtime']['frames']} source={data['source']} time={data['elapsed_ms']}ms (text regions; not verified buttons)")
        for e in data["elements"]:
            print(f"[{e['id']}] {e['text']}  @ {e['touch'][0]},{e['touch'][1]}")
    return data

if args.command == "state":
    state()
elif args.command == "click":
    data=json.loads(state_file.read_text())
    if data["runtime"]["pid"] != send("status")["pid"]:
        raise RuntimeError("Runner restarted; request state again")
    if time.time()-data.get("captured_at",0)>60:
        raise RuntimeError("OCR state expired; request state again")
    e=next(e for e in data["elements"] if e["id"]==int(args.value))
    x,y=e["touch"]
    try:
        send(f"touch 1 {x} {y}")
        time.sleep(0.4)
    finally:
        send(f"touch 0 {x} {y}")
    time.sleep(args.settle)
    state()
elif args.command == "press":
    buttons = dict(A=0, B=1, X=2, Y=3, L=6, R=7, ZL=8, ZR=9, PLUS=10, MINUS=11, LEFT=12, UP=13, RIGHT=14, DOWN=15,
                   LLEFT=16,LUP=17,LRIGHT=18,LDOWN=19,RLEFT=20,RUP=21,RRIGHT=22,RDOWN=23)
    try:
        print(send(f"buttons {1 << buttons[args.value.upper()]}"))
        time.sleep(0.3)
    finally:
        send("buttons 0")
elif args.command == "shot":
    if not args.value:
        p.error("shot requires a path")
    print(screenshot(args.value))
elif args.command == "status":
    print(send("status"))
elif args.command == "settings":
    print(json.dumps(send("settings" + (" " + args.value if args.value else "")), indent=2))
elif args.command == "controller":
    if not args.value:
        p.error("controller requires auto, none, or a device ID from settings")
    print(json.dumps(send("settings controller " + args.value), indent=2))
