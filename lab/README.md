# Lab GNS3

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

## Nội dung thư mục

| Đường dẫn | Mô tả |
|---|---|
| [ip-plan.md](ip-plan.md) | Bảng IP mạng quản lý và link dữ liệu |
| [topology.gns3](topology.gns3) | File sơ đồ GNS3 (chỉ có sơ đồ, không có ổ đĩa router) |
| [bootstrap/](bootstrap/) | Lệnh cấu hình tay ban đầu cho từng router |
| [configs/](configs/) | Cấu hình đang chạy của 4 router, xuất ngày 22/11/2026 (mật khẩu đã che) |

File image router và file portable project (`.gns3project`) không đưa vào repo vì quá nặng. File portable project được đăng ở mục **Releases** của repo.

## Phần mềm

| Thành phần | Phiên bản / file |
|---|---|
| VMware Workstation Pro | 17.6.4 |
| GNS3 + GNS3 VM (bản VMware) | 2.2.61 (hai bản phải cùng phiên bản) |
| MikroTik CHR | `chr-7.24.6.img` |
| VyOS | `vyos-2026.11.18-0016-rolling-generic-amd64.iso` |

## Tài khoản

Cả 4 router dùng chung user `admin` và một mật khẩu lab; mật khẩu lấy từ biến `NET_PASSWORD` trong file `.env` của chương trình, không ghi trong repo. Router VyOS còn user mặc định `vyos` (cùng mật khẩu), dùng khi đăng nhập console.

---

## Dựng lab

### Bước 1. Chuẩn bị Windows

1. Bật ảo hóa (VT-x/AMD-V) trong BIOS.
2. Nếu máy có Docker Desktop, WSL2 hoặc Hyper-V: tắt Hyper-V khi chạy lab (CMD quyền Administrator), rồi khởi động lại máy:
   ```
   bcdedit /set hypervisorlaunchtype off
   ```
   Bật lại khi cần Docker/WSL: `bcdedit /set hypervisorlaunchtype auto` rồi khởi động lại. Nếu Windows bật *Core isolation → Memory integrity* thì cũng phải tắt.
   Lý do: khi Hyper-V bật, GNS3 VM không có KVM, router chạy rất chậm hoặc không chạy.
3. Cài VMware Workstation, rồi cài GNS3 (bỏ chọn SolarWinds khi cài).

### Bước 2. Tạo mạng quản lý VMnet3

VMware → **Edit → Virtual Network Editor → Change Settings**:

1. Đảm bảo có **VMnet1** (Host-only, có DHCP) và **VMnet8** (NAT). GNS3 VM cần hai mạng này. Nếu thiếu, bấm **Restore Defaults** (lệnh này xóa các VMnet tự tạo khác).
2. **Add Network → VMnet3**:
   - Host-only
   - Bỏ tick *Use local DHCP service*
   - Subnet `192.168.100.0`, mask `255.255.255.0`
3. Kiểm tra bằng `ipconfig`: card **VMware Network Adapter VMnet3** phải có IP `192.168.100.1`.

Không dùng card *Microsoft KM-TEST Loopback* như cách cũ: Cloud chạy trên máy local nối sang router trong GNS3 VM qua card Loopback làm ARP và SSH từ Windows bị timeout.

### Bước 3. Nhập và cấu hình GNS3 VM

1. VMware → **File → Open** → chọn `GNS3 VM.ova` → tên máy ảo đặt đúng là `GNS3 VM` → **Import**.
2. **Edit virtual machine settings**:
   - Memory: ít nhất 4 GB (4 router dùng khoảng 2,8 GB)
   - Processors: 2, tick **Virtualize Intel VT-x/EPT or AMD-V/RVI**
   - **Add → Network Adapter**, chọn **Custom: VMnet3**. GNS3 VM sẽ có 3 card: `eth0` (VMnet1), `eth1` (NAT), `eth2` (VMnet3).
3. GNS3 → **Edit → Preferences → GNS3 VM**: tick *Enable the GNS3 VM*, engine **VMware Workstation**, VM name **GNS3 VM**, vCPU 2, RAM 3968 MB. Bấm OK, đợi chấm xanh ở *Servers Summary*. Màn hình VM phải báo `KVM support available: True`.

### Bước 4. Lấy project

**Cách A — Import portable project (nhanh nhất):** tạo template ở Bước 5 trước (để GNS3 có image), sau đó tải `Nhom1_HeThongKiemKeMang.gns3project` ở mục Releases, chọn **File → Import portable project**, chạy trên **GNS3 VM**. File đã chứa sẵn cấu hình 4 router, bỏ qua Bước 6.

**Cách B — Dựng từ đầu:** làm Bước 5, mở `topology.gns3` (*File → Open project*), rồi làm Bước 6.

### Bước 5. Tạo template router

GNS3 → **Edit → Preferences → QEMU → Qemu VMs → New**, luôn chọn **Run this QEMU VM on the GNS3 VM**.

| Thiết lập | MikroTik | VyOS |
|---|---|---|
| Tên template | `MikroTik-CHR` | `VyOS-Router` (đúng tên này) |
| RAM | 384 MB | 1024 MB |
| Console | telnet | telnet |
| Disk (hda) | **New image → Browse** → `chr-7.24.6.img` (file đã giải nén, không phải `.zip`) | **New image → Create** → qcow2, 4096 MiB, tên `VyOS-Router-hda.qcow2` |
| Disk interface | virtio | ide |
| CD/DVD | — | ISO VyOS |
| Boot priority | HDD | HDD or CD/DVD-ROM |
| Adapters | 8 | 3 |
| Name format | `ether{port1}` | `eth{0}` |
| Adapter type | virtio-net-pci | Intel Gigabit Ethernet (e1000) |

Các mục sau *Disk image* chỉnh bằng nút **Edit** sau khi tạo xong template.

Sau khi mở project, node Cloud phải chạy trên **GNS3 VM**, có interface `eth2`, nối vào cổng **e4** của `SW-Management`. Với node VY1/VY2: *Configure* → Boot priority **HDD or CD/DVD-ROM**, tab CD/DVD chọn ISO VyOS.

### Bước 6. Cấu hình router (chỉ khi dựng từ đầu)

Bấm **Start all**, nhấp đúp từng router để mở console, rồi làm theo file tương ứng trong [bootstrap/](bootstrap/):

- `R1.rsc`, `R2.rsc`: MikroTik, đăng nhập lần đầu `admin` / mật khẩu trống, RouterOS bắt đặt mật khẩu mới.
- `VY1.txt`, `VY2.txt`: VyOS, phải chạy `install image` trước, nếu không cấu hình sẽ mất khi khởi động lại.

Lưu ý khi gõ lệnh vào console:

- Tắt bộ gõ tiếng Việt (Unikey/EVKey). Kiểu gõ Telex biến `s`, `f`, `r`, `x`, `j` thành dấu, làm sai mật khẩu và lệnh.
- Dán **từng dòng một**. Console serial của VyOS hay mất hoặc giữ lại lệnh khi dán cả khối.

### Bước 7. Kiểm tra từ Windows

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

## Tắt và mở lại lab

- Tắt: **Stop all** → đóng GNS3 (GNS3 VM tự tắt) → đóng VMware.
- Mở lại: mở GNS3 → đợi GNS3 VM chấm xanh → mở project → **Start all**, đợi 1–2 phút.
- Ổ đĩa router nằm **bên trong GNS3 VM** (`/opt/gns3/projects/`). Không xóa GNS3 VM khi chưa export portable project.
- Sao lưu hoặc chia sẻ: **File → Export portable project** (phải Stop all trước), bỏ tick *Include base images*.
