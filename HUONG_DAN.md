# Hướng dẫn xem và chạy thử bài nộp

Nhóm 1, đề tài số 3: **Hệ thống kiểm kê và giám sát trạng thái mạng**.

Có ba mức kiểm tra, từ nhanh đến đầy đủ. Hai mức đầu **không cần lab GNS3**.

| Mức | Thời gian | Cần cài | Xem được gì |
|---|---|---|---|
| A. Xem minh chứng | 5 phút | Không | Kết quả chạy thật trên lab: ảnh, log, báo cáo, bản sao lưu |
| B. Chạy thử bằng router giả lập | 10 phút | Python 3.9+ | Toàn bộ chương trình và giao diện web, chạy trên máy bất kỳ |
| C. Chạy với lab thật | 1–2 giờ dựng lab | GNS3, VMware | Như B nhưng kết nối SSH tới 4 router thật |

## 1. Bài nộp gồm những gì

```
BTL_TDHM_<MaLop>_Nhom1/
├── HUONG_DAN.md        ← file này
├── README.md           giới thiệu, cài đặt, danh sách lệnh
├── docs/               tài liệu kiến trúc (.docx) và các sơ đồ
├── demo/               minh chứng chạy thật trên lab (mức A)
├── source-code/        mã nguồn Python
└── lab/                topology GNS3, bảng IP, cấu hình ban đầu router (mức C)
```

## 2. Mức A: xem minh chứng (không cần cài gì)

Mở thư mục `demo/` và đọc `demo/README.md`. File này liệt kê từng bước đã chạy trên lab ngày 22/11/2026 và file minh chứng của từng bước: ảnh chụp CMD và giao diện web, file log, báo cáo `.md`, cấu hình trước/sau khi áp và kết quả so sánh.

Báo cáo `.md` mở được bằng Notepad. Nếu mở bằng VS Code hoặc xem trên GitHub thì bảng hiển thị đẹp hơn.

## 3. Mức B: chạy thử bằng router giả lập

Chế độ `--demo` thay 4 router thật bằng 4 router giả lập. Router giả lập trả lời bằng **đúng output thật đã lưu từ lab** (trong `source-code/tests/samples/`). Cấu hình áp lên router giả lập được ghi lại, nên sau khi áp, lần quét tiếp theo sẽ thấy cấu hình mới. Chế độ này không mở kết nối SSH nào, và mọi kết quả được ghi vào `source-code/output_demo/`, tách riêng khỏi kết quả thật.

```
cd source-code
pip install -r requirements.txt
pytest                              # 81 test, chạy khoảng 1 giây
python main.py --demo web           # rồi mở http://127.0.0.1:5000
```

Gợi ý thao tác trên web theo thứ tự:

1. **Thiết bị** → để nguyên 4 máy được chọn → bấm **Quét**. Trang tiến trình hiện từng router chuyển sang "XONG" ngay khi router đó chạy xong.
2. **Tổng quan**: số máy online/offline, số bản sao lưu, tỷ lệ tuân thủ cấu hình (khoảng 40% ở lần đầu), cảnh báo và lịch sử thao tác.
3. Bấm vào **VY1**: cổng, OSPF neighbor, LLDP, bảng định tuyến, ARP, và bảng tuân thủ cho biết tiêu chí nào chưa đạt.
4. **Thiết bị** → chọn template `baseline`, **bỏ** dấu tích "dry-run" → **Áp cấu hình**. Làm tương tự với template `ospf`.
5. **Quét** lại → tỷ lệ tuân thủ lên 100%, và mỗi router có cảnh báo `config_changed` vì cấu hình đã đổi.
6. **Sao lưu**: xem, tải về, chọn 2 bản rồi bấm **So sánh**. **Báo cáo**: xem và tải file `.md`. **Lịch sử**: mọi thao tác kèm thời gian, người thực hiện và nguồn (CLI hay web).

Các lệnh dòng lệnh cũng chạy được với `--demo`, ví dụ `python main.py --demo scan` hoặc `python main.py --demo deploy baseline --dry-run`.

## 4. Giao diện web hoạt động thế nào

Chương trình có **một phần lõi** và **hai cách dùng** phần lõi đó: dòng lệnh (`main.py`) và web (`web/`). Cả hai chỉ gọi lớp `NetworkService`; web không tự kết nối router và không chứa logic nghiệp vụ.

```
 Trình duyệt                      CMD
     │ HTTP                        │
 web/app.py (Flask)            main.py (argparse)       ← lớp trình diễn
     └──────────────┬──────────────┘
          services/NetworkService                        ← lớp nghiệp vụ
   inventory · monitoring · backup · provisioning · reporting
                    │
   ConnectionManager (đa luồng) → NetworkDevice          ← lớp kết nối thiết bị
   MikroTikDevice / VyOSDevice / CiscoIOSDevice → SSH (Netmiko)
                    │
   inventory.yaml, .env, output/ (snapshot, sao lưu,     ← lớp dữ liệu
   báo cáo .md, history.jsonl, log)
```

Khi bấm **Quét** trên web:

1. Trình duyệt gửi danh sách router đã chọn tới `/tasks`.
2. Flask khởi chạy tác vụ trong một luồng nền (`web/tasks.py`), rồi chuyển trình duyệt sang trang tiến trình.
3. Luồng nền gọi `NetworkService.scan()`. `ConnectionManager` mở SSH song song tới các router; xong router nào thì báo ngay router đó.
4. Trang tiến trình nhận các thông báo này qua Server-Sent Events (`/tasks/<id>/events`), nên bảng tự cập nhật mà không phải tải lại trang.
5. Khi xong, kết quả được ghi vào `output/`: snapshot cho lần so sánh sau, báo cáo `.md`, một dòng lịch sử. Các trang Tổng quan, Thiết bị, Báo cáo đọc lại từ đó.

Sao lưu và áp cấu hình chạy theo cùng cách này. Vì vậy, mọi việc làm được trên web cũng làm được bằng một lệnh CLI tương ứng (xem `README.md`).

## 5. Mức C: chạy với lab thật

1. Dựng lab theo `lab/README.md`, hoặc import file `.gns3project` trong `lab/`.
2. Trong `source-code`, chép `.env.example` thành `.env` và điền tài khoản router.
3. Chạy các lệnh như mức B nhưng **bỏ** `--demo`, ví dụ `python main.py scan` hoặc `python main.py web`. Kết quả nằm trong `source-code/output/`.

## 6. Đối chiếu với yêu cầu của đề

| Yêu cầu | Thực hiện ở | Lệnh / trang web |
|---|---|---|
| 4.3.1 Inventory: đọc, thêm/sửa/xóa, lọc | `inventory/inventory.py`, `inventory.yaml` | `inventory list/add/edit/remove`, bộ lọc `--group --role --tag`; trang Thiết bị |
| 4.3.2 Kết nối SSH, xử lý lỗi, đa luồng | `devices/base.py`, `core/connection_manager.py`, `core/exceptions.py` | mọi lệnh; router mất kết nối hiện "MẤT KẾT NỐI" |
| 4.3.3 Thu thập và chuẩn hóa thông tin | `devices/mikrotik.py`, `vyos.py`, `cisco_ios.py`, `core/models.py` | `scan`; trang chi tiết thiết bị, `facts.json`, `facts.csv` |
| 4.3.4 Sao lưu theo lịch / theo yêu cầu, diff, rollback | `backup/backup_manager.py`, `core/scheduler.py` | `backup`, `backup --every`, `diff`, `rollback`; trang Sao lưu |
| 4.3.5 Cấu hình hàng loạt từ template, dry-run, tự rollback | `provisioning/`, các template `*.j2` | `deploy ospf`, `deploy baseline`, `--dry-run` |
| 4.3.7 Log và báo cáo | `reporting/logger.py`, `markdown_report.py`, `history.py` | `output/logs/automation.log`, `output/reports/*.md`; trang Báo cáo, Lịch sử |
| 4.3.8 Xử lý lỗi, bảo mật tài khoản | `core/exceptions.py`, `core/credentials.py`, `.env` | `.env` nằm trong `.gitignore` |
| Đề tài 3: phát hiện bất thường, dashboard cảnh báo | `monitoring/rules.py`, `monitoring/compliance.py` | trang Tổng quan |
| 4.2 Thiết kế hướng đối tượng | `devices/` (trừu tượng, kế thừa, đa hình), `core/credentials.py` (đóng gói) | Chương 4 tài liệu |
| 5.1 Giao diện người dùng (điểm cộng) | `web/` | `python main.py web` |
| 6.2 Tài liệu kiến trúc | `docs/TaiLieuKienTruc_Nhom1.docx` | |
