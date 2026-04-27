import sys
from typing import Optional
from dataclasses import dataclass

if sys.platform == "win32":
    import win32com.client
    import pythoncom

@dataclass
class ConnectionConfig:
    max_retries: int = 3
    retry_delay: float = 1.0
    app_name: str = "CorelDRAW.Application"
    visible: bool = True
    reconnect_on_failure: bool = True

@dataclass
class ConnectionStatus:
    connected: bool = False
    app_running: bool = False
    version: Optional[str] = None
    last_error: Optional[str] = None

class CorelDrawConnection:
    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self._app = None
        self._status = ConnectionStatus()

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

        try:
            pythoncom.CoInitialize()
            try:
                self._app = win32com.client.GetActiveObject(self.config.app_name, keep=True)
            except Exception:
                self._app = win32com.client.Dispatch(self.config.app_name)
                self._app.Visible = self.config.visible

            version = self._app.Version
            self._status = ConnectionStatus(connected=True, app_running=True, version=version)
            return True

        except Exception as e:
            self._status = ConnectionStatus(connected=False, app_running=False, last_error=str(e))
            return False

    def disconnect(self) -> None:
        if self._app is not None:
            try:
                self._app.Quit()
            except Exception:
                pass
            self._app = None
            self._status = ConnectionStatus()
            if sys.platform == "win32":
                pythoncom.CoUninitialize()

    def reconnect(self) -> bool:
        self.disconnect()
        import time
        time.sleep(self.config.retry_delay)
        return self.connect()

    def is_alive(self) -> bool:
        if not self._app or not self._status.connected:
            return False
        try:
            _ = self._app.ActiveDocument
            return True
        except Exception:
            return False

    def safe_call(self, func, *args, **kwargs):
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                result = func(*args, **kwargs)
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