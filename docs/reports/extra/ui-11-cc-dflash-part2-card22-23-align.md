# CC-DFlash Part 2 Card 2.2/2.3 Alignment Report

Báo cáo tiến độ hoàn thành tối ưu hóa căn gióng chiều dọc và đồng bộ nhịp điệu nội dung giữa **Card 2.2 Vì sao compression có thể hữu ích?** và **Card 2.3 Không phải lossless end-to-end** trong phần **Part 2 — Method & Conditions** trên trang thuyết trình CC-DFlash.

## Chi tiết công việc đã thực hiện

### 1. Đồng bộ chiều cao và Căn gióng chân Callout (Align Bottom) trên Desktop

* Nhờ lưới đối xứng 2 cột đã được thiết lập ở Task UI-10, cả hai card đã có cùng chiều cao bên ngoài.
* Để đẩy phần callout `.insight-strip` của cả hai card về sát cạnh dưới (align bottom) và thẳng hàng với nhau theo chiều dọc, chúng tôi đã áp dụng CSS Flexbox:
  * Thiết lập `.section-card` bên trong lưới Part 2 thành một vertical flex container (`display: flex; flex-direction: column;`).
  * Sử dụng thuộc tính `margin-top: auto` cho `.insight-strip` của Part 2 để tự động chiếm dụng toàn bộ khoảng trống thừa phía trên và đẩy callout xuống đáy card.
* Quy tắc CSS trên chỉ áp dụng cho màn hình lớn hơn `760px` (`@media (min-width: 761px)`) để trên các thiết bị di động khi các card xếp dọc, khoảng cách (margin-top) tự động co về mốc `20px` mặc định, ngăn chặn hiện tượng co hẹp khoảng cách gây lỗi giao diện.

### 2. Đồng bộ hóa độ dài Bullet Points

* Rút gọn và chuẩn hóa độ dài văn bản của các bullet points trong cả hai card để đảm bảo nhịp điệu đọc (text density) tương đương, tránh việc card 2.3 bị quá nặng chữ so với card 2.2.
* **Văn bản mới của Card 2.2**:
  * *Prefill cost*: Xử lý input chiếm phần lớn thời gian khi prompt dài.
  * *Giảm input tokens*: Nén context giúp giảm lượng tính toán prefill.
  * *DFlash hỗ trợ decoding*: Tăng tốc sinh token tiếp theo (decoding phase).
  * *Savings vs T_compress*: Có lợi khi prefill savings + decoding gain lớn hơn `T_compress`.
* **Văn bản mới của Card 2.3**:
  * *Verify trên context nén*: DFlash chạy trên prompt đã bị nén.
  * *Nén mất mát*: Compressor có thể làm mất chi tiết quan trọng.
  * *Rủi ro output*: Nếu mất thông tin cốt lõi, output cuối có thể sai.
  * *Evaluation*: Phải đo cả speedup và quality proxy.

## Tình trạng và Giới hạn (Scope)

* **Giữ nguyên các nội dung kỹ thuật**: Không đổi các khái niệm, mốc thời gian, kết quả thí nghiệm, hay claim boundary.
* **Canvas / Shaders / Shaders background**: Không thay đổi.
