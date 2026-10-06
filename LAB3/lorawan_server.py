import socket, base64, json, time

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('10.0.0.100', 1700)) # Standard LoRaWAN UDP forwarder port
print("LoRaWAN Network Server listening on UDP 1700...")

while True:
    data, addr = sock.recvfrom(1024)
    try:
        # Decode Base64 to simulate LoRaWAN PHY payload decryption (AES-128)
        decoded = base64.b64decode(data).decode('utf-8')
        payload = json.loads(decoded)
        
        dev_eui = payload.get('devEUI')
        temp = payload.get('temp')
        
        # Simulate MIC (Message Integrity Code) check for security
        if payload.get('mic') == "VALID":
            status = "*** WARNING: ABOVE 30C ***" if temp > 30 else "OK"
            print(f"{time.strftime('%H:%M:%S')} [LoRaWAN] Device {dev_eui} -> {temp}C ({status})")
        else:
            print(f"{time.strftime('%H:%M:%S')} [LoRaWAN] Dropped packet from {addr}: Invalid MIC")
    except Exception as e:
        print(f"Error decoding LoRaWAN packet: {e}")
