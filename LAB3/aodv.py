import socket, time, sys, threading, uuid

my_ip = sys.argv[1]
target = sys.argv[2] if len(sys.argv) > 2 else None
all_nodes = ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4']

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((my_ip, 5001))

route_found = False
seen_rreqs = set()

def listen():
    global route_found
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode()
            if msg.startswith("RREQ"):
                _, req_id, req_src, req_dst = msg.split("-")
                if req_id in seen_rreqs: continue
                seen_rreqs.add(req_id)
                
                if req_dst == my_ip:
                    print(f"[{my_ip}] I am the target! Sending RREP to {req_src}")
                    sock.sendto(f"RREP-{req_id}-{my_ip}-{req_src}".encode(), (addr[0], 5001))
                    route_found = True
                else:
                    print(f"[{my_ip}] Forwarding RREQ for {req_dst}")
                    time.sleep(0.2)
                    # Flood to everyone except the sender
                    for node_ip in all_nodes:
                        if node_ip != my_ip and node_ip != addr[0]:
                            sock.sendto(msg.encode(), (node_ip, 5001))
            elif msg.startswith("RREP"):
                _, req_id, rep_src, rep_dst = msg.split("-")
                if rep_dst == my_ip:
                    print(f"[{my_ip}] Route established to {rep_src}!")
                    route_found = True
                else:
                    print(f"[{my_ip}] Forwarding RREP back to {rep_dst}")
                    # Forward back towards source
                    for node_ip in all_nodes:
                        if node_ip != my_ip and node_ip != addr[0]:
                            sock.sendto(msg.encode(), (node_ip, 5001))
        except Exception as e:
            pass

threading.Thread(target=listen, daemon=True).start()

if target:
    req_id = str(uuid.uuid4())[:8]
    print(f"[{my_ip}] Need route to {target}. Flooding RREQ...")
    for node_ip in all_nodes:
        if node_ip != my_ip:
            sock.sendto(f"RREQ-{req_id}-{my_ip}-{target}".encode(), (node_ip, 5001))
    
    while not route_found:
        time.sleep(0.5)
    print(f"[{my_ip}] Routing complete. Ready to Ping {target}!")
else:
    print(f"[{my_ip}] AODV Daemon listening for RREQs...")
    while True: time.sleep(1)
