"""Localhost command bridge (SRS 13: structured ops, one job at a time).

Sockets run on a worker thread (blocking accept/recv), but Blender data is only
touched on the main thread via a ``bpy.app.timers`` callback — bpy is not
thread-safe. Messages are 4-byte big-endian length-prefixed JSON.
"""
import json
import queue
import socket
import struct
import threading
import traceback

import bpy  # type: ignore

from . import builders, exporter, renderer, scene_inspector, validators
from .bridge_paths import BridgeWorkspaceResolver

_LOCAL = ("127.0.0.1", "localhost", "::1")


def _recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _recv_msg(conn):
    header = _recv_exact(conn, 4)
    if not header:
        return None
    (length,) = struct.unpack(">I", header)
    if length > 16 * 1024 * 1024:  # 16 MB cap (resource-bomb guard)
        return None
    payload = _recv_exact(conn, length)
    return json.loads(payload.decode("utf-8")) if payload else None


def _send_msg(conn, obj):
    data = json.dumps(obj).encode("utf-8")
    conn.sendall(struct.pack(">I", len(data)) + data)


def _blender_abspath(path):
    return bpy.path.abspath(path) if isinstance(path, str) and path.startswith("//") else path


def _dispatch(cmd, workspace):
    action = cmd["action"]
    if action == "ping":
        return {"ok": True, "pong": True}
    if action == "initialize":
        bpy.context.scene["task_id"] = cmd.get("task_id", "")
        return {"ok": True, "collections": list(builders.bpyutil.ensure_standard_collections().keys())}
    if action == "apply_recipe":
        return {"ok": True, "operations": builders.apply_recipe(cmd.get("recipe") or {"operations": []})}
    if action == "inspect":
        return {"ok": True, "inspection": scene_inspector.inspect_scene()}
    if action in ("render_preview", "render_final"):
        img = str(workspace.resolve_output(_blender_abspath(cmd["output"])))
        return {"ok": True, "render": renderer.render_still(
            img, cmd.get("budget") or {}, preview=(action == "render_preview"))}
    if action == "export_glb":
        glb = str(workspace.resolve_output(_blender_abspath(cmd["output"])))
        return {"ok": True, "export": exporter.export_glb(glb, cmd.get("manifest"))}
    return {"ok": False, "error": f"unhandled action {action}"}


class BridgeServer:
    def __init__(self, host="127.0.0.1", port=8765, safety_mode="strict", workspace_root="//artifacts"):
        if safety_mode == "strict" and host not in _LOCAL:
            raise ValueError("strict mode binds localhost only")
        self.host, self.port, self.safety_mode = host, port, safety_mode
        self.workspace_root = _blender_abspath(workspace_root)
        self.workspace = BridgeWorkspaceResolver(self.workspace_root)
        self._sock = None
        self._thread = None
        self._running = False
        self._jobs: "queue.Queue" = queue.Queue()

    def start(self):
        if self._running:
            return
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(1)
        self._sock.settimeout(0.5)
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        bpy.app.timers.register(self._process, persistent=True)

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

    def _accept_loop(self):
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                try:
                    cmd = _recv_msg(conn)
                    if cmd is None:
                        continue
                    err = validators.validate_command(cmd, self.safety_mode)
                    if err:
                        _send_msg(conn, {"ok": False, "error": err})
                        continue
                    result_q: "queue.Queue" = queue.Queue(maxsize=1)
                    self._jobs.put((cmd, result_q))
                    result = result_q.get(timeout=600)  # one job at a time
                    _send_msg(conn, result)
                except Exception as exc:
                    try:
                        _send_msg(conn, {"ok": False, "error": str(exc)})
                    except OSError:
                        pass

    def _process(self):
        if not self._running:
            return None
        try:
            cmd, result_q = self._jobs.get_nowait()
        except queue.Empty:
            return 0.1
        try:
            result_q.put(_dispatch(cmd, self.workspace))
        except Exception:
            result_q.put({"ok": False, "error": "exception", "trace": traceback.format_exc()})
        return 0.05


_SERVER = None


def start_bridge(host, port, safety_mode, workspace_root="//artifacts"):
    global _SERVER
    if _SERVER is None:
        _SERVER = BridgeServer(host, port, safety_mode, workspace_root)
    _SERVER.start()
    return _SERVER


def stop_bridge():
    global _SERVER
    if _SERVER is not None:
        _SERVER.stop()
        _SERVER = None
