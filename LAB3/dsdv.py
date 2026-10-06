import socket, time, sys, threading

my_ip = sys.argv[1]
all_nodes = ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4']

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((my_ip, 5000))

table = {my_ip: 0} 

def listen():
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            remote_table = eval(data.decode())
            updated = False
            for ip, seq in remote_table.items():
                if ip not in table or seq > table[ip]:
                    table[ip] = seq
                    updated = True
            if updated:
                print(f"[{my_ip}] Updated Routing Table: {table}")
        except Exception as e:
            pass

threading.Thread(target=listen, daemon=True).start()

print(f"[{my_ip}] DSDV Started. Flooding table to neighbors...")
while True:
    time.sleep(3)
    table[my_ip] += 1
    # Flood to all other nodes
    for node_ip in all_nodes:
        if node_ip != my_ip:
            sock.sendto(str(table).encode(), (node_ip, 5000))
    print(f"[{my_ip}] Flooding table: {table}")
