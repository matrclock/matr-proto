import displayio
displayio.release_displays()

try:
    import cyw43  # Also tests for Raspberry Pi Pico W
    cyw43.set_power_management(cyw43.PM_DISABLED)
except ImportError:
    cyw43 = None
print(hex(cyw43.get_power_management())) # Will show the HEX value.