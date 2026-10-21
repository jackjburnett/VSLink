"""VSLink's Windows tray shell for the shared Wi-Fi and BLE receiver."""

import argparse
import ctypes
import io
import logging
import os
import subprocess
import sys
import threading
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pystray

from AppBranding import APP_NAME, asset_path, load_tray_icons, tray_icon_name
from AppSettings import SettingsStore
from VSLink import VirtualLeverless

logger = logging.getLogger(__name__)


class _LogStream(io.TextIOBase):
    def write(self, value):
        if value.strip():
            logging.getLogger("gamepad").info(value.rstrip())
        return len(value)

    def flush(self):
        pass


def configure_logging(directory=None):
    # This can be overridden for portable installs and isolated smoke tests.
    directory = Path(directory or os.environ.get("VLR_LOG_DIR") or (
        Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VSLink" / "logs"
    ))
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "receiver.log", maxBytes=2_000_000,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    # Existing parser/manager print calls also work in a console-free executable.
    sys.stdout = _LogStream()
    sys.stderr = _LogStream()
    sys.excepthook = lambda kind, value, trace: logger.error(
        "Unhandled exception", exc_info=(kind, value, trace))
    return directory


class WindowsStartup:
    key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    value_name = APP_NAME
    legacy_value_name = "VirtualLeverlessReceiver"

    def __init__(self):
        if getattr(sys, "frozen", False):
            arguments = [sys.executable]
        else:
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            arguments = [str(pythonw if pythonw.exists() else Path(sys.executable)),
                         str(Path(__file__).with_name("Receiver.pyw"))]
        self.command = subprocess.list2cmdline(arguments)

    def enabled(self):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key) as key:
                for name in (self.value_name, self.legacy_value_name):
                    try:
                        if winreg.QueryValueEx(key, name)[0] == self.command:
                            return True
                    except FileNotFoundError:
                        pass
        except OSError:
            pass
        return False

    def set_enabled(self, enabled):
        import winreg
        if enabled:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.key) as key:
                winreg.SetValueEx(key, self.value_name, 0, winreg.REG_SZ, self.command)
                try:
                    winreg.DeleteValue(key, self.legacy_value_name)
                except FileNotFoundError:
                    pass
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key, 0, winreg.KEY_SET_VALUE) as key:
                    for name in (self.value_name, self.legacy_value_name):
                        try:
                            winreg.DeleteValue(key, name)
                        except FileNotFoundError:
                            pass
            except FileNotFoundError:
                pass


class TrayApplication:
    def __init__(self, log_directory, manager=None, settings=None, settings_store=None):
        self.settings_store = settings_store if settings_store is not None else SettingsStore()
        self.manager = manager if manager is not None else VirtualLeverless(
            settings if settings is not None else self.settings_store.load())
        self.log_directory = Path(log_directory)
        self.startup = WindowsStartup()
        self._closing = threading.Event()
        self._status_requested = threading.Event()
        self._settings_requested = threading.Event()
        self._settings_lock = threading.Lock()
        self._settings_window = None
        self._status_window = None
        self._status_label = None
        self._tray_images = load_tray_icons()
        self._icon_name = tray_icon_name(self.manager.status)
        item = pystray.MenuItem
        self.icon = pystray.Icon(APP_NAME, self._tray_images[self._icon_name], APP_NAME, pystray.Menu(
            item(lambda _: f"Wi-Fi: {self.manager.status.wifi.state} (port {self.manager.status.wifi_port})", None, enabled=False),
            item(lambda _: f"Bluetooth: {self.manager.status.bluetooth.state}", None, enabled=False),
            item(lambda _: f"Controllers: {self.manager.status.controllers}/4", None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("Enable Wi-Fi", lambda: self.toggle_transport("wifi"),
                 checked=lambda _: self.manager.settings.wifi_enabled),
            item("Enable Bluetooth", lambda: self.toggle_transport("bluetooth"),
                 checked=lambda _: self.manager.settings.bluetooth_enabled),
            item("Restart Connections", lambda: self.manager.restart()),
            item("Show Status", self.show_status, default=True),
            item("Settings", pystray.Menu(
                item("Connection Settings...", self.show_settings),
                item("Start with Windows", self.toggle_startup, checked=lambda _: self.startup.enabled()),
            )),
            item("Open Logs", lambda: os.startfile(str(self.log_directory))),
            pystray.Menu.SEPARATOR,
            item("Exit", self.exit),
        ))

    def show_status(self):
        # Return to pystray immediately; all windows belong to the main Tk loop.
        self._status_requested.set()

    def _status_message(self):
        status = self.manager.status
        message = (f"Wi-Fi: {status.wifi.state} (port {status.wifi_port})\n"
                   f"Bluetooth: {status.bluetooth.state}\n"
                   f"Connected controllers: {status.controllers}/4\n"
                   f"Wi-Fi controllers: {status.wifi.controllers}\n"
                   f"Bluetooth controllers: {status.bluetooth.controllers}")
        for name, transport in (("Wi-Fi", status.wifi), ("Bluetooth", status.bluetooth)):
            if transport.error:
                message += f"\n\n{name}: {transport.error}"
        message += f"\n\nLogs: {self.log_directory}"
        return message

    def _open_status(self, root):
        import tkinter as tk
        from tkinter import ttk
        if self._status_window is not None and self._status_window.winfo_exists():
            self._present_window(self._status_window)
            return
        window = self._status_window = tk.Toplevel(root)
        window.title(f"{APP_NAME} Status")
        window.iconbitmap(str(asset_path("favicon.ico")))
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=20)
        frame.grid()
        self._status_label = ttk.Label(frame, text=self._status_message(),
                                       justify="left", wraplength=560)
        self._status_label.grid(row=0, column=0, sticky="w")
        button = ttk.Button(frame, text="OK", command=window.destroy)
        button.grid(row=1, column=0, sticky="e", pady=(16, 0))
        window.protocol("WM_DELETE_WINDOW", window.destroy)
        window.bind("<Return>", lambda _: window.destroy())
        window.bind("<Escape>", lambda _: window.destroy())
        button.focus_set()
        self._present_window(window)

    @staticmethod
    def _present_window(window):
        # Restore minimized windows too. Briefly raise above other apps only in
        # response to the user's tray action; don't leave an always-on-top window.
        window.deiconify()
        window.lift()
        window.attributes("-topmost", True)

        def focus():
            if window.winfo_exists():
                window.attributes("-topmost", False)
                window.focus_force()

        window.after_idle(focus)

    def apply_settings(self, **changes):
        with self._settings_lock:
            settings = replace(self.manager.settings, **changes)
            self.settings_store.save(settings)
            self.manager.configure(settings)

    def toggle_transport(self, name):
        try:
            field = name + "_enabled"
            self.apply_settings(**{field: not getattr(self.manager.settings, field)})
        except (OSError, ValueError):
            logger.exception("Unable to save connection settings")
            self.icon.notify(f"Could not save settings. Check the {APP_NAME} log.", APP_NAME)

    def show_settings(self):
        # Tray callbacks run on pystray's thread; Tk stays on the main UI thread.
        self._settings_requested.set()

    def _process_ui_requests(self, root):
        if self._status_requested.is_set():
            self._status_requested.clear()
            self._open_status(root)
        if self._settings_requested.is_set():
            self._settings_requested.clear()
            self._open_settings(root)
        if self._status_window is not None and self._status_window.winfo_exists():
            message = self._status_message()
            if self._status_label.cget("text") != message:
                self._status_label.configure(text=message)

    def _open_settings(self, root):
        import tkinter as tk
        from tkinter import messagebox, ttk
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._present_window(self._settings_window)
            return
        window = self._settings_window = tk.Toplevel(root)
        window.title(f"{APP_NAME} Settings")
        window.iconbitmap(str(asset_path("favicon.ico")))
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=20)
        frame.grid()
        settings = self.manager.settings
        wifi = tk.BooleanVar(value=settings.wifi_enabled)
        bluetooth = tk.BooleanVar(value=settings.bluetooth_enabled)
        port = tk.StringVar(value=str(settings.wifi_port))
        ttk.Checkbutton(frame, text="Enable Wi-Fi", variable=wifi).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(frame, text="Enable Bluetooth LE", variable=bluetooth).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))
        ttk.Label(frame, text="Wi-Fi WebSocket port").grid(row=2, column=0, sticky="w", padx=(0, 14))
        ttk.Entry(frame, textvariable=port, width=10).grid(row=2, column=1, sticky="e")
        ttk.Label(frame, text="VirtuaStick connects to ws://<PC IP>:<port>\nChanging the port disconnects Wi-Fi controllers.").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=14)

        def save():
            try:
                self.apply_settings(wifi_enabled=wifi.get(), bluetooth_enabled=bluetooth.get(),
                                    wifi_port=int(port.get()))
            except ValueError:
                messagebox.showerror(APP_NAME, "Enter a port between 1 and 65535.", parent=window)
                return
            except OSError as exc:
                logger.exception("Unable to save connection settings")
                messagebox.showerror(APP_NAME, f"Could not save settings: {exc}", parent=window)
                return
            window.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save", command=save).pack(side="left")
        window.bind("<Return>", lambda _: save())
        window.bind("<Escape>", lambda _: window.destroy())
        self._present_window(window)

    def toggle_startup(self):
        try:
            self.startup.set_enabled(not self.startup.enabled())
        except OSError:
            logger.exception("Unable to change Windows startup setting")
            self.icon.notify(f"Could not update the startup setting. Check the {APP_NAME} log.", APP_NAME)

    def exit(self):
        self._closing.set()
        self.manager.shutdown()
        self.icon.stop()

    def _setup(self, icon):
        icon.visible = True
        self.manager.start()
        previous = None
        while not self._closing.wait(0.25):
            status = self.manager.status
            if status == previous:
                continue
            self._update_tray(status, previous)
            previous = status

    def _update_tray(self, status, previous=None):
        self.icon.title = (f"{APP_NAME}\nWi-Fi: {status.wifi.state}:{status.wifi_port} | "
                           f"BLE: {status.bluetooth.state}\nControllers: {status.controllers}/4")
        name = tray_icon_name(status)
        if name != self._icon_name:
            self.icon.icon = self._tray_images[name]
            self._icon_name = name
        self.icon.update_menu()
        errors = "\n".join(filter(None, (status.wifi.error, status.bluetooth.error)))
        if errors and (previous is None or (status.wifi.error, status.bluetooth.error) != (
                previous.wifi.error, previous.bluetooth.error)):
            self.icon.notify(errors, APP_NAME)

    def run(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.title(APP_NAME)
        root.iconbitmap(default=str(asset_path("favicon.ico")))
        root.protocol("WM_DELETE_WINDOW", self.exit)

        def poll():
            if self._closing.is_set():
                root.destroy()
                return
            self._process_ui_requests(root)
            root.after(100, poll)

        try:
            self.icon.run_detached(setup=self._setup)
            root.after(100, poll)
            root.mainloop()
        finally:
            self._closing.set()
            self.icon.stop()
            self.manager.close()


def main():
    arguments = argparse.ArgumentParser(description=f"{APP_NAME} Wi-Fi and BLE system tray server for VirtuaStick")
    arguments.add_argument("--no-bluetooth", action="store_true", help="Launch the tray with Bluetooth stopped")
    arguments.add_argument("--no-wifi", action="store_true", help="Launch the tray with Wi-Fi stopped")
    arguments.add_argument("--port", type=int, help="Override the saved Wi-Fi port for this launch")
    args = arguments.parse_args()
    log_directory = configure_logging()
    settings_store = SettingsStore()
    settings = settings_store.load()
    changes = {}
    if args.no_bluetooth:
        changes["bluetooth_enabled"] = False
    if args.no_wifi:
        changes["wifi_enabled"] = False
    if args.port is not None:
        changes["wifi_port"] = args.port
    try:
        settings = replace(settings, **changes)
    except ValueError as exc:
        arguments.error(str(exc))
    # Prevent a second tray instance from creating duplicate services/controllers.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    ctypes.set_last_error(0)
    # Retain the old mutex ID to prevent duplicate services with earlier versions.
    mutex = kernel.CreateMutexW(None, False, r"Local\VirtualLeverlessReceiver.Tray")
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if ctypes.get_last_error() == 183:
            logger.info("%s is already running", APP_NAME)
            return 0
        logger.info("Starting %s from %s", APP_NAME, sys.executable)
        TrayApplication(log_directory, settings=settings, settings_store=settings_store).run()
    except Exception:
        logger.exception("%s failed", APP_NAME)
        ctypes.windll.user32.MessageBoxW(None, f"{APP_NAME} could not run. Check:\n{log_directory}", APP_NAME, 0x10)
        return 1
    finally:
        kernel.CloseHandle(mutex)
    return 0
