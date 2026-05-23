def send_sms(phone_number, message):
    print("\nSetting SMS text mode...")
    r = send_at_command('AT+CMGF=1')
    if 'OK' not in r:
        print("Failed to set SMS mode")
        return

    print("Sending to number...")
    # Flush first
    while uart.any():
        uart.read()

    uart.write('AT+CMGS="' + phone_number + '"\r\n')

    # Wait for '>' prompt
    prompt = b""
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 5000:
        if uart.any():
            prompt += uart.read(uart.any())
            if b'>' in prompt:
                break
        time.sleep_ms(50)

    if b'>' not in prompt:
        print("ERROR: No '>' prompt received")
        return

    print("Sending message body...")
    uart.write(message + '\x1A')  # Ctrl+Z

    # Wait longer for +CMGS confirmation (network takes time)
    response = b""
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 10000:  # 10 sec timeout
        if uart.any():
            response += uart.read(uart.any())
            # Stop once we see OK or ERROR
            decoded = response.decode('utf-8', 'ignore')
            if 'OK' in decoded or 'ERROR' in decoded:
                break
        time.sleep_ms(100)

    decoded = response.decode('utf-8', 'ignore').strip()
    print("RAW:", repr(decoded))

    if '+CMGS' in decoded:
        print("✓ SMS sent successfully!")
    elif 'ERROR' in decoded:
        print("✗ SMS failed:", decoded)
    else:
        print("? No confirmation — SMS may still have sent. Check your phone.")