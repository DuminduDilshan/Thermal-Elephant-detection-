import machine
import utime

# ── MLX90614 ──────────────────────────────────────
i2c = machine.I2C(0, sda=machine.Pin(4), scl=machine.Pin(5), freq=100000)
MLX_ADDR = 0x5A
MLX_OBJ  = 0x07

def read_temp():
    try:
        data = i2c.readfrom_mem(MLX_ADDR, MLX_OBJ, 3)
        raw  = (data[1] << 8) | data[0]
        return (raw * 0.02) - 273.15
    except:
        return None

# ── PIR ───────────────────────────────────────────
pir = machine.Pin(15, machine.Pin.IN)

# ── Scan I2C bus first ────────────────────────────
print("Scanning I2C...")
devices = i2c.scan()
if devices:
    for d in devices:
        print(f"  Found: 0x{d:02X}")
    if 0x5A in devices:
        print("  MLX90614 OK ✓")
    else:
        print("  MLX90614 NOT found ✗ — check wiring")
else:
    print("  No I2C devices found ✗")

print("\nStarting test loop...\n")

# ── Test loop ─────────────────────────────────────
while True:
    temp    = read_temp()
    motion  = pir.value()

    if temp is not None:
        print(f"Temp: {temp:6.2f}°C  |  PIR: {'MOTION !' if motion else 'clear  '}")
    else:
        print("MLX90614 read error — check connections")

    utime.sleep_ms(500)