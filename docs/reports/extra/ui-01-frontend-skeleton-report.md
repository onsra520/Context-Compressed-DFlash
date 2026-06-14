# Frontend UI Skeleton Setup Report

Báo cáo tiến độ dựng lại cấu trúc skeleton frontend cho dự án CC-DFlash.

## Chi tiết công việc đã thực hiện

### 1. Dọn dẹp giao diện cũ
Đã xóa các file tạm và giao diện cũ không còn phù hợp:
* `docs/reports/extra/cc-dflash-title-home.html` (Đã xóa)
* `docs/reports/extra/ui-01-presentation-extra-task-plan-report.md` (Đã xóa)
* `docs/paper/presentation_2.html` (Đã xóa)

*Lưu ý:* Giữ nguyên file `presentation_1.html` của phần HTFSD cũ.

### 2. Thiết lập cấu trúc Frontend mới
Đã dựng cấu trúc thư mục frontend mới và tạo các trang skeleton tối giản (minimalist, tông màu đen / xám / trắng, không sử dụng external CDN):

```text
frontend/
  index.html
  pages/
    cc-dflash/
      cc-dflash.html
      scripts/
        cc-dflash.js
      styles/
        cc-dflash.css
    htfsd/
      htfsd.html
      styles/
        htfsd.css
```

* **Hub Page (`frontend/index.html`):** Trang điều hướng tối giản giữa trang CC-DFlash và HTFSD Legacy, có ghi chú rõ đây chỉ là skeleton UI.
* **CC-DFlash Page (`frontend/pages/cc-dflash/cc-dflash.html`):** Thiết lập các section placeholder (Lý do chuyển hướng, Overview, Benchmark design) và khu vực Demo mô phỏng chạy 4 trạng thái (`Baseline-AR`, `DFlash-R1`, `LLMLingua-AR-R2`, `CC-DFlash-R2`).
* **HTFSD Page (`frontend/pages/htfsd/htfsd.html`):** Thiết lập trang skeleton làm khu vực lưu trữ/migrate nội dung HTFSD legacy sau này.

### 3. Tình trạng và Giới hạn (Scope)
* Chưa tích hợp nội dung chi tiết hay kết quả thực tế.
* Chưa phát triển hiệu ứng animation / mô phỏng black hole phức tạp.
* Chưa tích hợp logic chạy interactive demo thực tế.
* **Xác nhận:** Không tác động tới roadmap chính (`docs/Roadmap.html`), task status chung của dự án, hoặc các dữ liệu/kết quả benchmark/results/model/dataset.
