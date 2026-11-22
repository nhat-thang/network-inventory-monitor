# Bảng IP

## Mạng quản lý — 192.168.100.0/24 (cấu hình tay)

| Thiết bị | Nền tảng | Cổng | IP |
|---|---|---|---|
| Laptop | Windows (VMware Network Adapter VMnet3) | — | 192.168.100.1 |
| R1 | MikroTik CHR 7.24.6 | ether1 | 192.168.100.11 |
| R2 | MikroTik CHR 7.24.6 | ether1 | 192.168.100.12 |
| VY1 | VyOS 2026.11.18 rolling | eth0 | 192.168.100.21 |
| VY2 | VyOS 2026.11.18 rolling | eth0 | 192.168.100.22 |

Đường đi: Laptop (VMnet3) → card mạng thứ 3 của GNS3 VM (`eth2`) → node Cloud → `SW-Management` (cổng e4) → cổng quản lý của từng router (SW e0–e3).

## Link dữ liệu — OSPF area 0 (chương trình tự cấu hình)

| Link | Subnet | Đầu A | Đầu B |
|---|---|---|---|
| R1 – R2 | 10.0.12.0/30 | R1 ether2 · .1 | R2 ether2 · .2 |
| R1 – VY1 | 10.0.13.0/30 | R1 ether3 · .1 | VY1 eth1 · .2 |
| R2 – VY2 | 10.0.24.0/30 | R2 ether3 · .1 | VY2 eth1 · .2 |
| VY1 – VY2 | 10.0.34.0/30 | VY1 eth2 · .1 | VY2 eth2 · .2 |

## Router ID

| Router | Router ID |
|---|---|
| R1 | 1.1.1.1 |
| R2 | 2.2.2.2 |
| VY1 | 3.3.3.3 |
| VY2 | 4.4.4.4 |
