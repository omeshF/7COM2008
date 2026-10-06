import time
from pymodbus.client.sync import ModbusTcpClient

client = ModbusTcpClient('10.0.0.100')
client.connect()
print("Polling Modbus Register every 2 seconds...")
for i in range(60):
    result = client.read_holding_registers(0, 1, unit=1)
    if result and hasattr(result, 'registers'):
        t = result.registers[0]
        status = "*** WARNING: ABOVE 30C ***" if t > 30 else "OK"
        print(f"{time.strftime('%H:%M:%S')} Modbus Register 0: {t}C - {status}")
    time.sleep(2)
client.close()
