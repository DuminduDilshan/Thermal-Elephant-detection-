from machine import UART, Pin, I2C
import time

# ── UART for SIM800L — TX:GP0, RX:GP1 ────────────
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1), timeout=1000)

# ── I2C for MLX90614 — SDA:GP4, SCL:GP5 ──────────
sda = Pin(4, pull=Pin.PULL_UP)
scl = Pin(5, pull=Pin.PULL_UP)
i2c = I2C(0, sda=sda, scl=scl, freq=50000)

MLX_ADDR = 0x5A
MLX_OBJ  = 0x07

# ── PIR — GP15 ────────────────────────────────────
pir = Pin(15, Pin.IN)

# ── Config ────────────────────────────────────────
ALERT_NUMBER = "+94706935333"
TEMP_MIN     = 33.0   # °C min for warm body
TEMP_MAX     = 40.0   # °C max (above = fire/vehicle)
COOLDOWN_MS  = 60000  # 1 min between SMS alerts

# ─────────────────────────────────────────────────
# MLX90614
# ─────────────────────────────────────────────────
def read_temp():
    try:
        data = i2c.readfrom_mem(MLX_ADDR, MLX_OBJ, 3)
        raw  = (data[1] << 8) | data[0]
        return (raw * 0.02) - 273.15
    except:
        return None

# ─────────────────────────────────────────────────
# SIM800L
# ─────────────────────────────────────────────────
def send_at_command(command, timeout=3000):
    while uart.any():
        uart.read()
    uart.write(command + '\r\n')
    response = b""
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < timeout:
        if uart.any():
            chunk = uart.read(uart.any())
            if chunk:
                response += chunk
            time.sleep_ms(100)
            if not uart.any():
                break
        time.sleep_ms(10)
    return response.decode('utf-8', 'ignore').strip()

def check_gsm():
    print("Initializing GSM...")
    uart.write('ATE0\r\n')
    time.sleep(1)
    while uart.any():
        uart.read()

    r = send_at_command('AT')
    if 'OK' not in r:
        print("  SIM800L not responding ✗")
        return False
    print("  SIM800L OK ✓")

    r = send_at_command('AT+CPIN?')
    if '+CPIN: READY' not in r:
        print("  SIM not ready ✗")
        return False
    print("  SIM ready ✓")

    r = send_at_command('AT+CREG?')
    if '+CREG: 0,1' not in r and '+CREG: 0,5' not in r:
        print("  Network not registered ✗")
        return False
    print("  Network registered ✓")

    r = send_at_command('AT+CSQ')
    try:
        val = int(r.split('+CSQ:')[-1].strip().split(',')[0])
        if val == 99:
            print("  No signal ✗")
        else:
            dbm = -113 + (val * 2)
            print("  Signal: " + str(val) + "/31 (" + str(dbm) + "dBm) ✓")
    except:
        pass

    return True

def send_sms(number, message):
    print("Sending SMS to " + number + "...")

    r = send_at_command('AT+CMGF=1')
    if 'OK' not in r:
        print("  Text mode failed ✗")
        return False

    send_at_command('AT+CSCS="GSM"')

    while uart.any():
        uart.read()

    uart.write('AT+CMGS="' + number + '"\r\n')

    prompt = b""
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 5000:
        if uart.any():
            prompt += uart.read(uart.any())
            if b'>' in prompt:
                break
        time.sleep_ms(50)

    if b'>' not in prompt:
        print("  No prompt ✗")
        return False

    uart.write(message + '\x1A')

    response = b""
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 10000:
        if uart.any():
            response += uart.read(uart.any())
            decoded = response.decode('utf-8', 'ignore')
            if 'OK' in decoded or 'ERROR' in decoded:
                break
        time.sleep_ms(100)

    decoded = response.decode('utf-8', 'ignore').strip()
    if '+CMGS' in decoded:
        print("  SMS sent ✓")
        return True
    else:
        print("  SMS failed ✗ " + decoded)
        return False

# ─────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────
print("=" * 40)
print("  ELEPHANT DETECTOR — STARTUP")
print("=" * 40)

# I2C scan
print("\n[1] I2C scan...")
devices = i2c.scan()
if len(devices) > 10:
    print("  Bus floating! Add 4.7k pull-ups ✗")
elif len(devices) == 0:
    print("  No I2C devices found ✗")
else:
    for d in devices:
        print("  Found: 0x{:02X}".format(d))
    print("  MLX90614 OK ✓" if MLX_ADDR in devices else "  MLX90614 NOT found ✗")

# MLX90614 test
print("\n[2] MLX90614 test...")
for i in range(3):
    t = read_temp()
    if t is not None:
        print("  Reading {}: {:.2f}C ✓".format(i+1, t))
    else:
        print("  Reading {}: FAILED ✗".format(i+1))
    time.sleep_ms(500)

# PIR test
print("\n[3] PIR test...")
print("  PIR: " + ("MOTION" if pir.value() else "clear"))

# GSM init
print("\n[4] GSM init...")
gsm_ok = check_gsm()

# Startup SMS
if gsm_ok:
    print("\n[5] Sending startup SMS...")
    send_sms(ALERT_NUMBER, "ELEPHANT DETECTOR: System online. All sensors OK.")
else:
    print("\n[5] GSM not ready — skipping startup SMS")

# ─────────────────────────────────────────────────
# DETECTION LOOP
# ─────────────────────────────────────────────────
print("\n" + "=" * 40)
print("  DETECTION MODE ACTIVE")
print("=" * 40)
print("{:>10}  |  {:8}  |  {}".format("Temp", "PIR", "Status"))
print("-" * 45)

last_alert = 0

while True:
    temp   = read_temp()
    motion = pir.value()
    now    = time.ticks_ms()

    temp_str   = "{:.2f}C".format(temp) if temp is not None else "ERROR "
    motion_str = "MOTION!" if motion else "clear  "
    status     = "Standby"

    if motion and temp is not None:
        if TEMP_MIN <= temp <= TEMP_MAX:
            status = "Warm body detected"
            if time.ticks_diff(now, last_alert) > COOLDOWN_MS:
                status = "ELEPHANT ALERT — SMS sending"
                print("{:>10}  |  {:8}  |  {}".format(
                    temp_str, motion_str, status))
                send_sms(ALERT_NUMBER,
                    "ELEPHANT ALERT!\nTemp: {:.1f}C\nLocation: Forest fence node 1".format(temp))
                last_alert = now
        elif temp > TEMP_MAX:
            status = "Too hot (fire/vehicle?)"
        else:
            status = "Too cold (small animal)"
    elif motion:
        status = "Motion — sensor error"

    print("{:>10}  |  {:8}  |  {}".format(temp_str, motion_str, status))
    time.sleep_ms(500)
