import socket, time
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(2)
print("Polling CoAP (UDP) Server every 2 seconds...")
for i in range(60):
    sock.sendto(b"GET", ('10.0.0.100', 5683))
    data, addr = sock.recvfrom(1024)
    t = int(data.decode())
    status = "*** WARNING: ABOVE 30C ***" if t > 30 else "OK"
    print(f"{time.strftime('%H:%M:%S')} CoAP UDP returned: {t}C - {status}")
    time.sleep(2)
