## Branding and Tray Artwork, used by both the Python source and bundled app (.exe)
from pathlib import Path

from PIL import Image

# Sets the app name and the tray icon names, stored in the assets folder
APP_NAME = "VSLink"
TRAY_ICON_NAMES = ("error", "offline", "online", "1-connected", "2-connected",
                   "3-connected", "4-connected")

# Sets the asset path as the parent folder of this file and then the assets folder
def asset_path(filename):
    return Path(__file__).resolve().parent / "assets" / filename

# Sets the tray icon to be used
def tray_icon_name(status):
    # Sets the values of the transports to the status of Wi-Fi and Bluetooth
    transports = (status.wifi, status.bluetooth)
    # Prioritises error states, showing the error icon
    if any(transport.error or transport.state == "Error" for transport in transports):
        return "error"
    # Then checks if any controllers are connected, setting the state to that amount of controllers
    if status.controllers > 0:
        return f"{min(status.controllers, 4)}-connected"
    # Then checks if the transports are online, setting the state to online
    if status.wifi.state == "Listening" or status.bluetooth.state == "Advertising":
        return "online"
    # If none of the above conditions are met, set the state to offline
    return "offline"

# Loads the tray icons from the assets folder once, returning a dictionary of images
def load_tray_icons():
    images = {}
    for name in TRAY_ICON_NAMES:
        with Image.open(asset_path(name + ".png")) as image:
            images[name] = image.convert("RGBA")
    return images
