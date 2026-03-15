"""Serial scan utility for Thermal USB Camera (IR8062 / Thermal Camera HAT variant)

Purpose:
 1. List all serial (COM) ports
 2. Try given (or common) baud rates to see if the device outputs raw frame data automatically
 3. Show a short hex preview and simple statistics (byte rate)
 4. Optionally send a handshake (hex bytes) once after opening to trigger streaming if required

Usage examples (PowerShell):
  python scan_ir_serial.py --port COM16
  python scan_ir_serial.py --port COM16 --baud 1500000 --seconds 3
  python scan_ir_serial.py --auto --seconds 2
  python scan_ir_serial.py --port COM16 --handshake A5 5A 01 FB --seconds 3

Caution:
 - Only use --handshake if you are sure about the protocol or after passive attempts show no data.
 - Do NOT send random bytes repeatedly; keep it one-shot unless specified.

Output interpretation:
 - If 'Received: 0 bytes' for all baud rates -> very likely not a classic serial stream OR needs a start command OR wrong port.
 - If you see repeating patterns / stable byte rate -> capture that hex for parser design.

Save dump:
  Use --dump dump.bin to save raw bytes (first N seconds).

Author: helper utility
"""
from __future__ import annotations
import sys
import time
import argparse
from pathlib import Path
from typing import List

try:
    import serial  # type: ignore
    import serial.tools.list_ports as list_ports  # type: ignore
except Exception as e:  # pragma: no cover
    print("[ERR] pyserial not installed. Install with: pip install pyserial")
    raise

COMMON_BAUDS = [1500000, 921600, 460800, 230400, 115200, 256000, 128000, 57600, 38400, 19200, 9600]

# A small curated set of low‑risk probe sequences (avoid spamming random binary)
# These try patterns like 0x5A 0x5A header, simple length=0 frames, ASCII queries.
PROBE_SEQUENCES = [
    bytes.fromhex("5A 5A"),               # possible sync/header
    b"?",                                # generic query
    b"AT\r",                             # very common (unlikely but safe)
    bytes.fromhex("5A 5A 01 00 00"),      # header + minimal payload guess
    bytes.fromhex("A5 5A 01 FB"),         # user earlier hypothetical handshake
]


def list_all_ports():
    ports = list_ports.comports()
    if not ports:
        print("No serial ports found.")
        return []
    print("Available ports:")
    for p in ports:
        print(f"  {p.device:>8} | {p.description}")
    return [p.device for p in ports]


def open_and_capture(port: str, baud: int, seconds: float, handshake: List[int] | None, dump_path: Path | None,
                     toggle_dtr: bool, toggle_rts: bool, probe: bool, quiet: bool, idle_before: float, idle_after: float):
    print(f"\n--- Port={port} Baud={baud} Capture {seconds}s (pre-wait {idle_before}s / post-wait {idle_after}s) ---")
    try:
        with serial.Serial(port=port, baudrate=baud, timeout=0.05) as ser:
            # Optionally set & toggle control lines (some devices start streaming when DTR asserted)
            if toggle_dtr:
                ser.dtr = False
                time.sleep(0.05)
                ser.dtr = True
                print("[INFO] Toggled DTR -> True")
            if toggle_rts:
                ser.rts = False
                time.sleep(0.05)
                ser.rts = True
                print("[INFO] Toggled RTS -> True")

            # initial idle wait (device might need time after open)
            if idle_before > 0:
                time.sleep(idle_before)

            # Optional single handshake sequence
            if handshake:
                hs_bytes = bytes(handshake)
                print(f"Sending handshake: {' '.join(f'{b:02X}' for b in hs_bytes)}")
                ser.write(hs_bytes)
                ser.flush()
                time.sleep(0.15)

            # Probe sequence set (only if no explicit handshake provided OR user explicitly wants both)
            if probe:
                print("[INFO] Running probe sequences (one-shot each, short delay)...")
                for seq in PROBE_SEQUENCES:
                    try:
                        ser.write(seq)
                        ser.flush()
                        if not quiet:
                            printable = ' '.join(f"{b:02X}" for b in seq) if any(b < 0x20 or b>0x7E for b in seq) else seq.decode(errors='ignore')
                            print(f"  sent: {printable}")
                        time.sleep(0.12)
                    except Exception as _e:  # pragma: no cover
                        print(f"  [WARN] probe send failed: {_e}")

            start = time.time()
            data = bytearray()
            while time.time() - start < seconds:
                waiting = ser.in_waiting
                if waiting:
                    chunk = ser.read(waiting)
                    data.extend(chunk)
                else:
                    # short sleep to avoid busy loop
                    time.sleep(0.01)
            total = len(data)
            dur = max(time.time() - start, 1e-6)
            rate = total / dur
            print(f"Received: {total} bytes  ({rate:.1f} B/s)")
            if total:
                preview = ' '.join(f"{b:02X}" for b in data[:64])
                print(f"Hex preview (first {min(64,total)}): {preview}")
                if dump_path:
                    dump_path.write_bytes(data)
                    print(f"Raw bytes saved to: {dump_path}")
            else:
                print("No data.")

            # Post-wait observe (maybe device starts after initial command)
            if idle_after > 0:
                time.sleep(idle_after)
                waiting2 = ser.in_waiting
                if waiting2:
                    extra = ser.read(waiting2)
                    print(f"[LATE] +{len(extra)} bytes after post-wait")
                    if dump_path and not total:
                        dump_path.write_bytes(extra)
                        print(f"Raw bytes (late) saved to: {dump_path}")
                    if extra:
                        preview2 = ' '.join(f"{b:02X}" for b in extra[:64])
                        print(f"Late hex preview: {preview2}")
    except Exception as e:
        print(f"[FAIL] {e}")


def parse_handshake(hex_list: List[str]) -> List[int]:
    out = []
    for h in hex_list:
        h2 = h.strip().replace('0x','')
        if not h2:
            continue
        out.append(int(h2, 16) & 0xFF)
    return out


def main():
    ap = argparse.ArgumentParser(description="Scan IR thermal serial output")
    ap.add_argument('--port', type=str, help='Specific COM port (e.g. COM16)')
    ap.add_argument('--baud', type=int, help='Single baud to test (default: try common list)')
    ap.add_argument('--auto', action='store_true', help='Scan all detected ports with common baud list')
    ap.add_argument('--seconds', type=float, default=2.0, help='Capture seconds per test')
    ap.add_argument('--handshake', nargs='*', help='Optional hex bytes to send once as handshake (e.g. A5 5A 01 FB)')
    ap.add_argument('--dump', type=str, help='Path to save raw bytes of last capture')
    ap.add_argument('--probe', action='store_true', help='Send built-in safe probe sequences (after optional handshake)')
    ap.add_argument('--toggle-dtr', action='store_true', help='Toggle & assert DTR before capture')
    ap.add_argument('--toggle-rts', action='store_true', help='Toggle & assert RTS before capture')
    ap.add_argument('--quiet', action='store_true', help='Less verbose (don\'t print each probe sequence detail)')
    ap.add_argument('--idle-before', type=float, default=0.2, help='Seconds wait after open (before any send)')
    ap.add_argument('--idle-after', type=float, default=0.0, help='Seconds wait after capture to check late bytes')
    args = ap.parse_args()

    ports = list_all_ports()
    if not ports:
        return

    handshake = parse_handshake(args.handshake) if args.handshake else None
    dump_path = Path(args.dump) if args.dump else None

    targets = []
    if args.auto:
        for p in ports:
            targets.append(p)
    elif args.port:
        targets.append(args.port)
    else:
        print("Specify --port or use --auto to scan all.")
        return

    baud_list = [args.baud] if args.baud else COMMON_BAUDS

    for p in targets:
        for b in baud_list:
            open_and_capture(
                port=p,
                baud=b,
                seconds=args.seconds,
                handshake=handshake,
                dump_path=dump_path,
                toggle_dtr=args.toggle_dtr,
                toggle_rts=args.toggle_rts,
                probe=args.probe,
                quiet=args.quiet,
                idle_before=args.idle_before,
                idle_after=args.idle_after,
            )

if __name__ == '__main__':
    main()
