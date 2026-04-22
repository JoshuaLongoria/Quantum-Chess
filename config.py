"""
config.py — IBM Quantum credentials loader

Reads the API key from ../apikey.json (one level above this file).
That file is intentionally kept OUTSIDE the Quantum-Chess folder and is
listed in .gitignore so it never gets committed or shared accidentally.

Available backends on this account:
  ibm_fez        (default)
  ibm_marrakesh
  ibm_kingston

Override from the command line without editing this file:
  python main.py --mode ibm --backend ibm_marrakesh
"""
import json
import os

_key_file = os.path.join(os.path.dirname(__file__), '..', 'apikey.json')

try:
    with open(_key_file) as _f:
        _data = json.load(_f)
    IBM_QUANTUM_TOKEN = _data.get("apikey", "")
except (FileNotFoundError, KeyError, json.JSONDecodeError):
    IBM_QUANTUM_TOKEN = ""

IBM_BACKEND = "ibm_fez"
