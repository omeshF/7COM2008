import time, threading
from pymodbus.server.sync import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

temp = 20
direction = 1
store = ModbusServerContext(slaves=ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, [temp]*100)), single=True)

def update_temp():
    global temp, direction
    while True:
        time.sleep(2)
        temp += direction
        if temp >= 31: direction = -1
        elif temp <= 20: direction = 1
        store[0].setValues(3, 0, [temp])

threading.Thread(target=update_temp, daemon=True).start()
StartTcpServer(store, address=('10.0.0.100', 502))
