# Output mẫu từ lab

Output thật của các lệnh `show` lấy từ lab GNS3 ngày 22/11/2026, dùng để viết và kiểm thử các hàm `parse_*` mà không cần bật lab (`tests/test_parsers.py`).

```
samples/
├── mikrotik/   # R1, RouterOS 7.24.6
│   ├── system_resource.txt      /system resource print
│   ├── system_identity.txt      /system identity print
│   ├── system_license.txt       /system license print
│   ├── interface_terse.txt      /interface print terse
│   ├── ip_address_terse.txt     /ip address print terse
│   ├── ip_arp_terse.txt         /ip arp print terse
│   ├── ospf_neighbor_terse.txt  /routing ospf neighbor print terse (trống: chưa chạy OSPF)
│   └── export.txt               /export
└── vyos/       # VY1, VyOS 2026.11.18 rolling
    ├── show_version.txt
    ├── show_host_name.txt
    ├── show_system_uptime.txt
    ├── show_interfaces.txt
    ├── show_arp.txt
    ├── show_ip_ospf_neighbor.txt (OSPF chưa bật)
    └── show_configuration_commands.txt
```

Output được lấy bằng script `collect_samples.py` (Netmiko), đã bỏ ký tự điều khiển terminal và che mã băm mật khẩu. Sau khi chạy `deploy-ospf`, nên lấy thêm output OSPF ở hai trạng thái: chạy bình thường và khi một link bị tắt.
