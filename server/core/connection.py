import os
import sys
import queue
import threading
import time
from typing import Optional, Callable, Any
from dataclasses import dataclass

if sys.platform == "win32":
    import win32com.client
    import pythoncom


@dataclass
class ConnectionConfig:
    max_retries: int = 3
    retry_delay: float = 1.0
    app_name: str = os.environ.get("COREL_CORELDRAW_APP_NAME", "CorelDRAW.Application")
    visible: bool = True
    reconnect_on_failure: bool = False


@dataclass
class ConnectionStatus:
    connected: bool = False
    app_running: bool = False
    version: Optional[str] = None
    last_error: Optional[str] = None


class _COMTask:
    __slots__ = ("func", "args", "kwargs", "result", "error", "_done")

    def __init__(self, func: Callable, args: tuple, kwargs: dict):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result: Any = None
        self.error: Optional[Exception] = None
        self._done = threading.Event()

    def wait(self, timeout: float) -> Any:
        if not self._done.wait(timeout=timeout):
            raise TimeoutError(f"COM call timed out after {timeout}s")
        if self.error is not None:
            raise self.error
        return self.result


class _COMThread(threading.Thread):
    """Dedicated STA thread that owns all CorelDRAW COM objects.

    FastMCP HTTP mode dispatches sync tool functions via run_in_executor to a
    thread pool. COM STA objects cannot be called across thread boundaries
    (RPC_E_WRONG_THREAD). This thread serialises every COM operation so the
    calling thread's apartment never matters.
    """

    def __init__(self):
        super().__init__(daemon=True, name="COM-STA-Thread")
        self._queue: "queue.Queue[Optional[_COMTask]]" = queue.Queue()
        self._ready = threading.Event()
        self._running = True

    def run(self) -> None:
        if sys.platform == "win32":
            pythoncom.CoInitialize()
        self._ready.set()
        try:
            while True:
                task = self._queue.get()
                if task is None:
                    break
                try:
                    task.result = task.func(*task.args, **task.kwargs)
                except Exception as exc:
                    task.error = exc
                finally:
                    task._done.set()
        finally:
            if sys.platform == "win32":
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def call(self, func: Callable, *args, timeout: float = 60.0, **kwargs) -> Any:
        if not self._running:
            raise RuntimeError("COM thread has been shut down")
        task = _COMTask(func, args, kwargs)
        self._queue.put(task)
        return task.wait(timeout)

    def shutdown(self) -> None:
        self._running = False
        self._queue.put(None)


class CorelDrawConnection:
    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self._app = None
        self._status = ConnectionStatus()
        self._com_thread = _COMThread()
        self._com_thread.start()
        self._com_thread._ready.wait()

    @property
    def app(self):
        return self._app

    @property
    def status(self) -> ConnectionStatus:
        return self._status

    def connect(self) -> bool:
        if sys.platform != "win32":
            self._status.last_error = "Platform not supported"
            return False

        def _do_connect():
            try:
                return win32com.client.GetActiveObject(self.config.app_name)
            except Exception:
                app = win32com.client.Dispatch(self.config.app_name)
                app.Visible = self.config.visible
                return app

        try:
            self._app = self._com_thread.call(_do_connect)
            version = self._com_thread.call(lambda: self._app.Version)
            self._status = ConnectionStatus(connected=True, app_running=True, version=version)
            return True
        except Exception as e:
            self._status = ConnectionStatus(connected=False, app_running=False, last_error=str(e))
            return False

    def disconnect(self) -> None:
        # Release COM reference without calling Quit() — user owns CorelDRAW lifecycle.
        self._app = None
        self._status = ConnectionStatus()
        self._com_thread.shutdown()

    def reconnect(self) -> bool:
        self._app = None
        self._status = ConnectionStatus()
        # Replace the COM thread so the new connection gets a fresh STA.
        self._com_thread.shutdown()
        self._com_thread = _COMThread()
        self._com_thread.start()
        self._com_thread._ready.wait()
        time.sleep(self.config.retry_delay)
        return self.connect()

    def is_alive(self) -> bool:
        if not self._app or not self._status.connected:
            return False
        try:
            self._com_thread.call(lambda: self._app.ActiveDocument, timeout=5.0)
            return True
        except Exception:
            return False

    def safe_call(self, func, *args, **kwargs):
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                result = self._com_thread.call(func, *args, timeout=60.0, **kwargs)
                return {"success": True, "result": result}
            except Exception as e:
                last_error = str(e)
                if attempt < self.config.max_retries - 1 and self.config.reconnect_on_failure:
                    if not self.reconnect():
                        break
        return {"success": False, "result": None, "error": last_error or "Unknown error"}


_connection: Optional[CorelDrawConnection] = None


def get_connection() -> CorelDrawConnection:
    global _connection
    if _connection is None:
        _connection = CorelDrawConnection()
    return _connection


def init_connection(config: Optional[ConnectionConfig] = None) -> bool:
    global _connection
    _connection = CorelDrawConnection(config)
    return _connection.connect()


def close_connection() -> None:
    global _connection
    if _connection:
        _connection.disconnect()
        _connection = None
