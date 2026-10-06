#!/usr/bin/python3
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, Controller
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def iot_topology():
    net = Mininet(switch=OVSKernelSwitch, controller=Controller)

    info("*** Adding Controller ***\n")
    c0 = net.addController('c0')

    info("*** Adding Switch ***\n")
    s1 = net.addSwitch('s1')

    info("*** Adding IoT Nodes ***\n")
    server = net.addHost('server', ip='10.0.0.100/24', mac='00:00:00:00:00:10')
    
    # 5 Sensors (MQTT, HTTP, Modbus, CoAP, LoRaWAN)
    mqtt_s = net.addHost('mqtt', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    http_s = net.addHost('http', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
    modbus_s = net.addHost('modbus', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
    coap_s = net.addHost('coap', ip='10.0.0.4/24', mac='00:00:00:00:00:04')
    lora_s = net.addHost('lora', ip='10.0.0.5/24', mac='00:00:00:00:00:05')

    info("*** Creating Links ***\n")
    for node in [server, mqtt_s, http_s, modbus_s, coap_s, lora_s]:
        net.addLink(node, s1)

    info("*** Starting Network ***\n")
    net.start()

    info("*** Starting Background MQTT Broker on Server ***\n")
    server.cmd('mosquitto -d')

    info("*** IoT Network Ready! ***\n")
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    iot_topology()
