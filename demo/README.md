# Minh chứng chạy trên lab, ngày 22/11/2026

Các kết quả dưới đây lấy từ lab GNS3 gồm 2 router MikroTik CHR 7.24.6 và 2 router VyOS rolling (xem `lab/README.md`). Chương trình chạy trên Windows, kết nối tới router qua mạng quản lý `192.168.100.0/24`.

Lab được chạy hai đợt:

- **Buổi sáng (08:37–08:44):** cấu hình OSPF bằng chương trình và tạo sự cố lần đầu. Lúc này chương trình còn ở phiên bản cũ (báo cáo HTML, chưa có giao diện web).
- **Buổi chiều (16:03–16:40):** chạy lại với phiên bản cuối: template `baseline`, kiểm tra tuân thủ, giao diện web, rollback, sự cố và khôi phục. Phần lớn ảnh chụp và báo cáo trong thư mục này là của đợt chiều.

File `logs/automation.log` ghi đủ cả hai đợt, mỗi dòng gồm thời gian, người thực hiện (`user=`), luồng và nội dung. File `data/history.jsonl` là lịch sử thao tác của đợt chiều, ghi thêm nguồn (`cli` hay `web`).

## 1. Cấu hình OSPF bằng chương trình (buổi sáng)

| Thời gian | Lệnh | Kết quả |
|---|---|---|
| 08:37:59 | `backup` | Sao lưu cấu hình ban đầu của 4 router |
| 08:38:12–08:38:53 | `deploy-ospf` | Mỗi router được sao lưu ngay trước khi áp; MikroTik áp 6 dòng, VyOS áp 5 dòng |
| 08:39:12–08:39:51 | `deploy-ospf` lần 2 | Không lỗi, không tạo bản ghi trùng (template idempotent) |

Cấu hình trước và sau khi áp OSPF của R1, VY1 cùng kết quả so sánh nằm trong `backups/1_ospf/`.

## 2. Template baseline và kiểm tra tuân thủ

Template `baseline` bật LLDP, tắt Telnet (RouterOS) và thêm banner đăng nhập.

| Thời gian | Lệnh | Kết quả |
|---|---|---|
| 16:03:33 | `scan` | Tỷ lệ tuân thủ **60%**: R1, R2 chưa tắt Telnet; VY1, VY2 chưa bật LLDP; cả 4 chưa có banner (`reports/report_20261122-160333.md`) |
| 16:03:56 | `deploy baseline` | Áp thành công 4/4 router |
| 16:04:04 | `scan` | Tỷ lệ tuân thủ **100%**; mỗi router có cảnh báo `config_changed` (`reports/report_20261122-160404.md`) |

Đợt 16:03 được chạy tay và không chụp màn hình. Ảnh CMD trong `screenshots/cmd/` (`cmd_01` đến `cmd_05`) là của lần chạy lại cùng kịch bản lúc 16:22–16:24, khi baseline đã có sẵn: lệnh áp vẫn chạy thành công nhưng không làm thay đổi cấu hình, nên hai lần quét đều 100%. `cmd_06_backup_dinh_ky.png` là lệnh `backup --every 0.5 --times 2`, chạy sao lưu 2 lần cách nhau 30 giây rồi tự dừng.

Cấu hình trước/sau baseline và kết quả so sánh: `backups/2_baseline/`.

## 3. Giao diện web

| Ảnh (`screenshots/web/`) | Nội dung |
|---|---|
| `web_01_thiet_bi.png` | Danh sách thiết bị, bộ lọc nhóm/tag, các nút thực thi tác vụ |
| `web_03_tac_vu_xong.png` | Trang tiến trình của một lần quét 4 router, mỗi router một dòng, kèm thời điểm hoàn thành |
| `web_04_tong_quan.png` | Tổng quan: 4/4 trực tuyến, số bản sao lưu, tỷ lệ tuân thủ 100%, lịch sử thao tác |
| `web_05_chi_tiet_VY1.png`, `web_06_chi_tiet_R1.png` | Chi tiết router: cổng, OSPF neighbor, láng giềng LLDP, bảng định tuyến, ARP, bảng tuân thủ, danh sách bản sao lưu |
| `web_07_so_sanh_cau_hinh_VY1.png` | So sánh bản sao lưu VY1 lúc 16:03:38 (trước baseline) và 16:25:20: đúng hai dòng LLDP và banner được thêm. Mã băm mật khẩu trong ảnh đã được làm mờ |
| `web_08_sao_luu.png` | Danh sách bản sao lưu của 4 router |
| `web_09_bao_cao.png`, `web_10_danh_sach_bao_cao.png` | Xem báo cáo `.md` trên trình duyệt và danh sách báo cáo |
| `web_18_lich_su.png` | Lịch sử thao tác từ cả CLI và web |
| `web_19_thiet_bi_cuoi.png` | Danh sách thiết bị sau lần quét cuối |

Ảnh web được chụp tự động bằng Chrome chạy ở chế độ không giao diện. Một lần quét 4 router chỉ mất khoảng 7 giây, nên không chụp kịp lúc tác vụ đang chạy; các ảnh trang tiến trình đều là trạng thái đã hoàn tất.

## 4. Rollback trên web

| Thời gian | Thao tác | Kết quả |
|---|---|---|
| 16:39:11 | Rollback VY1 về bản `VY1_20261122-160338.cfg` (trước baseline) | Chương trình tính và gửi 2 lệnh `delete` rồi `commit` (`web_11_rollback_VY1.png`) |
| 16:39:19 | Quét VY1 | Tuân thủ còn **80%**: tiêu chí banner không đạt (`web_12_VY1_sau_rollback.png`, `reports/report_20261122-163919.md`) |
| 16:39:42 | `deploy baseline --devices VY1` | Áp lại baseline (`cmd_07_ap_lai_baseline_VY1.png`) |
| 16:40:32 | Quét 4 router | VY1 trở lại 100%; cảnh báo `config_changed` cho VY1 (`reports/report_20261122-164032.md`) |

Sau rollback, VyOS giữ lại nút `set service lldp` (chỉ mất dòng `interface all`), nên tiêu chí LLDP vẫn được tính là đạt. So sánh cấu hình trước và sau rollback: `backups/3_rollback/diff_VY1_rollback.txt`.

`history.jsonl` còn ghi hai lần rollback trước đó (16:25:07 và 16:34:19). Lần đầu chọn nhầm bản sao lưu đã có baseline nên không có gì thay đổi. Lần thứ hai chạy trên một tiến trình web cũ còn mở từ trước, chưa có bản sửa lỗi hiển thị. Ảnh trong thư mục này là của lần thứ ba.

## 5. Sự cố và khôi phục

Trong GNS3 (điều khiển qua API của GNS3): tạm dừng (suspend) link R1–R2 và tắt VY2, đợi 60 giây để OSPF hết thời gian chờ láng giềng (dead interval 40 giây).

Lần quét lúc 16:26:49 cho kết quả 3/4 trực tuyến và **7 cảnh báo nghiêm trọng**, đều khớp với sự cố đã tạo, không có cảnh báo sai:

| Thiết bị | Luật | Nội dung |
|---|---|---|
| VY2 | `device_offline` | `DeviceTimeoutError`: không phản hồi từ 192.168.100.22 |
| R1 | `interface_down` | ether2 chuyển từ up sang down |
| R2 | `interface_down` | ether2 chuyển từ up sang down |
| R1 | `ospf_neighbor_lost` | Mất neighbor 2.2.2.2 (R2) |
| R2 | `ospf_neighbor_lost` | Mất neighbor 1.1.1.1 (R1) |
| R2 | `ospf_neighbor_lost` | Mất neighbor 4.4.4.4 (VY2) |
| VY1 | `ospf_neighbor_lost` | Mất neighbor 4.4.4.4 (VY2) |

Ảnh: `web_13_su_co_tac_vu.png`, `web_14_su_co_tong_quan.png`, `web_15_su_co_chi_tiet_R1.png`, `web_16_su_co_bao_cao.png`, `cmd_08_scan_su_co.png`. Báo cáo: `reports/report_20261122-162649.md`.

Sau đó bật lại link và VY2. Lần quét lúc 16:29:11 cho kết quả 4/4 trực tuyến, không còn cảnh báo nghiêm trọng. Chương trình phát hiện VY2 vừa khởi động lại (`reboot`, uptime 100 giây) và cấu hình R2 thay đổi (`config_changed`). Ảnh: `web_17_khoi_phuc_tong_quan.png`. Báo cáo: `reports/report_20261122-162911.md`.

Buổi sáng (08:43) cũng tạo đúng sự cố này và ra cùng 7 cảnh báo.

## Nội dung thư mục

| Đường dẫn | Nội dung |
|---|---|
| `screenshots/lab/` | Topology trong GNS3, card mạng VMnet3 trên Windows |
| `screenshots/cmd/` | Màn hình CMD khi chạy các lệnh |
| `screenshots/web/` | Giao diện web |
| `reports/` | Báo cáo `.md` do chương trình sinh ra ở các bước chính |
| `data/` | `facts.json`, `facts.csv`, `last_scan.json` của lần quét cuối; `history.jsonl`; `raw_vy1_lldp.txt` là output gốc của lệnh LLDP trên VY1, dùng để viết test |
| `logs/automation.log` | Log của chương trình trong cả ngày |
| `backups/` | Bản sao lưu cấu hình và kết quả so sánh, chia theo 3 giai đoạn: OSPF, baseline, rollback. Mã băm mật khẩu đã thay bằng `***` |
