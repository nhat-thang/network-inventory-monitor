# Network Inventory Monitor

Hệ thống kiểm kê và giám sát trạng thái mạng đa nhà cung cấp, viết bằng Python theo hướng đối tượng, dùng **Netmiko** để kết nối thiết bị qua SSH.

Đề tài số 3 – Bài tập lớn môn Lập trình hướng đối tượng, Học viện Công nghệ Bưu chính Viễn thông.

Mã nguồn trên GitHub: https://github.com/nhat-thang/network-inventory-monitor

## Bắt đầu từ đâu

| Muốn | Mở |
|---|---|
| Đọc tài liệu kiến trúc | `docs/TaiLieuKienTruc_Nhom1.docx` |
| Xem kết quả chạy thật trên lab (không cần cài gì) | `demo/README.md`, rồi mở lần lượt các thư mục `demo/00_…` đến `demo/06_…` |
| Chạy thử chương trình ngay, không cần lab | Mục [Cài đặt](#cài-đặt), rồi `python main.py --demo web` |
| Đối chiếu từng yêu cầu của đề với mã nguồn, dựng lại lab GNS3 | `lab/README.md` |
| Gặp lỗi khi chạy | Mục [Xử lý lỗi thường gặp](#xử-lý-lỗi-thường-gặp) cuối file này |

## Cấu trúc bài nộp

```
BTL_TDHM_H99_Nhom01/
├── README.md           file này
├── docs/               tài liệu kiến trúc và các sơ đồ
├── demo/               minh chứng chạy thật trên lab, chia theo kịch bản kiểm thử
│   ├── 00_moi_truong_lab/
│   ├── 01_cau_hinh_OSPF/          bước 1–3
│   ├── 02_baseline_va_tuan_thu/   bước 4–6
│   ├── 03_giao_dien_web/          bước 7
│   ├── 04_rollback/               bước 8
│   ├── 05_su_co_va_khoi_phuc/     bước 9–10
│   └── 06_du_lieu_va_log/
├── lab/                hướng dẫn xem/chạy thử, topology GNS3, bảng IP, cấu hình ban đầu router
└── source-code/        mã nguồn Python
    ├── main.py         điểm chạy (CLI)
    ├── services/       NetworkService: lớp dịch vụ dùng chung cho CLI và web
    ├── web/            giao diện web Flask (chỉ gọi NetworkService)
    ├── core/           model dữ liệu, ngoại lệ, tài khoản, kết nối đa luồng, lập lịch
    ├── devices/        NetworkDevice (lớp trừu tượng), MikroTikDevice, VyOSDevice, CiscoIOSDevice, Factory
    ├── inventory/      đọc, lọc, thêm/sửa/xóa thiết bị
    ├── collectors/     thu thập và chuẩn hóa thông tin thiết bị
    ├── monitoring/     các luật phát hiện bất thường (Strategy), kiểm tra tuân thủ
    ├── backup/         sao lưu, diff, rollback cấu hình
    ├── provisioning/   template Jinja2, dry-run, cấu hình hàng loạt
    ├── reporting/      logger, báo cáo Markdown, lịch sử thao tác
    └── tests/          pytest + output mẫu từ lab
```

## Chức năng

1. **Inventory:** đọc danh sách thiết bị từ `inventory.yaml`, lọc theo nhóm, vai trò hoặc tag.
2. **Kết nối:** SSH tới nhiều thiết bị song song; lỗi ở một thiết bị không làm dừng chương trình.
3. **Thu thập thông tin:** phiên bản OS, serial, uptime, trạng thái cổng, bảng định tuyến, OSPF neighbor, láng giềng LLDP, bảng ARP, CPU, RAM.
4. **Phát hiện bất thường:** thiết bị offline, cổng down, CPU cao, RAM cao, mất OSPF neighbor, thiết bị khởi động lại, cấu hình bị thay đổi.
   **Kiểm tra tuân thủ cấu hình:** bật SSH, tắt Telnet, bật LLDP, có banner đăng nhập, OSPF router-id đúng quy hoạch; tính tỷ lệ % cho từng thiết bị và toàn mạng.
5. **Báo cáo:** file Markdown `.md` (tổng quan, cảnh báo, bảng thiết bị, chi tiết cổng / định tuyến / OSPF / LLDP / ARP của từng thiết bị), kèm JSON và CSV; lịch sử thao tác lưu trong `output/history.jsonl`.
6. **Sao lưu và khôi phục:** lưu cấu hình kèm thời gian, sao lưu định kỳ, so sánh hai phiên bản, rollback.
7. **Cấu hình hàng loạt:** áp template Jinja2 (`ospf`, `baseline`: bật LLDP, tắt Telnet, thêm banner) cho nhiều thiết bị, có dry-run và tự rollback khi lỗi.
8. **Giao diện web (Flask):** xem tổng quan (online/offline, số bản sao lưu, tỷ lệ tuân thủ, lịch sử thao tác), chọn thiết bị để quét / sao lưu / áp cấu hình và theo dõi tiến trình từng thiết bị theo thời gian thực, xem và so sánh bản sao lưu, xem và tải báo cáo .md, xem lịch sử. Phần lõi vẫn chạy độc lập qua CLI.

## Cài đặt

Yêu cầu: Python 3.9 trở lên. Chạy với router thật cần thêm lab GNS3 dựng theo `lab/README.md`; chạy thử bằng `--demo` thì không cần.

```bash
cd source-code
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
copy .env.example .env          # rồi điền tài khoản thật vào .env (không cần nếu chỉ chạy --demo)
```

## Sử dụng

```bash
python main.py inventory list                 # xem danh sách thiết bị
python main.py inventory add SW1 --host 192.168.100.31 --device-type vyos --group edge
python main.py inventory edit SW1 --group core
python main.py inventory remove SW1
python main.py scan                           # thu thập, phát hiện bất thường, xuất output/reports/report_*.md
python main.py scan --group core              # chỉ quét nhóm "core"
python main.py backup                         # sao lưu running-config
python main.py backup --every 30 --times 4    # sao lưu định kỳ 30 phút/lần, 4 lần
python main.py diff R1                        # so sánh 2 bản sao lưu gần nhất của R1
python main.py rollback R1 <file>             # khôi phục R1 về một bản sao lưu
python main.py deploy baseline --dry-run      # xem trước template baseline (LLDP, tắt Telnet, banner)
python main.py deploy ospf --tag vyos         # áp template OSPF cho các thiết bị có tag vyos
python main.py web                            # mở giao diện web tại http://127.0.0.1:5000
```

Thêm `--demo` trước tên lệnh (ví dụ `python main.py --demo web`) để chạy với router giả lập, không cần lab; kết quả ghi vào `output_demo/`.

`deploy-ospf` vẫn dùng được và tương đương `deploy ospf`.

## Kiểm thử

```bash
cd source-code
pytest
```

82 test, không cần lab: parser được kiểm tra bằng output thật của router lưu trong `tests/samples/`; lớp dịch vụ và giao diện web được kiểm tra bằng thiết bị giả lập trả về chính các output đó (`devices/simulated.py`).

## Bảo mật

- Tài khoản thiết bị đọc từ file `.env` hoặc biến môi trường, không ghi trong mã nguồn.
- File `.env` đã nằm trong `.gitignore`; chỉ commit `.env.example`.

## Thêm hãng thiết bị mới

1. Tạo lớp con của `NetworkDevice` trong `devices/`.
2. Đăng ký lớp đó với Factory bằng `@DeviceFactory.register("<device_type>")`.
3. Nếu muốn dùng template, thêm `provisioning/templates/<template>_<device_type>.j2`.

Không cần sửa code của các lớp đã có.

## Xử lý lỗi thường gặp

**`ModuleNotFoundError: No module named 'netmiko'`** (hoặc `flask`, `yaml`, `dotenv`)
Chưa kích hoạt môi trường ảo hoặc chưa cài thư viện. Vào `source-code`, chạy `.venv\Scripts\activate` rồi `pip install -r requirements.txt`.

**PowerShell báo "running scripts is disabled on this system" khi kích hoạt `.venv`**
Chạy `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` rồi kích hoạt lại, hoặc dùng CMD thay cho PowerShell.

**`ValueError: Missing NET_USERNAME or NET_PASSWORD; copy .env.example to .env`**
Chưa có file `.env`. Chạy `copy .env.example .env` trong `source-code` và điền tài khoản SSH của router. Nếu chỉ muốn chạy thử, dùng `--demo`, không cần `.env`.

**`[LỖI] R1: DeviceTimeoutError: R1: no response from 192.168.100.11`**
Máy không tới được router. Kiểm tra lần lượt: lab GNS3 đã bật đủ 4 router; card **VMware Network Adapter VMnet3** trên máy có IP `192.168.100.1` (`ipconfig`); `ping 192.168.100.11` trả lời. Chi tiết ở `lab/README.md`. Lỗi ở một router không làm dừng các router còn lại.

**`DeviceAuthenticationError: R1: authentication failed`**
Tài khoản trong `.env` không khớp với tài khoản đã tạo trên router (xem `lab/bootstrap/`).

**`Error: Unknown device: 'R5'`**
Tên thiết bị không có trong `inventory.yaml`. Xem danh sách đúng bằng `python main.py inventory list`.

**Mở `http://127.0.0.1:5000` không lên trang**
`127.0.0.1` là chính máy đang mở trình duyệt, nên phải chạy `python main.py web` (hoặc `python main.py --demo web`) trên máy đó trước, và giữ cửa sổ lệnh đó mở trong lúc dùng web. Nếu cổng 5000 đang bị chương trình khác dùng, chạy `python main.py web --port 5001` và mở `http://127.0.0.1:5001`.
