# Minh chứng chạy trên lab — 22/11/2026

Kết quả chạy chương trình trên lab GNS3 thật (2 MikroTik CHR 7.24.6 + 2 VyOS rolling, xem `lab/README.md`), từ Windows qua mạng quản lý `192.168.100.0/24`.

## Kịch bản đã chạy

| Bước | Lệnh | Kết quả |
|---|---|---|
| 1 | `python main.py inventory list` | Đọc 4 thiết bị từ `inventory.yaml` |
| 2 | `python main.py scan` | 4/4 online, thu thập version, serial/ID, uptime, CPU, cổng, IP, ARP |
| 3 | `python main.py backup` | Sao lưu cấu hình 4 router vào `output/backups/` |
| 4 | `python main.py deploy-ospf --dry-run` | Xem trước cấu hình OSPF (RouterOS và VyOS) |
| 5 | `python main.py deploy-ospf` | Sao lưu rồi áp OSPF lên 4 router; chạy lại lần 2 không tạo bản trùng |
| 6 | `python main.py scan` | Mỗi router có 2 OSPF neighbor `Full`; 4 cảnh báo *thông tin* "cấu hình đã thay đổi" |
| 7 | Trong GNS3: *Suspend* link R1–R2, *Stop* VY2, đợi 1 phút | Tạo sự cố |
| 8 | `python main.py scan` | **7 cảnh báo nghiêm trọng**, đúng với sự cố đã tạo (bảng dưới) |
| 9 | `python main.py diff R1` | Phần OSPF được thêm giữa hai bản sao lưu |

Cảnh báo ở bước 8:

| Thiết bị | Luật | Nội dung |
|---|---|---|
| VY2 | `device_offline` | Không SSH được (timeout) |
| R1, R2 | `interface_down` | ether2 vừa chuyển từ up sang down |
| R1, R2 | `ospf_neighbor_lost` | Mất neighbor của nhau (2.2.2.2 / 1.1.1.1) |
| R2, VY1 | `ospf_neighbor_lost` | Mất neighbor 4.4.4.4 (VY2) |

## Nội dung thư mục

| File | Mô tả |
|---|---|
| [report/report_su_co.html](report/report_su_co.html) | Dashboard HTML do lệnh `scan` sinh ra ở bước 8 (tải về rồi mở bằng trình duyệt) |
| [screenshots/dashboard_su_co.png](screenshots/dashboard_su_co.png) | Ảnh chụp dashboard trên |
| [screenshots/cmd_scan_su_co.png](screenshots/cmd_scan_su_co.png) | Màn hình CMD khi chạy `scan` ở bước 8 |
| [report/facts.json](report/facts.json), [report/facts.csv](report/facts.csv) | Dữ liệu thu thập ở bước 8 |
| [logs/automation.log](logs/automation.log) | Log toàn bộ các bước, mỗi dòng có thời gian, người thực hiện (`user=`) và luồng |
| [backups/](backups/) | Cấu hình R1 và VY1 trước/sau khi áp OSPF (mã băm mật khẩu đã che) và kết quả so sánh `diff_R1.txt`, `diff_VY1.txt` |

Video demo (nếu có) để trên Drive/YouTube và dán link vào đây, không commit file video.
