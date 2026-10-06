import socket, base64, json, time

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SERVER_IP = '10.0.0.100'
SERVER_PORT = 1700
DEV_EUI = "A84041C910000001"

print("LoRaWAN End Device transmitting...")
print(f"DevEUI: {DEV_EUI}")
print(f"Target Network Server: {SERVER_IP}:{SERVER_PORT}")
print("")

temp = 20
direction = 1

for i in range(60):
    payload = {
        "devEUI": DEV_EUI,
        "temp": temp,
        "mic": "VALID" # Simulated Message Integrity Code
    }
    
    # LoRaWAN encrypts the payload (simulated via Base64)
    json_str = json.dumps(payload)
    encoded_payload = base64.b64encode(json_str.encode('utf-8'))
    
    sock.sendto(encoded_payload, (SERVER_IP, SERVER_PORT))
    
    status = "*** WARNING: ABOVE 30C ***" if temp > 30 else "OK"
    print(f"{time.strftime('%H:%M:%S')} Sent LoRaWAN Packet: {temp}C - {status}")
    
    time.sleep(2)
    
    if direction == 1:
        temp += 1
        if temp >= 31: direction = -1
    else:
        temp -= 1
        if temp <= 20: direction = 1
