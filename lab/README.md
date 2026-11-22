# Lab GNS3 và cách chạy thử chương trình

Thư mục này gồm hai phần: **cách xem và chạy thử bài nộp** (đọc trước), và **cách dựng lại lab GNS3** gồm 4 router.

## Xem và chạy thử bài nộp

Nhóm 1, đề tài số 3: **Hệ thống kiểm kê và giám sát trạng thái mạng**.

Có ba mức kiểm tra, từ nhanh đến đầy đủ. Hai mức đầu **không cần lab GNS3**.

| Mức | Thời gian | Cần cài | Xem được gì |
|---|---|---|---|
| A. Xem minh chứng | 5 phút | Không | Kết quả chạy thật trên lab: ảnh, log, báo cáo, bản sao lưu |
| B. Chạy thử bằng router giả lập | 10 phút | Python 3.9+ | Toàn bộ chương trình và giao diện web, chạy trên máy bất kỳ |
| C. Chạy với lab thật | 1–2 giờ dựng lab | GNS3, VMware | Như B nhưng kết nối SSH tới 4 router thật |

### 1. Bài nộp gồm những gì

```
BTL_TDHM_H99_Nhom1/
├── README.md           giới thiệu, cài đặt, danh sách lệnh
├── docs/               tài liệu kiến trúc (.docx) và các sơ đồ
├── demo/               minh chứng chạy thật trên lab (mức A)
├── source-code/        mã nguồn Python
└── lab/                README này, topology GNS3, bảng IP, cấu hình ban đầu router
```

### 2. Mức A: xem minh chứng (không cần cài gì)

Mở thư mục `demo/` (ở thư mục gốc bài nộp) và đọc `demo/README.md`. File này liệt kê từng bước đã chạy trên lab ngày 22/11/2026 và file minh chứng của từng bước: ảnh chụp CMD và giao diện web, file log, báo cáo `.md`, cấu hình trước/sau khi áp và kết quả so sánh.

Báo cáo `.md` mở được bằng Notepad. Nếu mở bằng VS Code hoặc xem trên GitHub thì bảng hiển thị đẹp hơn.

### 3. Mức B: chạy thử bằng router giả lập

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

### 4. Giao diện web hoạt động thế nào

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

### 5. Mức C: chạy với lab thật

1. Dựng lab theo phần **Dựng lab** bên dưới, hoặc import file `.gns3project` trong thư mục này.
2. Trong `source-code`, chép `.env.example` thành `.env` và điền tài khoản router.
3. Chạy các lệnh như mức B nhưng **bỏ** `--demo`, ví dụ `python main.py scan` hoặc `python main.py web`. Kết quả nằm trong `source-code/output/`.

### 6. Đối chiếu với yêu cầu của đề

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

## Lab GNS3

Lab gồm 4 router thuộc 2 nền tảng (2 MikroTik CHR, 2 VyOS), nối thành vòng để chạy OSPF. Mỗi router có thêm một cổng vào mạng quản lý `192.168.100.0/24`, qua đó chương trình Python SSH vào.

```
Mạng quản lý:
  Laptop 192.168.100.1 (VMnet3) ── Cloud (GNS3 VM, eth2) ── SW-Management
  SW-Management ── R1 ether1 / R2 ether1 / VY1 eth0 / VY2 eth0

Vòng dữ liệu (OSPF):
  R1 ether2 ─── ether2 R2
  R1 ether3 ─── eth1 VY1
  R2 ether3 ─── eth1 VY2
  VY1 eth2  ─── eth2 VY2
```

### Nội dung thư mục

| Đường dẫn | Mô tả |
|---|---|
| [ip-plan.md](ip-plan.md) | Bảng IP mạng quản lý và link dữ liệu |
| [topology.gns3](topology.gns3) | File sơ đồ GNS3 (chỉ có sơ đồ, không có ổ đĩa router) |
| [bootstrap/](bootstrap/) | Lệnh cấu hình tay ban đầu cho từng router |
| [configs/](configs/) | Cấu hình đang chạy của 4 router, xuất ngày 22/11/2026 (mật khẩu đã che) |

File image router (MikroTik CHR, ISO VyOS) không kèm theo vì quá nặng; tải theo bảng phiên bản bên dưới. File `Nhom1_HeThongKiemKeMang.gns3project` (project GNS3 đã có sẵn cấu hình 4 router) nằm ngay trong thư mục này.

### Phần mềm

| Thành phần | Phiên bản / file |
|---|---|
| VMware Workstation Pro | 17.6.4 |
| GNS3 + GNS3 VM (bản VMware) | 2.2.61 (hai bản phải cùng phiên bản) |
| MikroTik CHR | `chr-7.24.6.img` |
| VyOS | `vyos-2026.11.18-0016-rolling-generic-amd64.iso` |

### Tài khoản

Cả 4 router dùng chung user `admin` và một mật khẩu lab; mật khẩu lấy từ biến `NET_PASSWORD` trong file `.env` của chương trình, không ghi trong repo. Router VyOS còn user mặc định `vyos` (cùng mật khẩu), dùng khi đăng nhập console.

---

### Dựng lab

#### Bước 1. Chuẩn bị Windows

1. Bật ảo hóa (VT-x/AMD-V) trong BIOS.
2. Nếu máy có Docker Desktop, WSL2 hoặc Hyper-V: tắt Hyper-V khi chạy lab (CMD quyền Administrator), rồi khởi động lại máy:
   ```
   bcdedit /set hypervisorlaunchtype off
   ```
   Bật lại khi cần Docker/WSL: `bcdedit /set hypervisorlaunchtype auto` rồi khởi động lại. Nếu Windows bật *Core isolation → Memory integrity* thì cũng phải tắt.
   Lý do: khi Hyper-V bật, GNS3 VM không có KVM, router chạy rất chậm hoặc không chạy.
3. Cài VMware Workstation, rồi cài GNS3 (bỏ chọn SolarWinds khi cài).

#### Bước 2. Tạo mạng quản lý VMnet3

VMware → **Edit → Virtual Network Editor → Change Settings**:

1. Đảm bảo có **VMnet1** (Host-only, có DHCP) và **VMnet8** (NAT). GNS3 VM cần hai mạng này. Nếu thiếu, bấm **Restore Defaults** (lệnh này xóa các VMnet tự tạo khác).
2. **Add Network → VMnet3**:
   - Host-only
   - Bỏ tick *Use local DHCP service*
   - Subnet `192.168.100.0`, mask `255.255.255.0`
3. Kiểm tra bằng `ipconfig`: card **VMware Network Adapter VMnet3** phải có IP `192.168.100.1`.

Không dùng card *Microsoft KM-TEST Loopback* như cách cũ: Cloud chạy trên máy local nối sang router trong GNS3 VM qua card Loopback làm ARP và SSH từ Windows bị timeout.

#### Bước 3. Nhập và cấu hình GNS3 VM

1. VMware → **File → Open** → chọn `GNS3 VM.ova` → tên máy ảo đặt đúng là `GNS3 VM` → **Import**.
2. **Edit virtual machine settings**:
   - Memory: ít nhất 4 GB (4 router dùng khoảng 2,8 GB)
   - Processors: 2, tick **Virtualize Intel VT-x/EPT or AMD-V/RVI**
   - **Add → Network Adapter**, chọn **Custom: VMnet3**. GNS3 VM sẽ có 3 card: `eth0` (VMnet1), `eth1` (NAT), `eth2` (VMnet3).
3. GNS3 → **Edit → Preferences → GNS3 VM**: tick *Enable the GNS3 VM*, engine **VMware Workstation**, VM name **GNS3 VM**, vCPU 2, RAM 3968 MB. Bấm OK, đợi chấm xanh ở *Servers Summary*. Màn hình VM phải báo `KVM support available: True`.

#### Bước 4. Lấy project

**Cách A. Import portable project (nhanh nhất):** tạo template ở Bước 5 trước (để GNS3 có image), sau đó chọn **File → Import portable project**, chọn file `Nhom1_HeThongKiemKeMang.gns3project` trong thư mục `lab/`, chạy trên **GNS3 VM**. File đã chứa sẵn cấu hình 4 router, bỏ qua Bước 6.

**Cách B. Dựng từ đầu:** làm Bước 5, mở `topology.gns3` (*File → Open project*), rồi làm Bước 6.

#### Bước 5. Tạo template router

GNS3 → **Edit → Preferences → QEMU → Qemu VMs → New**, luôn chọn **Run this QEMU VM on the GNS3 VM**.

| Thiết lập | MikroTik | VyOS |
|---|---|---|
| Tên template | `MikroTik-CHR` | `VyOS-Router` (đúng tên này) |
| RAM | 384 MB | 1024 MB |
| Console | telnet | telnet |
| Disk (hda) | **New image → Browse** → `chr-7.24.6.img` (file đã giải nén, không phải `.zip`) | **New image → Create** → qcow2, 4096 MiB, tên `VyOS-Router-hda.qcow2` |
| Disk interface | virtio | ide |
| CD/DVD | không dùng | ISO VyOS |
| Boot priority | HDD | HDD or CD/DVD-ROM |
| Adapters | 8 | 3 |
| Name format | `ether{port1}` | `eth{0}` |
| Adapter type | virtio-net-pci | Intel Gigabit Ethernet (e1000) |

Các mục sau *Disk image* chỉnh bằng nút **Edit** sau khi tạo xong template.

Sau khi mở project, node Cloud phải chạy trên **GNS3 VM**, có interface `eth2`, nối vào cổng **e4** của `SW-Management`. Với node VY1/VY2: *Configure* → Boot priority **HDD or CD/DVD-ROM**, tab CD/DVD chọn ISO VyOS.

#### Bước 6. Cấu hình router (chỉ khi dựng từ đầu)

Bấm **Start all**, nhấp đúp từng router để mở console, rồi làm theo file tương ứng trong [bootstrap/](bootstrap/):

- `R1.rsc`, `R2.rsc`: MikroTik, đăng nhập lần đầu `admin` / mật khẩu trống, RouterOS bắt đặt mật khẩu mới.
- `VY1.txt`, `VY2.txt`: VyOS, phải chạy `install image` trước, nếu không cấu hình sẽ mất khi khởi động lại.

Lưu ý khi gõ lệnh vào console:

- Tắt bộ gõ tiếng Việt (Unikey/EVKey). Kiểu gõ Telex biến `s`, `f`, `r`, `x`, `j` thành dấu, làm sai mật khẩu và lệnh.
- Dán **từng dòng một**. Console serial của VyOS hay mất hoặc giữ lại lệnh khi dán cả khối.

#### Bước 7. Kiểm tra từ Windows

```
ping 192.168.100.11
ping 192.168.100.12
ping 192.168.100.21
ping 192.168.100.22
ssh admin@192.168.100.11
ssh admin@192.168.100.21
```

`arp -a` phải có dòng `dynamic` cho 4 IP trên. Nếu SSH báo `auth timeout`, chạy lại và nhập mật khẩu ngay khi được hỏi.

IP các link `10.0.x.x` và OSPF **không** cấu hình tay, mà do lệnh `python main.py deploy-ospf` cấu hình.

### Tắt và mở lại lab

- Tắt: **Stop all** → đóng GNS3 (GNS3 VM tự tắt) → đóng VMware.
- Mở lại: mở GNS3 → đợi GNS3 VM chấm xanh → mở project → **Start all**, đợi 1–2 phút.
- Ổ đĩa router nằm **bên trong GNS3 VM** (`/opt/gns3/projects/`). Không xóa GNS3 VM khi chưa export portable project.
- Sao lưu hoặc chia sẻ: **File → Export portable project** (phải Stop all trước), bỏ tick *Include base images*.
