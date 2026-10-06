import socket, time, threading
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('10.0.0.100', 5683))
temp = 20
direction = 1
def update_temp():
    global temp, direction
    while True:
        time.sleep(2)
        temp += direction
        if temp >= 31: direction = -1
        elif temp <= 20: direction = 1
threading.Thread(target=update_temp, daemon=True).start()
print("CoAP (UDP) Server listening on port 5683...")
while True:
    data, addr = sock.recvfrom(1024)
    sock.sendto(f"{temp}".encode(), addr)
