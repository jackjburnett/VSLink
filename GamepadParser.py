"""
Gamepad Parser Module

This module handles parsing of gamepad input messages and updating virtual gamepad
instances accordingly. It maps string-based action commands to virtual gamepad
inputs using configurable action maps for different controller types.

Dependencies:
    time: Standard Python library for time-related functions (used in testing)
    vgamepad: A Python library for creating virtual gamepads that simulate
              Xbox 360 and PS4 controller input on Windows systems
    data_store.ACTION_MAP_DS4: Action mapping for PS4 (DS4) controller buttons
    data_store.ACTION_MAP_XBOX: Action mapping for Xbox 360 controller buttons  
    data_store.ACTION_MAP_JOYSTICK: Action mapping for joystick movements
    data_store.ACTION_MAP_TRIGGERS: Action mapping for trigger inputs

Functions:
    parse_gamepad(message, gamepad): Parse gamepad message and update virtual gamepad

The module supports both Xbox 360 and PS4 (DS4) virtual controllers with
comprehensive button, joystick, and trigger input handling.
"""

import time

import vgamepad as vg

import data_store.ACTION_MAP_DS4 as AMD
import data_store.ACTION_MAP_JOYSTICK as AMJ
import data_store.ACTION_MAP_TRIGGERS as AMT
import data_store.ACTION_MAP_XBOX as AMX


def parse_gamepad(message, gamepad):
    """
    Parse a gamepad message and update the virtual gamepad accordingly.

    Parameters:
        message (str): The gamepad message to parse.
        gamepad (vg.VX360Gamepad or vg.VDS4Gamepad): The virtual gamepad to update.
    """
    # Set the appropriate action map based on gamepad type
    if isinstance(gamepad, vg.VX360Gamepad):
        action_map = AMX.ACTION_MAP
    elif isinstance(gamepad, vg.VDS4Gamepad):
        action_map = AMD.ACTION_MAP
    else:
        print(f"Invalid gamepad type. Expected vg.VX360Gamepad or vg.VDS4Gamepad.")
        return
    try:
        # Retrieve the lambda function based on the message
        action = action_map.get(message)

        if action:
            # Execute the button action function
            action(gamepad)
        else:
            # Try joystick actions if no button action found
            if not AMJ.handle_joystick_action(message, gamepad):
                # Try trigger actions if no joystick action found
                if not AMT.handle_trigger_action(message, gamepad):
                    print(f"Unknown action: {message}")

        # Send the updates to the virtual gamepad
        gamepad.update()

    except Exception as e:
        # Handle any potential errors that occur during parsing or gamepad interaction
        print(f"Error parsing message: {e}")


# Tests the script if executed standalone
# For testing, go to https://hardwaretester.com/gamepad
if __name__ == "__main__":
    # Use the maps as the source of truth, including aliases and RESET.
    # Their insertion order keeps each press/release pair together.
    x_actions = list(AMX.ACTION_MAP)
    d_actions = list(AMD.ACTION_MAP)
    joystick_actions = [
        # Digital joystick directions are already covered by each action map.
        f"{side}_JOYSTICK_{x}_{y}"
        for side in ("LEFT", "RIGHT")
        for x, y in (
            (-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0),
            (-0.5, 0.5), (0.5, -0.5), (-2.0, 2.0), (2.0, -2.0),
            (0.0, 0.0),  # Return to neutral after each stick.
        )
    ]
    trigger_actions = [
        # The analog handler supports all six aliases on either controller.
        f"{trigger}_{value}"
        for trigger in ("LEFT_TRIGGER", "LT", "L2", "RIGHT_TRIGGER", "RT", "R2")
        for value in (0.5, 1.0, -0.5, 1.5, 0.0)
    ]

    def test_gamepad(gamepad, actions):
        """Test a gamepad with a list of actions"""
        try:
            for act in actions:
                print(f"Testing {type(gamepad).__name__}: {act}")
                parse_gamepad(act, gamepad)
                time.sleep(1)
        finally:
            # Release held buttons/axes even if a manual test is interrupted.
            gamepad.reset()
            gamepad.update()

    # Test XBOX controller
    TestGamepad = vg.VX360Gamepad()
    test_gamepad(TestGamepad, x_actions)
    test_gamepad(TestGamepad, joystick_actions)
    test_gamepad(TestGamepad, trigger_actions)

    # Test DS4 controller
    TestGamepad = vg.VDS4Gamepad()
    test_gamepad(TestGamepad, d_actions)
    test_gamepad(TestGamepad, joystick_actions)
    test_gamepad(TestGamepad, trigger_actions)
