# Network Inventory Monitor

Hệ thống kiểm kê và giám sát trạng thái mạng đa nhà cung cấp, viết bằng Python theo hướng đối tượng, dùng **Netmiko** để kết nối thiết bị qua SSH.

Đề tài số 3 – Bài tập lớn môn Lập trình hướng đối tượng, Học viện Công nghệ Bưu chính Viễn thông.

## Chức năng

1. **Inventory:** đọc danh sách thiết bị từ `inventory.yaml`, lọc theo nhóm, vai trò hoặc tag.
2. **Kết nối:** SSH tới nhiều thiết bị song song; lỗi ở một thiết bị không làm dừng chương trình.
3. **Thu thập thông tin:** phiên bản OS, serial, uptime, trạng thái cổng, OSPF neighbor, bảng ARP, CPU.
4. **Phát hiện bất thường:** thiết bị offline, cổng down, CPU cao, mất OSPF neighbor.
5. **Báo cáo:** xuất báo cáo HTML, JSON và CSV.
6. **Sao lưu và khôi phục:** lưu cấu hình kèm thời gian, so sánh hai phiên bản, rollback.
7. **Cấu hình hàng loạt:** áp cấu hình OSPF từ template Jinja2, có chế độ dry-run và tự rollback khi lỗi.

## Cấu trúc repo

```
network-inventory-monitor/
├── source-code/        # mã nguồn chương trình
│   ├── main.py         # điểm chạy (CLI)
│   ├── core/           # model dữ liệu, ngoại lệ, tài khoản, kết nối đa luồng
│   ├── devices/        # NetworkDevice (lớp trừu tượng), CiscoIOSDevice, VyOSDevice, Factory
│   ├── inventory/      # đọc, lọc, thêm/sửa/xóa thiết bị
│   ├── collectors/     # thu thập và chuẩn hóa thông tin thiết bị
│   ├── monitoring/     # các luật phát hiện bất thường (Strategy)
│   ├── backup/         # sao lưu, diff, rollback cấu hình
│   ├── provisioning/   # template Jinja2, dry-run, cấu hình hàng loạt
│   ├── reporting/      # logger, báo cáo HTML/JSON/CSV
│   └── tests/          # pytest + output mẫu từ lab
├── lab/                # môi trường GNS3: topology, bảng IP, cấu hình ban đầu
├── docs/               # tài liệu kiến trúc
└── demo/               # video, ảnh chụp, log minh chứng
```

## Cài đặt

Yêu cầu: Python 3.9 trở lên và lab GNS3 đã dựng theo `lab/README.md`.

```bash
cd source-code
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
copy .env.example .env          # rồi điền tài khoản thật vào .env
```

## Sử dụng

```bash
python main.py inventory list                 # xem danh sách thiết bị
python main.py scan                           # thu thập, phát hiện bất thường, xuất báo cáo
python main.py scan --group core              # chỉ quét nhóm "core"
python main.py backup                         # sao lưu running-config
python main.py diff R1                        # so sánh 2 bản sao lưu gần nhất của R1
python main.py rollback R1 <file>             # khôi phục R1 về một bản sao lưu
python main.py deploy-ospf --dry-run          # xem trước cấu hình OSPF
python main.py deploy-ospf                    # áp cấu hình OSPF thật
```

## Kiểm thử

```bash
cd source-code
pytest
```

## Bảo mật

- Tài khoản thiết bị đọc từ file `.env` hoặc biến môi trường, không ghi trong mã nguồn.
- File `.env` đã nằm trong `.gitignore`; chỉ commit `.env.example`.

## Thêm hãng thiết bị mới

1. Tạo lớp con của `NetworkDevice` trong `devices/`.
2. Đăng ký lớp đó với Factory bằng `@DeviceFactory.register("<device_type>")`.

Không cần sửa code của các lớp đã có.
