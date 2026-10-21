# VSLink

A Windows system tray server for [VirtuaStick](https://jackjburnett.github.io/VirtuaStick/).
The tray runs **Wi-Fi (WebSocket) and Bluetooth LE simultaneously** through
`VSLink.py`, with one shared Gamepad Manager and Gamepad Parser. The
controller packet format and mappings are unchanged.

## Run the tray application

Use Windows 10/11 x64 and the
[ViGEmBus driver](https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0).
Bluetooth additionally needs an adapter with BLE peripheral support. Wi-Fi can
continue working if Bluetooth is unavailable or disabled.
The executable includes Python and its application dependencies. ViGEmBus remains
a separate installation.

Double-click `dist\tray\VSLink.exe`. On the first launch, the
application starts BLE advertising and a WebSocket listener on **TCP port 8000**.
It appears in the Windows notification area; it may be inside the
tray overflow menu. It has no console or main window.

Right-click the icon for:

- Wi-Fi/Bluetooth status and a combined connected controller count.
- **Enable Wi-Fi**, **Enable Bluetooth**, and **Restart Connections**.
- **Show Status**, also available by left-clicking the icon.
- **Settings > Connection Settings...** for the Wi-Fi port and transport toggles.
- **Settings > Start with Windows**, an optional per-user setting, off by default.
- **Open Logs** and **Exit**.

The tray uses the VSLink PNGs in `assets/` and updates automatically:

| Icon | State |
| --- | --- |
| `error.png` | A transport has failed; the status window shows the error. |
| `offline.png` | No transport is ready, including startup or both transports disabled. |
| `online.png` | Wi-Fi is listening or Bluetooth is advertising, with no controllers connected. |
| `1-connected.png` through `4-connected.png` | One through four controllers connected across both transports. |

An error takes priority over connected artwork; the tooltip and menu still show
the controller count. The PNGs load directly through Pillow, so separate `.ico`
files are only needed for the executable/window icon (`assets/favicon.ico`).

Closing a settings/status window leaves the receiver running. Disabling a
transport releases its controllers. Changing the port restarts only Wi-Fi,
disconnecting Wi-Fi clients; BLE controllers stay connected. Restart Connections
restarts the enabled transports. Exit closes sockets, stops advertising,
releases inputs, and waits for the worker to finish. A second tray copy exits
without creating another receiver.

Stop standalone `BLE.py`, `WiFI.py`, or `VSLink.py` instances before using
the tray application. Keep the
executable in a permanent location before enabling Start with Windows, because
the setting records its path. Bluetooth failures appear in the tray status and
log; restore the radio and choose Restart Connections to retry.

## Run from source

Use a working Python environment (the build was verified with Python 3.13 x64):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pythonw.exe Receiver.pyw
```

For a visible development terminal, use `python.exe Receiver.pyw` with the same
environment. Application output still goes to the log file. The optional
`--no-bluetooth` and `--no-wifi` arguments start the tray with the chosen transport
stopped. `--port 9000` overrides the saved port for that launch. CLI overrides
are not saved unless you subsequently save settings in the tray.

For the combined receiver without a tray:

```powershell
.\.venv\Scripts\python.exe VSLink.py
# Or choose a port / run Wi-Fi only:
.\.venv\Scripts\python.exe VSLink.py --port 9000 --no-bluetooth
```

Press Ctrl+C to shut down the console receiver and release its controllers.
Both entry points load the same per-user settings file:
`%LOCALAPPDATA%\VSLink\settings.json`. Tray changes are saved
automatically. The default port is 8000; valid ports are 1 through 65535.
`VLR_CONFIG_DIR` can override the settings directory for portable installs/tests.

## Connect over Wi-Fi

Connect the phone to the same local network and open a WebSocket connection to
`ws://<PC's LAN IPv4 address>:8000`, substituting the port if changed. The receiver
binds `0.0.0.0` (all IPv4 interfaces), so use the PC's LAN address on the phone.
Allow the receiver through Windows Firewall on your private network if prompted.
It does not configure router forwarding or change firewall rules itself.

Send one existing command per WebSocket message, e.g. `A_PRESS`, then `A_RELEASE`.
Xbox/PS switching uses `Change gamepad type to: PS` or `Change gamepad type to: XBOX`,
just like BLE. Wi-Fi allocates a controller at connection; BLE allocates one at
its first write. Normal closure, network failure detection, disabling a transport,
and Exit reset/release the affected controller inputs.

The default limit is **four controllers total across both transports**, matching
the initial project target and the four user slots supported by
[XInput](https://learn.microsoft.com/en-us/windows/win32/xinput/getting-started-with-xinput).
It is an application policy, not a BLE connection limit. Other physical XInput
controllers can occupy Windows slots too; this limit does not reserve those slots.
Support above four would depend on the controller type and the game's input API.

## Build the executable

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath dist/tray --workpath build/tray Receiver.spec
```

The result is a single `dist\tray\VSLink.exe`. The
`Receiver.spec` discovers the installed WinRT and ViGEm client libraries; it has
no machine-specific DLL paths and includes both transports, the settings UI,
the state PNGs, and the VSLink favicon. After replacing an older executable,
enable Start with Windows again to register the new executable path.

## Modules and logging

- `Receiver.pyw` starts the console-free tray application.
- `TrayApp.py` owns the tray icon, menus, startup setting, and rotating logs.
- `AppBranding.py` selects the status artwork and locates bundled branding assets.
- `VSLink.py` coordinates both transports on one asyncio worker, so all
  controller creation, parsing, and cleanup happen on the same thread.
- `ControllerRouter.py` shares controller ownership, type switching and the total
  controller limit. IDs use `wifi:` and `ble:` prefixes to avoid collisions.
- `WebSocketServer.py` and `BLE.py` implement their respective connection lifecycles
  and forward commands to the shared router.
- `AppSettings.py` validates and persists the port and transport enable settings.
- `GamepadManager.py`, `GamepadParser.py`, and `data_store/` retain their mappings.
- `BluetoothManager.py` remains available for standalone BLE-only embedding; the
  tray uses the combined coordinator instead.

Logs are stored in
`%LOCALAPPDATA%\VSLink\logs\receiver.log`, with three rotating
backups. Existing gamepad print output is captured there too. Per-packet logging
stays off during normal play. `VLR_LOG_DIR` can override the log folder for a
portable install or isolated test.

The legacy `WiFI.py` entry point remains available for Wi-Fi-only terminal use;
its default bind address/port are now `0.0.0.0:8000`. For shared settings and
controller ownership, use `VSLink.py` or the tray instead of launching
separate transport processes.

## Standalone BLE testing

Run a standalone Windows BLE peripheral using the existing Gamepad Manager and
Parser. Controller mappings and the BLE service/characteristic UUIDs are unchanged.

```powershell
python -m pip install -r requirements.txt
python BLE.py
```

Use a working Python 3.9–3.13 installation, ViGEmBus, and a Windows Bluetooth
adapter that supports BLE peripheral mode. The script checks the adapter and
radio before starting. Stop it with Ctrl+C to stop advertising and release inputs.

For discovery, keep `BLE.py` running until it prints `Advertising service ...`.
Use a BLE scanner such as [nRF Connect for Mobile](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-mobile)
on Android/iOS, or your Unity app's BLE scan. The phone's normal Bluetooth pairing
screen may not list this custom service. Allow the scanner's requested Bluetooth
permissions, scan nearby devices, and identify the advertised service UUID below.
The device name may be missing or different from the PC name. Connect inside the
BLE app; this prototype does not require pairing in the phone's settings.

If the custom service is missing and only standard services appear, disconnect
the phone, restart the receiver, and wait for `Windows advertising state: STARTED`
before reconnecting. In nRF Connect for Android, use the connected device's
three-dot menu **Refresh services** (or **Refresh device cache**, depending on
connection state/version), then discover services again. Android may retain a
service list from before the receiver was started; see
[Nordic's service cache troubleshooting](https://devzone.nordicsemi.com/f/nordic-q-a/38930/can-t-discover-custom-service-on-android-phone/150694).
Identify the scanner entry by its advertised service UUID rather than only the
PC name. If that UUID is absent from advertisements, or the service remains
missing after refreshing, capture the receiver's startup output with `--verbose`.
The local creation/advertising messages do not prove discovery on a physical phone.

In the Unity mobile app (or a BLE test app), scan for service UUID
`d749b3ea-d666-4f2f-b49d-3e43fc6db631`, connect, and write UTF-8 commands to
characteristic `d749b3ea-d666-4f2f-b49d-3e43fc6db632`. Send one complete existing
command per write, for example `A_PRESS`, `A_RELEASE`,
`LEFT_JOYSTICK_-1.0_0.0`, or `Change gamepad type to: PS`. Writes with or without
response are supported. Start testing with writes with response so errors are
visible. Each command must fit the phone's negotiated ATT write size; this
prototype does not reassemble split writes or batch commands.

To test input, write `A_PRESS` in text/UTF-8 mode with response, then write
`A_RELEASE` as a separate command. Run `python BLE.py --log-input` to log payloads,
for example `BLE received: b'A_PRESS' (7 bytes)`, after updating the controller.
Normal operation leaves per-packet logging off to reduce console I/O in the input
path. Restart `BLE.py` after updating the script. Add `--verbose` to also see each Windows `WriteRequested`
event and the decoded command. If neither appears, check that you are writing to
the input characteristic above rather than a descriptor or another service.

To investigate delay, run `python BLE.py --timings` for a short test. It reports
queueing, Windows request retrieval, and controller processing time from the
Windows write callback to the gamepad update. It does not measure the phone's
input handling, Bluetooth airtime, or the game's display latency. The first
command also creates the virtual controller; compare later commands separately.
Disable timing/debug output when measuring normal play.

For repeated input, the phone can use Write Without Response (`Command` in many
BLE scanners), which avoids waiting for an ATT response between queued writes.
The sender must respect its platform's queue/backpressure limits and preserve
press/release order. This does not set the BLE connection interval or guarantee
lower latency for a single write. Android apps can request
[high-priority connection parameters](https://developer.android.com/reference/android/bluetooth/BluetoothGatt#requestConnectionPriority(int));
on iOS, respect
[write-without-response readiness](https://developer.apple.com/documentation/corebluetooth/cbperipheral/cansendwritewithoutresponse).

Each phone's first input write creates its own Xbox controller (up to four BLE
clients). GATT session closure deletes that phone's controller through the
existing manager, which resets its inputs. A discovered/connected phone that has
not written input does not yet allocate a controller. Type switching follows the
existing WebSocket behavior. Use the combined receiver for Wi-Fi and BLE together
with a shared controller limit and one worker.

The characteristic uses plain writes without pairing/authentication; this is a
local prototype. Adapter or advertising failures stop the script and clean up;
rerun it after restoring Bluetooth. Android/iPhone discovery, input writes,
disconnect events, and multiple concurrent phones still need physical testing.
See [Microsoft's Windows GATT server documentation](https://learn.microsoft.com/en-us/windows/apps/develop/devices-sensors/gatt-server)
and [PyWinRT](https://pywinrt.readthedocs.io/en/latest/) for the native API bindings.

- The `.exe` bundles Python and all dependencies, users do not need Python installed.  
- Users must have ViGEmBus installed for virtual controllers to work.  
- The project currently targets Windows x64. For x86, a separate build is required.

---

## License

This project is licensed under the GNU General Public License (GPL). See the LICENSE file for details.

---

## Contact

For any issues or questions, contact [jackjburnett](https://github.com/jackjburnett).
