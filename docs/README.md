# Tài liệu kiến trúc

- [TaiLieuKienTruc_Nhom1.docx](TaiLieuKienTruc_Nhom1.docx): tài liệu 9 chương (39 trang) theo mục 6.2 của đề.
  Trước khi nộp cần điền: giảng viên, họ tên và MSSV các thành viên (trang bìa) và bảng phân công, tỷ lệ đóng góp (Bảng 1.1, mục 1.5).
- `diagrams/`: các sơ đồ dùng trong tài liệu, kèm file nguồn để vẽ lại
  - `architecture` (Graphviz): kiến trúc 4 lớp
  - `class_devices`, `class_monitoring`, `class_services` (Graphviz): biểu đồ lớp
  - `seq_scan`, `seq_deploy` (Mermaid): biểu đồ tuần tự
  - `topology` (Graphviz, `dot -Kneato`): sơ đồ lab

Vẽ lại một sơ đồ Graphviz: `dot -Tpng -Gdpi=170 diagrams/architecture.dot -o diagrams/architecture.png`.
