import json
from qiskit_ibm_runtime import QiskitRuntimeService

data = json.load(open('../apikey.json'))
s = QiskitRuntimeService(channel='ibm_quantum_platform', token=data['apikey'])
backends = s.backends(simulator=False, operational=True)
print("Available backends:")
for b in backends:
    print(" -", b.name)
