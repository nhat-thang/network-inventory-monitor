# Output mẫu từ lab

Lưu output thật của các lệnh `show` vào đây để viết và kiểm thử các hàm `parse_*` mà không cần bật lab.

```
samples/
├── cisco_ios/
│   ├── show_version.txt
│   ├── show_ip_interface_brief.txt
│   ├── show_ip_ospf_neighbor.txt
│   ├── show_ip_arp.txt
│   └── show_processes_cpu.txt
└── vyos/
    ├── show_version.txt
    ├── show_interfaces.txt
    ├── show_ip_ospf_neighbor.txt
    ├── show_arp.txt
    └── show_system_cpu.txt
```

Nên lưu output ở hai trạng thái: khi OSPF chạy bình thường, và khi một link bị tắt. Như vậy có sẵn dữ liệu để kiểm thử các luật phát hiện bất thường.
