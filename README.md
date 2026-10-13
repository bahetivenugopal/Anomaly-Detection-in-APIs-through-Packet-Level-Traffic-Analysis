# Anomaly Detection in APIs — Packet-Level Traffic Analysis
**VIT TYA13 | Academic Year 2025-26**
Guide: Prof. (Dr.) Sheetal Phatangare

---

## Quick Start

```
Terminal 1:  cd fake_apis   && python auth_service.py
Terminal 2:  cd fake_apis   && python payments_service.py
Terminal 3:  cd fake_apis   && python inventory_service.py
Terminal 4:  cd proxy       && python interceptor.py
Terminal 5:  python client/traffic_generator.py --rps 8
Terminal 6:  cd dashboard   && .\node_modules\.bin\react-scripts start
Browser:     http://localhost:3000
```

## First Time Setup

```
pip install -r requirements.txt
cd dashboard && npm install
```

## Fault Injection (Terminal)

```
python client/traffic_generator.py --fault latency_drift --api payments
python client/traffic_generator.py --fault error_rate --api auth
python client/traffic_generator.py --fault reset --api all
```

## Bonus Sniffer (Run as Administrator)

```
python bonus/live_sniffer.py --list
python bonus/live_sniffer.py --iface "Wi-Fi" --filter "tcp or udp"
```

## Full Documentation
See Project_Reference_Guide_TYA13.docx for complete file reference and parameter guide.
