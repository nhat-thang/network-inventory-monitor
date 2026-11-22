# Network Inventory Monitor

Hệ thống kiểm kê và giám sát trạng thái mạng đa nhà cung cấp, viết bằng Python theo hướng đối tượng, dùng **Netmiko** để kết nối thiết bị qua SSH.

Đề tài số 3 – Bài tập lớn môn Lập trình hướng đối tượng, Học viện Công nghệ Bưu chính Viễn thông.

## Chức năng

1. **Inventory:** đọc danh sách thiết bị từ `inventory.yaml`, lọc theo nhóm, vai trò hoặc tag.
2. **Kết nối:** SSH tới nhiều thiết bị song song; lỗi ở một thiết bị không làm dừng chương trình.
3. **Thu thập thông tin:** phiên bản OS, serial, uptime, trạng thái cổng, bảng định tuyến, OSPF neighbor, láng giềng LLDP, bảng ARP, CPU, RAM.
4. **Phát hiện bất thường:** thiết bị offline, cổng down, CPU cao, RAM cao, mất OSPF neighbor, thiết bị khởi động lại, cấu hình bị thay đổi.
5. **Báo cáo:** file Excel (.xlsx, 8 sheet: tổng quan, thiết bị, cảnh báo, cổng, định tuyến, OSPF, LLDP, ARP), kèm JSON và CSV; lịch sử thao tác lưu trong `output/history.jsonl`.
6. **Sao lưu và khôi phục:** lưu cấu hình kèm thời gian, sao lưu định kỳ, so sánh hai phiên bản, rollback.
7. **Cấu hình hàng loạt:** áp template Jinja2 (`ospf`, `baseline`: bật LLDP và banner) cho nhiều thiết bị, có dry-run và tự rollback khi lỗi.
8. **Giao diện web (Flask):** xem tổng quan, chọn thiết bị để quét / sao lưu / áp cấu hình và theo dõi tiến trình từng thiết bị theo thời gian thực, xem và so sánh bản sao lưu, tải báo cáo Excel, xem lịch sử. Phần lõi vẫn chạy độc lập qua CLI.

## Cấu trúc repo

```
network-inventory-monitor/
├── source-code/        # mã nguồn chương trình
│   ├── main.py         # điểm chạy (CLI)
│   ├── services/       # NetworkService: lớp dịch vụ dùng chung cho CLI và web
│   ├── web/            # giao diện web Flask (chỉ gọi NetworkService)
│   ├── core/           # model dữ liệu, ngoại lệ, tài khoản, kết nối đa luồng, lập lịch
│   ├── devices/        # NetworkDevice (lớp trừu tượng), MikroTikDevice, VyOSDevice, CiscoIOSDevice, Factory
│   ├── inventory/      # đọc, lọc, thêm/sửa/xóa thiết bị
│   ├── collectors/     # thu thập và chuẩn hóa thông tin thiết bị
│   ├── monitoring/     # các luật phát hiện bất thường (Strategy)
│   ├── backup/         # sao lưu, diff, rollback cấu hình
│   ├── provisioning/   # template Jinja2, dry-run, cấu hình hàng loạt
│   ├── reporting/      # logger, báo cáo Excel, lịch sử thao tác
│   └── tests/          # pytest + output mẫu từ lab
├── lab/                # môi trường GNS3: topology, bảng IP, cấu hình ban đầu
├── docs/               # tài liệu kiến trúc
└── demo/               # video, ảnh chụp, log minh chứng
```

## Cài đặt

Yêu cầu: Python 3.9 trở lên và lab GNS3 đã dựng theo `lab/README.md`. Kết quả chạy thật trên lab xem trong `demo/`.

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
python main.py inventory add SW1 --host 192.168.100.31 --device-type vyos --group edge
python main.py inventory edit SW1 --group core
python main.py inventory remove SW1
python main.py scan                           # thu thập, phát hiện bất thường, xuất output/reports/report_*.xlsx
python main.py scan --group core              # chỉ quét nhóm "core"
python main.py backup                         # sao lưu running-config
python main.py backup --every 30 --times 4    # sao lưu định kỳ 30 phút/lần, 4 lần
python main.py diff R1                        # so sánh 2 bản sao lưu gần nhất của R1
python main.py rollback R1 <file>             # khôi phục R1 về một bản sao lưu
python main.py deploy baseline --dry-run      # xem trước template baseline (LLDP + banner)
python main.py deploy ospf --tag vyos         # áp template OSPF cho các thiết bị có tag vyos
python main.py web                            # mở giao diện web tại http://127.0.0.1:5000
```

`deploy-ospf` vẫn dùng được và tương đương `deploy ospf`.

## Kiểm thử

```bash
cd source-code
pytest
```

76 test, không cần lab: parser được kiểm tra bằng output thật của router lưu trong `tests/samples/`; lớp dịch vụ và giao diện web được kiểm tra bằng thiết bị giả lập trả về chính các output đó (`tests/fakes.py`).

## Bảo mật

- Tài khoản thiết bị đọc từ file `.env` hoặc biến môi trường, không ghi trong mã nguồn.
- File `.env` đã nằm trong `.gitignore`; chỉ commit `.env.example`.

## Thêm hãng thiết bị mới

1. Tạo lớp con của `NetworkDevice` trong `devices/`.
2. Đăng ký lớp đó với Factory bằng `@DeviceFactory.register("<device_type>")`.
3. Nếu muốn dùng template, thêm `provisioning/templates/<template>_<device_type>.j2`.

Không cần sửa code của các lớp đã có.
