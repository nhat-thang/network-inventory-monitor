# Lab GNS3

Lab gồm 4 router thuộc 2 nền tảng (2 Cisco IOSv, 2 VyOS), nối thành vòng để chạy OSPF. Mỗi router có thêm một cổng vào mạng quản lý `192.168.100.0/24`, qua đó chương trình Python SSH vào.

- Bảng IP: [ip-plan.md](ip-plan.md)
- Cấu hình tay ban đầu của từng router: [bootstrap/](bootstrap/)

## Phần mềm

| Thành phần | Phiên bản |
|---|---|
| GNS3 + GNS3 VM | _điền phiên bản đã dùng_ |
| Cisco IOSv | _điền tên file image_ |
| VyOS | _điền phiên bản_ |

File image router không được đưa vào repo.

## Dựng lại lab

1. Cài GNS3 và GNS3 VM cùng phiên bản; bật ảo hóa (VT-x/AMD-V) trong BIOS.
2. Cài appliance VyOS (miễn phí, từ GNS3 server) và Cisco IOSv.
3. Windows: thêm card **Microsoft KM-TEST Loopback Adapter**, đặt IP `192.168.100.1/24`.
4. Import `topology.gns3project` (*File → Import portable project*), hoặc tự kéo thả theo `ip-plan.md`. Gắn node Cloud vào card Loopback.
5. Nếu dựng mới: dán nội dung `bootstrap/<router>.txt` vào console của từng router.
6. Kiểm tra: `ssh admin@192.168.100.11` (và `.12`, `.21`, `.22`).

IP các link `10.0.x.x` và OSPF **không** cấu hình tay, mà do lệnh `python main.py deploy-ospf` cấu hình.
