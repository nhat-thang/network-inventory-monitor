# Tài liệu kiến trúc

- [TaiLieuKienTruc_Nhom1.docx](TaiLieuKienTruc_Nhom1.docx): tài liệu 9 chương (30 trang) theo mục 6.2 của đề.
  Trước khi nộp cần điền: tên khoa, giảng viên, mã lớp, họ tên và MSSV các thành viên (trang bìa) và bảng phân công (Phụ lục C).
- `diagrams/`: các sơ đồ dùng trong tài liệu, kèm file nguồn để vẽ lại
  - `architecture` (Graphviz): kiến trúc phân tầng
  - `class_devices`, `class_monitoring` (Graphviz): biểu đồ lớp
  - `seq_scan`, `seq_deploy` (Mermaid): biểu đồ tuần tự
  - `topology` (Graphviz, `dot -Kneato`): sơ đồ lab

Vẽ lại một sơ đồ Graphviz: `dot -Tpng -Gdpi=170 diagrams/architecture.dot -o diagrams/architecture.png`.
