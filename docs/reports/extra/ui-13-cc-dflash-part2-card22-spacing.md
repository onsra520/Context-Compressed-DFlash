# CC-DFlash Part 2 Card 2.2 Spacing & Wrap Report

Báo cáo tiến độ sửa lỗi hiển thị, tránh hiện tượng wrap chữ xấu và tăng khoảng cách an toàn cho **Card 2.2 Vì sao compression có thể hữu ích?** trong phần **Part 2 — Method & Conditions** trên trang thuyết trình CC-DFlash.

## Chi tiết công việc đã thực hiện

### 1. Rút gọn văn bản để tránh wrap chữ và đè callout

* Lỗi phát sinh: Đoạn text của bullet point thứ 4 trong Card 2.2 quá dài, làm inline code `T_compress` cuối dòng bị wrap xuống dòng tiếp theo và dính sát/chạm vào vùng viền của sub-card `CORE QUESTION`.
* Giải pháp: Rút gọn bullet point thứ 4 thành một câu súc tích hơn:
  * **Trước**: *Savings vs T_compress:* Có lợi khi prefill savings + decoding gain lớn hơn `T_compress`.
  * **Sau**: *Savings vs T_compress:* Chỉ có lợi nếu savings vượt chi phí nén.
* Kết quả: Câu văn mới cực kỳ ngắn gọn, toàn bộ nội dung nằm trọn trên một dòng duy nhất, không bị wrap và không có bất kỳ ký tự nào chạm sát callout.

### 2. Thiết lập khoảng cách an toàn (Spacing Gap)

* Giải pháp: Bổ sung thuộc tính `gap: 20px;` vào container `.part2-comparison` trong media query desktop (`@media (min-width: 761px)`).
* Kết quả: Đảm bảo có một khoảng cách tối thiểu 20px giữa tất cả các phần tử bên trong card (từ label số, tiêu đề, đoạn giới thiệu, danh sách bullet cho tới sub-card callout). Ngay cả khi văn bản co giãn trên các kích cỡ màn hình khác nhau, callout chốt `CORE QUESTION` luôn được hiển thị tách biệt rõ ràng khỏi danh sách bullet phía trên.

## Tình trạng và Giới hạn (Scope)

* **Không ảnh hưởng các thành phần khác**: Các card khác như Card `2.3` không bị thay đổi nội dung. Label số card `2.1`, `2.2`, `2.3` vẫn giữ nguyên dạng pill nhỏ gọn gàng.
* **Bảo toàn nội dung kỹ thuật**: Sub-card `CORE QUESTION` vẫn giữ nguyên trọn vẹn văn bản và ý nghĩa yêu cầu.
