# Minh chứng chạy trên lab, ngày 22/11/2026

Các kết quả dưới đây lấy từ lab GNS3 gồm 2 router MikroTik CHR 7.24.6 và 2 router VyOS rolling (xem `lab/README.md`). Chương trình chạy trên Windows, kết nối tới router qua mạng quản lý `192.168.100.0/24`.

## Cách xem thư mục này

Mỗi thư mục là một phần của kịch bản kiểm thử (Bảng 7.1 trong tài liệu). Ảnh trong từng thư mục được đánh số theo đúng thứ tự thực hiện, chỉ cần mở lần lượt từ `01_` trở đi.

| Thư mục | Bước (Bảng 7.1) | Nội dung |
|---|---|---|
| `00_moi_truong_lab/` | | Topology trong GNS3, card mạng VMnet3 trên Windows |
| `01_cau_hinh_OSPF/` | 1–3 | Đọc inventory, sao lưu, áp OSPF bằng chương trình |
| `02_baseline_va_tuan_thu/` | 4–6 | Template baseline, kiểm tra tuân thủ, sao lưu định kỳ |
| `03_giao_dien_web/` | 7 | Các trang của giao diện web |
| `04_rollback/` | 8 | Rollback VY1 trên web, áp lại baseline |
| `05_su_co_va_khoi_phuc/` | 9–10 | Tạo sự cố trong GNS3, phát hiện và khôi phục |
| `06_du_lieu_va_log/` | | Log cả ngày, lịch sử thao tác, dữ liệu lần quét cuối |

Trong mỗi thư mục, `bao_cao/` chứa báo cáo `.md` do chương trình sinh ra (mở được bằng Notepad), `sao_luu/` chứa bản sao lưu cấu hình trước/sau và kết quả so sánh. Mã băm mật khẩu trong các bản sao lưu đã được thay bằng `***`.

Lab được chạy hai đợt:

- **Buổi sáng (08:37–08:44):** cấu hình OSPF bằng chương trình và tạo sự cố lần đầu. Lúc này chương trình còn ở phiên bản cũ (báo cáo HTML, chưa có giao diện web).
- **Buổi chiều (16:03–16:40):** chạy lại với phiên bản cuối: template `baseline`, kiểm tra tuân thủ, giao diện web, rollback, sự cố và khôi phục. Phần lớn ảnh chụp và báo cáo trong thư mục này là của đợt chiều.

## 1. Cấu hình OSPF bằng chương trình (buổi sáng) — `01_cau_hinh_OSPF/`

| Thời gian | Lệnh | Kết quả |
|---|---|---|
| | `inventory list` | Đọc đúng 4 thiết bị (`01_inventory_list.png`) |
| 08:37:59 | `backup` | Sao lưu cấu hình ban đầu của 4 router |
| 08:38:12–08:38:53 | `deploy-ospf` | Mỗi router được sao lưu ngay trước khi áp; MikroTik áp 6 dòng, VyOS áp 5 dòng |
| 08:39:12–08:39:51 | `deploy-ospf` lần 2 | Không lỗi, không tạo bản ghi trùng (template idempotent) |

Cấu hình trước và sau khi áp OSPF của R1, VY1 cùng kết quả so sánh nằm trong `sao_luu/`.

## 2. Template baseline và kiểm tra tuân thủ — `02_baseline_va_tuan_thu/`

Template `baseline` bật LLDP, tắt Telnet (RouterOS) và thêm banner đăng nhập.

| Thời gian | Lệnh | Kết quả |
|---|---|---|
| 16:03:33 | `scan` | Tỷ lệ tuân thủ **60%**: R1, R2 chưa tắt Telnet; VY1, VY2 chưa bật LLDP; cả 4 chưa có banner (`bao_cao/report_20261122-160333.md`) |
| 16:03:56 | `deploy baseline` | Áp thành công 4/4 router |
| 16:04:04 | `scan` | Tỷ lệ tuân thủ **100%**; mỗi router có cảnh báo `config_changed` (`bao_cao/report_20261122-160404.md`) |

Đợt 16:03 được chạy tay và không chụp màn hình. Ảnh `01_inventory_list.png` (thư mục 1) và các ảnh `01_` đến `04_` trong thư mục này là của lần chạy lại cùng kịch bản lúc 16:22–16:24, khi baseline đã có sẵn: lệnh áp vẫn chạy thành công nhưng không làm thay đổi cấu hình, nên hai lần quét đều 100%.

| Ảnh | Nội dung |
|---|---|
| `01_scan_truoc_baseline.png` | Lệnh `scan` |
| `02_deploy_baseline_dry_run.png` | Xem trước lệnh của từng hãng, chưa áp |
| `03_deploy_baseline.png` | Áp baseline, sao lưu ngay trước khi áp |
| `04_scan_sau_baseline.png` | Lệnh `scan` lần 2 |
| `05_backup_dinh_ky.png` | `backup --every 0.5 --times 2`: sao lưu 2 lần cách nhau 30 giây rồi tự dừng |

Cấu hình trước/sau baseline và kết quả so sánh: `sao_luu/`.

## 3. Giao diện web — `03_giao_dien_web/`

| Ảnh | Nội dung |
|---|---|
| `01_thiet_bi.png` | Danh sách thiết bị, bộ lọc nhóm/tag, các nút thực thi tác vụ |
| `02_tac_vu_xong.png` | Trang tiến trình của một lần quét 4 router, mỗi router một dòng, kèm thời điểm hoàn thành |
| `03_tong_quan.png` | Tổng quan: 4/4 trực tuyến, số bản sao lưu, tỷ lệ tuân thủ 100%, lịch sử thao tác |
| `04_chi_tiet_VY1.png`, `05_chi_tiet_R1.png` | Chi tiết router: cổng, OSPF neighbor, láng giềng LLDP, bảng định tuyến, ARP, bảng tuân thủ, danh sách bản sao lưu |
| `06_so_sanh_cau_hinh_VY1.png` | So sánh bản sao lưu VY1 lúc 16:03:38 (trước baseline) và 16:25:20: đúng hai dòng LLDP và banner được thêm. Mã băm mật khẩu trong ảnh đã được làm mờ |
| `07_sao_luu.png` | Danh sách bản sao lưu của 4 router |
| `08_bao_cao.png`, `09_danh_sach_bao_cao.png` | Xem báo cáo `.md` trên trình duyệt và danh sách báo cáo |
| `10_lich_su.png` | Lịch sử thao tác từ cả CLI và web |
| `11_thiet_bi_cuoi.png` | Danh sách thiết bị sau lần quét cuối |

Ảnh web được chụp tự động bằng Chrome chạy ở chế độ không giao diện. Một lần quét 4 router chỉ mất khoảng 7 giây, nên không chụp kịp lúc tác vụ đang chạy; các ảnh trang tiến trình đều là trạng thái đã hoàn tất.

## 4. Rollback trên web — `04_rollback/`

| Thời gian | Thao tác | Kết quả |
|---|---|---|
| 16:39:11 | Rollback VY1 về bản `VY1_20261122-160338.cfg` (trước baseline) | Chương trình tính và gửi 2 lệnh `delete` rồi `commit` (`01_rollback_VY1.png`) |
| 16:39:19 | Quét VY1 | Tuân thủ còn **80%**: tiêu chí banner không đạt (`02_VY1_sau_rollback.png`, `bao_cao/report_20261122-163919.md`) |
| 16:39:42 | `deploy baseline --devices VY1` | Áp lại baseline (`03_ap_lai_baseline_VY1.png`) |
| 16:40:32 | Quét 4 router | VY1 trở lại 100%; cảnh báo `config_changed` cho VY1 (`bao_cao/report_20261122-164032.md`) |

Sau rollback, VyOS giữ lại nút `set service lldp` (chỉ mất dòng `interface all`), nên tiêu chí LLDP vẫn được tính là đạt. So sánh cấu hình trước và sau rollback: `sao_luu/diff_VY1_rollback.txt`.

`06_du_lieu_va_log/history.jsonl` còn ghi hai lần rollback trước đó (16:25:07 và 16:34:19). Lần đầu chọn nhầm bản sao lưu đã có baseline nên không có gì thay đổi. Lần thứ hai chạy trên một tiến trình web cũ còn mở từ trước, chưa có bản sửa lỗi hiển thị. Ảnh trong thư mục này là của lần thứ ba.

## 5. Sự cố và khôi phục — `05_su_co_va_khoi_phuc/`

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

Ảnh `01_` đến `05_`: lệnh `scan` trên CMD, trang tiến trình, tổng quan, chi tiết R1, báo cáo. Báo cáo: `bao_cao/report_20261122-162649.md`.

Sau đó bật lại link và VY2. Lần quét lúc 16:29:11 cho kết quả 4/4 trực tuyến, không còn cảnh báo nghiêm trọng. Chương trình phát hiện VY2 vừa khởi động lại (`reboot`, uptime 100 giây) và cấu hình R2 thay đổi (`config_changed`). Ảnh: `06_khoi_phuc_tong_quan.png`. Báo cáo: `bao_cao/report_20261122-162911.md`.

Buổi sáng (08:43) cũng tạo đúng sự cố này và ra cùng 7 cảnh báo.

## 6. Dữ liệu và log — `06_du_lieu_va_log/`

| File | Nội dung |
|---|---|
| `automation.log` | Log của chương trình trong cả ngày (cả hai đợt), mỗi dòng gồm thời gian, người thực hiện (`user=`), luồng và nội dung |
| `history.jsonl` | Lịch sử thao tác của đợt chiều, ghi thêm nguồn (`cli` hay `web`) |
| `facts.json`, `facts.csv`, `last_scan.json` | Dữ liệu của lần quét cuối |
| `raw_vy1_lldp.txt` | Output gốc của lệnh LLDP trên VY1, dùng để viết test |
