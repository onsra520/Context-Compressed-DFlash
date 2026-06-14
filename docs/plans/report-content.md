## 1. Lý do chuyển hướng từ HTFSD sang CC-DFlash

### 1.1. Hướng nghiên cứu ban đầu: HTFSD

Ban đầu, project đi theo hướng **HTFSD** — một hướng thử nghiệm nhằm tăng tốc quá trình sinh văn bản của LLM bằng cách kết hợp nhiều cơ chế speculative decoding.

Trong cách sinh văn bản thông thường, model chính tự dự đoán từng token một. Cách này đơn giản và ổn định, nhưng có thể chậm khi cần sinh nhiều token. Speculative decoding cố gắng tăng tốc bằng cách dùng một model nhỏ hơn để đoán trước một số token, sau đó model chính kiểm tra lại. Nếu các token được đoán trước trùng với lựa chọn của model chính, hệ thống có thể chấp nhận nhiều token trong một lượt và sinh nhanh hơn.

Một số khái niệm cần hiểu:

| Thuật ngữ            | Giải thích ngắn                                                                                      |
| -------------------- | ---------------------------------------------------------------------------------------------------- |
| **Baseline**         | Cách sinh bình thường: model chính tự sinh token, không có model phụ hỗ trợ.                         |
| **Drafter**          | Model nhỏ hơn, dùng để đoán trước token ứng viên.                                                    |
| **Verifier**         | Model chính, dùng để kiểm tra token do drafter đề xuất.                                              |
| **Accepted token**   | Token drafter đoán trùng với verifier nên được giữ lại.                                              |
| **Acceptance ratio** | Tỷ lệ token được verifier chấp nhận. Tỷ lệ này càng thấp thì speculative decoding càng khó có lợi.   |
| **K**                | Số token mà drafter đề xuất trong mỗi vòng. Ví dụ K=4 nghĩa là drafter đoán trước 4 token mỗi cycle. |

Mục tiêu của HTFSD là thử đẩy speculative decoding xa hơn bằng cách kết hợp nhiều tầng dự đoán, bao gồm cả token-level và feature/hidden-state-level. Tuy nhiên, khi đi vào triển khai thực tế, hướng này gặp hai nhóm vấn đề lớn: xung đột kiến trúc và tín hiệu benchmark không tốt ở low-tier.

---

### 1.2. Vấn đề kiến trúc: EAGLE-2 và DFlash không ăn khớp trực tiếp

Một khó khăn lớn của HTFSD là hướng này cố gắng kết hợp hai kiểu tăng tốc có cách vận hành khác nhau: **EAGLE-2** và **DFlash**.

Ở mức dễ hiểu, **EAGLE-2** có thể được hình dung như một cơ chế mở nhiều nhánh dự đoán. Nó xây một cây dự đoán động theo ngữ cảnh, sau đó model chính kiểm tra để chọn nhánh phù hợp. Trong khi đó, **DFlash** đi theo hướng khác: thay vì mở cây dự đoán, nó cố sinh song song một block token bằng cơ chế block diffusion.

Nói ngắn gọn, EAGLE-2 giống như “mở cây dự đoán”, còn DFlash giống như “điền cả một cụm token cùng lúc”. Hai hướng này đều nhằm tăng tốc inference, nhưng tổ chức quá trình draft theo hai cách khác nhau.

| Thành phần      | EAGLE-2 style                                | DFlash style                                             |
| --------------- | -------------------------------------------- | -------------------------------------------------------- |
| Cách draft      | Mở cây dự đoán động theo ngữ cảnh            | Sinh một block token song song                           |
| Tư duy chính    | Chọn nhánh dự đoán có khả năng đúng cao      | Giảm số bước sinh tuần tự bằng block diffusion           |
| Dạng dự đoán    | Dynamic draft tree                           | Parallel block drafting                                  |
| Cách tối ưu     | Tăng số token được chấp nhận qua cây draft   | Sinh nhiều token trong một block                         |
| Rủi ro khi ghép | Cần đồng bộ tree, feature, token và verifier | Không thiết kế để nhận trực tiếp dynamic tree từ EAGLE-2 |

Vì vậy, HTFSD không chỉ là bài toán gọi một model nhỏ rồi cho model lớn kiểm tra. Hướng này phải xử lý interface giữa hai cơ chế khác nhau: một bên là cây dự đoán động, một bên là block diffusion. Nếu muốn ghép hai cơ chế này, hệ thống phải giải quyết đồng thời nhiều vấn đề như tokenizer, token bridge, hidden-state compatibility, verify logic và cách commit token sau mỗi vòng.

Điều này làm HTFSD có rủi ro triển khai cao. Trước khi có thể chứng minh speedup, project đã phải giải quyết nhiều vấn đề tương thích ở tầng nội bộ giữa các model và giữa các cơ chế speculative decoding.

---

### 1.3. Benchmark low-tier cho thấy tín hiệu khả thi thấp

Bên cạnh rủi ro kiến trúc, báo cáo HTFSD cũ ở **Phase 3.16 — Low-Tier Speedup Blocker Audit** cũng cho thấy tín hiệu thực nghiệm không tốt. Đây chưa phải full benchmark cuối cùng, nhưng là một kiểm tra low-tier quan trọng để xem prototype có đủ khả thi để tiếp tục tối ưu hay không.

Môi trường thử nghiệm khi đó sử dụng:

| Thành phần       | Giá trị                                  |
| ---------------- | ---------------------------------------- |
| GPU              | NVIDIA GeForce RTX 4070 Laptop GPU       |
| VRAM             | 8188 MiB                                 |
| Verifier         | `gemma-4-E2B-it-UD-Q4_K_XL.gguf`         |
| Drafter          | `Qwen3-0.6B-UD-Q8_K_XL.gguf`             |
| GPU offload      | Cả drafter và verifier đều chạy trên GPU |
| `max_new_tokens` | 32                                       |
| `prompt_count`   | 8                                        |
| K được thử       | 4 và 8 token mỗi cycle                   |

Kết quả chính:

| Cấu hình                | Giải thích cấu hình                                                                                                                                                                                   |  Wall time |    Speedup | Diễn giải                                                         |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------: | ---------: | ----------------------------------------------------------------- |
| **baseline_gpu**        | Verifier Gemma sinh bình thường từng token, không dùng drafter, không dùng speculative decoding. Đây là mốc so sánh tốc độ.                                                                           | **3403ms** | **1.000×** | Reference                                                         |
| **Full replay, K=4**    | Mỗi cycle, Qwen drafter đề xuất 4 token. Verifier kiểm tra bằng cách chạy lại prompt, phần đã commit và candidate window. Cách này đơn giản hơn nhưng tốn thời gian vì phải replay context nhiều lần. |     9672ms |     0.352× | Khoảng **2.84× chậm hơn baseline**, và chỉ đạt **7/8 equivalent** |
| **Incremental KV, K=8** | Mỗi cycle, Qwen drafter đề xuất 8 token. Verifier cố tái sử dụng KV cache, trim về phần token đã commit rồi verify tiếp để tránh chạy lại toàn bộ context. Đây là bản tối ưu hơn full replay.         |    15650ms |     0.217× | Khoảng **4.60× chậm hơn baseline**, dù đạt **8/8 equivalent**     |

Trong bảng trên, **Full replay** là cách verify đơn giản nhưng tốn thời gian vì verifier phải tính lại nhiều phần context sau mỗi cycle. **Incremental KV** là hướng tối ưu hơn: hệ thống cố giữ lại KV cache của verifier để tránh tính lại từ đầu. Tuy nhiên, ngay cả bản Incremental KV sau khi sửa lỗi vẫn không đạt speedup.

Kết quả này cho thấy HTFSD low-tier không đạt yêu cầu tốc độ. Cấu hình nhanh nhất vẫn chậm hơn baseline khoảng 2.84 lần và chưa tương đương đầy đủ đầu ra. Cấu hình đạt tương đương 8/8 thì lại chậm hơn baseline khoảng 4.60 lần.

---

### 1.4. Các blocker chính của HTFSD low-tier

Kết quả low-tier cho thấy HTFSD không chậm vì một lỗi đơn lẻ, mà do nhiều overhead cộng lại.

Các blocker chính gồm:

* **Drafter call overhead**: mỗi cycle phải gọi Qwen3-0.6B để sinh token ứng viên, tạo thêm chi phí đáng kể.
* **Acceptance ratio thấp**: chỉ khoảng 18–32% token được chấp nhận, nên nhiều cycle không mang lại lợi ích.
* **Token bridge và prompt mismatch**: Qwen drafter và Gemma verifier dùng tokenizer/prompt template khác nhau, làm tăng chi phí chuyển đổi và giảm khả năng token được accept.
* **Fallback-heavy behavior**: nhiều cycle chỉ commit được rất ít token, khiến số vòng lặp tăng lên.

Tóm lại, chi phí gọi drafter và verify nhiều vòng lớn hơn lợi ích từ các token được accept. Vì vậy, HTFSD low-tier chưa cho thấy tín hiệu speedup đủ tốt để tiếp tục làm hướng MVP chính.

---

### 1.5. Kết luận từ HTFSD và lý do chuyển sang CC-DFlash

Từ các kết quả trên, HTFSD không bị loại bỏ vì ý tưởng speculative decoding là sai. Vấn đề là hướng triển khai ban đầu có quá nhiều rủi ro đối với một MVP đầu tiên.

Có hai lý do chính dẫn đến quyết định chuyển hướng. Thứ nhất, HTFSD gặp rủi ro kiến trúc khi cố kết hợp EAGLE-2-style dynamic draft tree với DFlash-style block diffusion. Hai cơ chế này vận hành khác nhau và không thể ghép trực tiếp nếu không thiết kế lại nhiều tầng interface. Thứ hai, benchmark low-tier cho thấy tín hiệu tốc độ âm: prototype không nhanh hơn baseline, ngay cả khi cả drafter và verifier đã được offload lên GPU.

Vì vậy, project chuyển sang hướng **CC-DFlash**. Thay vì cố lai nhiều cơ chế speculative decoding ở tầng nội bộ mô hình, CC-DFlash giữ nguyên DFlash và thêm một lớp nén context đầu vào phía trước.

Hướng mới có pipeline đơn giản hơn:

```text
Original context → Context compression → Compressed natural text → DFlash → Output
```

CC-DFlash tiếp tục mục tiêu tăng tốc inference, nhưng chuyển trọng tâm sang nén context đầu vào trước DFlash. Hướng này giữ nguyên DFlash, dùng compressed context dưới dạng natural text, và tránh được nhiều rủi ro tương thích của HTFSD như tokenizer, hidden-state và feature-space mismatch.

Do đó, CC-DFlash được chọn làm hướng MVP tiếp theo để kiểm tra một giả thuyết thực nghiệm rõ ràng hơn: nếu có thể giảm số lượng input tokens nhưng vẫn giữ chất lượng đầu ra và tok/s ở mức tương đương hoặc tốt hơn, thì context compression có thể là một lớp hỗ trợ có giá trị cho DFlash trong long-context inference.

## 2. CC-DFlash: Hướng tiếp cận sau khi chuyển hướng

### 2.1. Bài toán cần giải quyết

Sau khi loại HTFSD khỏi hướng MVP chính, project chuyển sang một câu hỏi thực nghiệm rõ ràng hơn: nếu không can thiệp sâu vào speculative decoding pipeline, liệu có thể cải thiện hiệu quả inference bằng cách giảm số lượng input tokens trước khi chạy DFlash hay không?

Trong inference của LLM, chi phí không chỉ nằm ở quá trình sinh token đầu ra. Với các prompt dài, model còn phải xử lý toàn bộ input context trước khi bắt đầu sinh. Giai đoạn này thường được gọi là **prefill**.

Có thể hiểu đơn giản:

| Thuật ngữ        | Giải thích ngắn                                                                   |
| ---------------- | --------------------------------------------------------------------------------- |
| **Input tokens** | Số token của prompt/context đầu vào. Prompt càng dài thì input tokens càng nhiều. |
| **Prefill**      | Giai đoạn model đọc và xử lý toàn bộ input context trước khi sinh token đầu tiên. |
| **Decoding**     | Giai đoạn model sinh token đầu ra từng bước.                                      |
| **tok/s**        | Số token sinh được mỗi giây, dùng để đo tốc độ sinh đầu ra.                       |
| **T_compress**   | Thời gian tốn thêm để nén context trước khi chạy model.                           |

DFlash tập trung tăng tốc phần decoding bằng speculative decoding. Tuy nhiên, nếu input context rất dài, phần prefill vẫn có thể chiếm chi phí đáng kể. Vì vậy, CC-DFlash được đặt ra như một hướng bổ sung: giảm độ dài context đầu vào trước khi đưa vào DFlash.

---

### 2.2. Ý tưởng chính của CC-DFlash

CC-DFlash viết tắt theo hướng hiểu trong project là **Context-Compressed DFlash**. Ý tưởng cốt lõi là thêm một lớp nén context trước DFlash.

Pipeline của hướng này là:

```text id="73c7fh"
Original context → Context compression → Compressed natural text → DFlash → Output
```

Thay vì đưa toàn bộ context gốc vào model, hệ thống dùng một compressor để giữ lại phần thông tin quan trọng hơn và loại bỏ bớt phần dư thừa. Sau đó, compressed context vẫn được biểu diễn dưới dạng **natural text**, tức là văn bản bình thường, rồi mới đưa vào DFlash.

Điểm quan trọng là CC-DFlash không sửa DFlash core. DFlash vẫn nhận prompt văn bản như bình thường. Điều này giúp hướng mới tránh được nhiều rủi ro của HTFSD, vì hệ thống không cần ghép hidden-state, không cần đồng bộ feature-space giữa hai kiến trúc speculative decoding, và không cần thiết kế lại cơ chế verify/commit token ở tầng nội bộ.

---

### 2.3. Vì sao nén context có thể hữu ích?

Với long-context inference, prompt đầu vào có thể rất dài. Nếu giảm được số lượng input tokens, model có thể xử lý ít token hơn ở giai đoạn prefill. Về mặt kỳ vọng, điều này có thể giúp giảm thời gian xử lý context và giảm một phần chi phí bộ nhớ.

Tuy nhiên, context compression không miễn phí. Hệ thống phải tốn thêm **T_compress**, tức thời gian chạy compressor. Ngoài ra, compression là một bước **lossy**, vì một phần thông tin trong context gốc có thể bị loại bỏ.

Do đó, CC-DFlash không giả định rằng nén context luôn tốt. Hướng này chỉ có giá trị nếu phần tiết kiệm từ input tokens và prefill đủ lớn để bù lại chi phí nén, đồng thời chất lượng đầu ra không giảm quá nhiều.

Có thể tóm tắt giả thuyết của project như sau:

```text id="kkko94"
Nếu giảm được input tokens mà vẫn giữ chất lượng đầu ra và tok/s ở mức tương đương hoặc tốt hơn,
thì context compression có thể là một lớp hỗ trợ có giá trị cho DFlash trong long-context inference.
```

---

### 2.4. Giới hạn claim của CC-DFlash

Một điểm cần làm rõ là CC-DFlash không phải một pipeline lossless end-to-end.

DFlash, khi xét riêng trên cùng một context đầu vào, hướng tới speculative decoding có kiểm chứng bằng target model. Tuy nhiên, CC-DFlash thêm một bước nén context trước đó. Vì context compression là lossy, compressed context có thể không còn giữ đầy đủ thông tin như context gốc.

Do đó, claim đúng của project là:

```text id="w3ke1j"
Lossy input compression + DFlash trên compressed context ≠ lossless full pipeline.
```

Nói cách khác, DFlash có thể giữ tính đúng tương đối với compressed context, nhưng toàn bộ pipeline CC-DFlash vẫn phụ thuộc vào chất lượng của bước nén. Vì vậy, project cần đánh giá đồng thời cả tốc độ và chất lượng, thay vì chỉ nhìn vào số token được giảm.

---

### 2.5. Vai trò của CC-DFlash trong project

CC-DFlash được chọn làm hướng MVP vì nó có phạm vi thực nghiệm rõ ràng hơn HTFSD. Thay vì cố gắng lai nhiều cơ chế speculative decoding ở tầng nội bộ mô hình, project tập trung vào một can thiệp độc lập hơn: nén context đầu vào trước khi chạy DFlash.

Hướng này cho phép benchmark theo các thành phần dễ đo hơn:

* số input tokens trước và sau nén;
* thời gian nén context;
* thời gian prefill;
* tốc độ sinh token đầu ra;
* chất lượng câu trả lời sau khi nén;
* so sánh giữa baseline, DFlash, compression-only và CC-DFlash.

Nhờ vậy, project có thể kiểm tra từng bước xem context compression có thật sự hỗ trợ DFlash hay chỉ tạo thêm overhead. Đây là nền tảng để chuyển sang phần tiếp theo: thiết kế benchmark và các điều kiện so sánh.

## 3. Thiết kế benchmark và các điều kiện so sánh

### 3.1. Mục tiêu của benchmark

Sau khi xác định CC-DFlash là hướng MVP chính, project cần một thiết kế benchmark đủ rõ để trả lời câu hỏi: việc nén context trước DFlash có thật sự mang lại lợi ích hay chỉ tạo thêm overhead?

CC-DFlash gồm hai thành phần chính: **context compression** và **DFlash**. Vì vậy, nếu chỉ so sánh trực tiếp giữa baseline và CC-DFlash, kết quả sẽ khó diễn giải. Khi đó, nếu CC-DFlash nhanh hơn hoặc chậm hơn, ta chưa biết nguyên nhân đến từ DFlash, từ compression, hay từ sự kết hợp của cả hai.

Do đó, benchmark được thiết kế theo hướng tách riêng từng yếu tố:

* baseline không dùng compression, không dùng DFlash;
* DFlash-only để đo lợi ích riêng của DFlash;
* compression-only để đo ảnh hưởng riêng của context compression;
* CC-DFlash để đo hiệu quả khi kết hợp compression và DFlash.

Cách thiết kế này giúp project không chỉ hỏi “CC-DFlash có nhanh hơn không?”, mà còn phân tích được “nó nhanh hơn hoặc chậm hơn vì lý do gì”.

---

### 3.2. Ý nghĩa của R1 và R2

Trong benchmark, các điều kiện được chia theo hai nhóm context chính: **R1** và **R2**.

**R1** là nhóm giữ nguyên context gốc. Có thể hiểu R1 là cấu hình dùng khoảng **100% input context**, không áp dụng context compression.

**R2** là nhóm có context compression. Trong project này, R2 dùng chính sách nén với `keep_rate ≈ 0.5`, tức mục tiêu giữ lại khoảng **50% phần context/token quan trọng** trước khi đưa vào model. Con số này không nhất thiết luôn đúng tuyệt đối 50% cho mọi prompt, vì kết quả nén thực tế còn phụ thuộc vào tokenizer, nội dung context và cách compressor chọn token quan trọng. Tuy nhiên, về mặt thiết kế benchmark, R2 được hiểu là nhóm context đã được rút gọn khoảng một nửa.

| Nhóm   | Ý nghĩa           | Context đầu vào                     |
| ------ | ----------------- | ----------------------------------- |
| **R1** | Không nén context | Khoảng 100% context gốc             |
| **R2** | Có nén context    | Khoảng 50% context/token quan trọng |

Cách đặt tên này giúp benchmark phân biệt rõ giữa điều kiện dùng context đầy đủ và điều kiện dùng context đã được nén.

---

### 3.3. Bốn điều kiện benchmark chính

Benchmark sử dụng bốn điều kiện chính để tách riêng tác động của từng thành phần.

| Điều kiện           | Context                | Decoding       | Vai trò trong benchmark                                             |
| ------------------- | ---------------------- | -------------- | ------------------------------------------------------------------- |
| **Baseline-AR**     | 100% context gốc       | Autoregressive | Mốc so sánh gốc, không dùng compression và không dùng DFlash.       |
| **DFlash-R1**       | 100% context gốc       | DFlash         | Đo lợi ích riêng của DFlash khi chạy trên context đầy đủ.           |
| **LLMLingua-AR-R2** | Context nén khoảng 50% | Autoregressive | Đo tác động riêng của context compression khi không dùng DFlash.    |
| **CC-DFlash-R2**    | Context nén khoảng 50% | DFlash         | Điều kiện chính của project: nén context trước, sau đó chạy DFlash. |

Trong đó, **AR** nghĩa là autoregressive decoding: model sinh token theo cách thông thường, từng bước một. **DFlash** là điều kiện dùng DFlash để tăng tốc quá trình decoding. **LLMLingua** là điều kiện dùng LLMLingua-2 làm compressor để rút gọn context đầu vào.

Có thể đọc bốn điều kiện này như một ma trận 2 × 2:

| Nhóm so sánh               | Không DFlash    | Có DFlash    |
| -------------------------- | --------------- | ------------ |
| **Không compression / R1** | Baseline-AR     | DFlash-R1    |
| **Có compression / R2**    | LLMLingua-AR-R2 | CC-DFlash-R2 |

Nhờ cách chia này, project có thể so sánh từng phần một cách rõ ràng. Nếu DFlash-R1 nhanh hơn Baseline-AR, lợi ích đó đến từ DFlash. Nếu LLMLingua-AR-R2 giảm input tokens nhưng chậm hơn do chi phí nén, vấn đề nằm ở compression overhead. Nếu CC-DFlash-R2 nhanh hơn LLMLingua-AR-R2, điều đó cho thấy DFlash có thể cải thiện pipeline sau khi context đã được nén.

---

### 3.4. Vì sao cần tách DFlash-only và compression-only?

CC-DFlash là sự kết hợp của compression và DFlash, nên các baseline trung gian là cần thiết để tránh kết luận sai.

Nếu chỉ so sánh **Baseline-AR** với **CC-DFlash-R2**, ta không biết phần thay đổi đến từ đâu. Một kết quả nhanh hơn có thể do DFlash, do context ngắn hơn sau compression, hoặc do cả hai. Ngược lại, một kết quả chậm hơn cũng có thể do chi phí nén quá lớn, DFlash không đủ lợi ích, hoặc chất lượng compression chưa phù hợp.

Vì vậy, hai điều kiện trung gian có vai trò quan trọng:

**DFlash-R1** cho biết DFlash hoạt động như thế nào khi dùng đầy đủ 100% context gốc. Đây là mốc để kiểm tra DFlash-only có tạo speedup trong setting hiện tại hay không.

**LLMLingua-AR-R2** cho biết compression hoạt động như thế nào khi không dùng DFlash. Đây là mốc để kiểm tra việc giảm input tokens có đủ bù lại chi phí `T_compress` hay không.

Sau đó, **CC-DFlash-R2** mới được so sánh với cả ba điều kiện còn lại. Nhờ vậy, benchmark không chỉ đo kết quả cuối cùng, mà còn giải thích được nguồn gốc của kết quả đó.

---

### 3.5. Hai nhóm dataset: short-context và long-context

Benchmark sử dụng hai nhóm dataset để kiểm tra CC-DFlash trong hai tình huống khác nhau: context ngắn và context dài.

| Dataset                           | Vai trò                                          | Lý do sử dụng                                                                                          |
| --------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| **GSM8K short-context**           | Kiểm tra chất lượng trên bài toán reasoning ngắn | Dễ đánh giá bằng đáp án số, phù hợp để kiểm tra compression có làm mất thông tin quan trọng hay không. |
| **QMSum meeting QA long-context** | Kiểm tra long-context inference                  | Phù hợp với giả thuyết của CC-DFlash vì context dài làm chi phí prefill trở nên đáng kể.               |

**GSM8K** là nhóm short-context. Vì prompt tương đối ngắn, lợi ích từ việc giảm input tokens thường không lớn. Tuy nhiên, dataset này hữu ích cho kiểm tra chất lượng, vì câu trả lời có thể được đánh giá bằng numeric match hoặc exact answer proxy. Nếu compression làm mất dữ kiện quan trọng, chất lượng sẽ giảm rõ.

**QMSum meeting QA** là nhóm long-context. Đây là nhóm quan trọng hơn đối với giả thuyết của CC-DFlash, vì project muốn kiểm tra xem context compression có hỗ trợ DFlash trong các prompt dài hay không. Với context dài, nếu compressor giảm được nhiều input tokens, phần prefill có cơ hội giảm đáng kể hơn so với short-context.

Do đó, hai dataset có vai trò khác nhau: GSM8K thiên về kiểm tra độ an toàn chất lượng trên reasoning ngắn, còn QMSum thiên về kiểm tra hiệu quả của CC-DFlash trong long-context inference.

---

### 3.6. Các metric chính cần theo dõi

CC-DFlash không thể được đánh giá chỉ bằng một metric tốc độ. Vì pipeline có thêm bước nén context, benchmark cần theo dõi đồng thời tốc độ, chi phí nén, mức giảm token và chất lượng đầu ra.

| Metric                            | Ý nghĩa                                                                                                                            |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Quality proxy**                 | Đo chất lượng câu trả lời. Với GSM8K có thể dùng numeric/exact match; với QMSum có thể dùng normalized overlap hoặc proxy phù hợp. |
| **Input tokens**                  | Số token đầu vào trước và sau compression.                                                                                         |
| **Compression ratio**             | Mức độ context được rút gọn.                                                                                                       |
| **T_compress**                    | Thời gian chạy compressor.                                                                                                         |
| **T_prefill**                     | Thời gian model xử lý input context trước khi sinh token đầu tiên.                                                                 |
| **Generation tok/s**              | Tốc độ sinh token đầu ra, thường chưa phản ánh toàn bộ overhead.                                                                   |
| **End-to-end tok/s**              | Tốc độ tổng thể sau khi tính cả compression và overhead liên quan.                                                                 |
| **Cap-hit / truncation behavior** | Kiểm tra output có bị chạm giới hạn `max_new_tokens` hoặc bị cắt cụt hay không.                                                    |
| **VRAM**                          | Theo dõi bộ nhớ GPU nếu log có hỗ trợ.                                                                                             |

Trong đó, **end-to-end tok/s** là metric quan trọng vì phản ánh trải nghiệm thực tế hơn generation tok/s. Một điều kiện có thể sinh token nhanh, nhưng nếu `T_compress` quá lớn thì tốc độ tổng thể vẫn thấp.

Tương tự, **quality proxy** cũng rất quan trọng. Compression có thể giảm input tokens, nhưng nếu làm mất thông tin cần thiết khiến câu trả lời sai hoặc thiếu, thì lợi ích tốc độ không còn nhiều ý nghĩa.

---

### 3.7. Cách đọc kết quả benchmark

Khi đọc kết quả benchmark, project không chỉ tìm một con số “nhanh hơn” tuyệt đối. Kết quả cần được đọc theo quan hệ giữa các điều kiện.

| So sánh                             | Ý nghĩa                                                            |
| ----------------------------------- | ------------------------------------------------------------------ |
| **DFlash-R1 vs Baseline-AR**        | DFlash có tạo speedup khi dùng 100% context gốc hay không.         |
| **LLMLingua-AR-R2 vs Baseline-AR**  | Compression-only có giúp ích hay bị `T_compress` làm chậm.         |
| **CC-DFlash-R2 vs LLMLingua-AR-R2** | DFlash có cải thiện pipeline sau compression hay không.            |
| **CC-DFlash-R2 vs DFlash-R1**       | Compression có giúp DFlash hiệu quả hơn hay chỉ tạo thêm overhead. |
| **CC-DFlash-R2 vs Baseline-AR**     | Pipeline đầy đủ có lợi end-to-end so với baseline gốc hay không.   |

Một kết quả tốt không nhất thiết là CC-DFlash thắng mọi điều kiện trong mọi dataset. Điều quan trọng hơn là xác định đúng vùng mà CC-DFlash có giá trị.

Trong short-context như GSM8K, DFlash-R1 có thể nhanh hơn CC-DFlash-R2 vì input ngắn khiến compression khó bù được `T_compress`. Ngược lại, trong long-context như QMSum, CC-DFlash-R2 mới là điều kiện đáng quan sát hơn vì context dài có nhiều cơ hội tiết kiệm prefill.

Vì vậy, benchmark cần được đọc theo đúng giả thuyết của project: CC-DFlash có giá trị nhất khi input context đủ dài, compression giảm được token đáng kể, chi phí `T_compress` không vượt quá phần tiết kiệm được, và chất lượng đầu ra vẫn ở mức tương đương.

---

### 3.8. Vai trò của benchmark trong report

Thiết kế benchmark này giúp report tránh đưa ra kết luận quá sớm. Thay vì chỉ claim rằng CC-DFlash nhanh hơn, project trình bày kết quả theo hướng phân tích điều kiện.

Benchmark cần trả lời các câu hỏi sau:

1. Compression có giảm input tokens đủ nhiều không?
2. Chi phí `T_compress` có quá lớn không?
3. DFlash có cải thiện tốc độ sau khi context đã được nén không?
4. Chất lượng đầu ra có giữ được ở mức chấp nhận được không?
5. CC-DFlash phù hợp hơn với short-context hay long-context?

Những câu hỏi này là nền tảng để chuyển sang phần tiếp theo của report: quá trình thực nghiệm và kết quả hiện có của CC-DFlash.

## 4. Quá trình thực nghiệm và kết quả hiện có của CC-DFlash

### 4.1. Mục tiêu của giai đoạn thực nghiệm

Sau khi thiết kế benchmark, project chuyển sang giai đoạn thực nghiệm để kiểm tra CC-DFlash theo từng bước. Mục tiêu không phải là chứng minh ngay rằng CC-DFlash luôn nhanh hơn baseline, mà là xác định rõ điều kiện nào giúp context compression có giá trị khi kết hợp với DFlash.

Giai đoạn thực nghiệm tập trung vào ba câu hỏi chính:

1. Context compression có giảm được input tokens đủ nhiều không?
2. Chi phí nén `T_compress` có làm mất lợi ích tốc độ không?
3. Chất lượng đầu ra sau khi nén có còn ở mức tương đương hay không?

Vì vậy, các thí nghiệm được chia thành nhiều task nhỏ: từ smoke test, benchmark n nhỏ, artifact audit, quality calibration, đến các run lớn hơn trên GSM8K và QMSum.

---

### 4.2. Chuẩn hóa dataset và benchmark matrix

Project chuyển sang thiết kế hai dataset chính để tách rõ short-context và long-context.

| Dataset                           | Vai trò trong thực nghiệm                                                                           |
| --------------------------------- | --------------------------------------------------------------------------------------------------- |
| **GSM8K short-context**           | Kiểm tra chất lượng trên bài toán reasoning ngắn, chủ yếu dùng numeric/exact match proxy.           |
| **QMSum meeting QA long-context** | Kiểm tra giả thuyết long-context, nơi giảm input tokens có khả năng tác động nhiều hơn đến prefill. |

Cùng với đó, benchmark matrix được cố định theo bốn điều kiện:

| Điều kiện           | Mục đích                                                      |
| ------------------- | ------------------------------------------------------------- |
| **Baseline-AR**     | Mốc so sánh gốc, không compression và không DFlash.           |
| **DFlash-R1**       | Đo tác động riêng của DFlash trên 100% context gốc.           |
| **LLMLingua-AR-R2** | Đo tác động riêng của compression với context nén khoảng 50%. |
| **CC-DFlash-R2**    | Đo pipeline chính: compression kết hợp với DFlash.            |

Việc cố định dataset và benchmark matrix giúp các kết quả sau đó có thể so sánh trực tiếp, tránh tình trạng mỗi task dùng một setting khác nhau.

---

### 4.3. Kết quả bước đầu trên GSM8K

GSM8K được dùng như nhóm short-context để kiểm tra chất lượng và hành vi của các điều kiện benchmark trong prompt ngắn. Vì context không dài, đây không phải môi trường lý tưởng nhất để CC-DFlash thể hiện lợi ích prefill. Tuy nhiên, GSM8K vẫn quan trọng vì nó giúp phát hiện việc compression có làm mất dữ kiện reasoning hay không.

Ở các run GSM8K n=30, kết quả chính cho thấy:

* **CC-DFlash-R2 giữ chất lượng tương đương LLMLingua-AR-R2** trong cùng nhóm context đã nén.
* **CC-DFlash-R2 nhanh hơn LLMLingua-AR-R2** về end-to-end speed, cho thấy DFlash có thể cải thiện pipeline sau compression.
* **DFlash-R1 vẫn là điều kiện nhanh hơn trong short-context**, vì GSM8K có input ngắn nên compression khó bù được chi phí `T_compress`.

Điều này phù hợp với giả thuyết ban đầu: CC-DFlash không nhất thiết phải thắng trong short-context. Với prompt ngắn, lợi ích từ giảm input tokens thường nhỏ, trong khi chi phí nén vẫn tồn tại.

Vai trò chính của GSM8K trong report vì vậy là kiểm tra chất lượng và attribution, không phải chứng minh lợi ích long-context cuối cùng.

---

### 4.4. Kết quả bước đầu trên QMSum long-context

QMSum meeting QA là nhóm quan trọng hơn đối với CC-DFlash, vì context dài giúp kiểm tra trực tiếp giả thuyết giảm input tokens để hỗ trợ prefill.

Ở các run QMSum n=30 với `max_new_tokens=384`, kết quả bước đầu cho thấy:

* **CC-DFlash-R2 nhanh hơn LLMLingua-AR-R2** về end-to-end speed.
* **CC-DFlash-R2 giữ quality proxy tương đương LLMLingua-AR-R2** trong cùng nhóm compressed context.
* Tuy nhiên, nhiều output compressed gặp hiện tượng **cap-hit**, tức output chạm giới hạn `max_new_tokens`.

Cap-hit cho thấy vấn đề không chỉ nằm ở tốc độ. Với QMSum, câu trả lời có thể dài hơn, nên nếu prompt không kiểm soát tốt độ dài output thì kết quả dễ bị cắt cụt hoặc khó đánh giá bằng proxy đơn giản. Vì vậy, QMSum cần thêm bước triage trước khi chạy benchmark lớn hơn.

---

### 4.5. Thử nghiệm concise policy trên QMSum

Để xử lý hiện tượng cap-hit ở QMSum, project thử thêm chính sách yêu cầu câu trả lời ngắn gọn hơn. Mục tiêu là giảm số output chạm `max_new_tokens`, từ đó giúp proxy đánh giá chất lượng ổn định hơn.

Kết quả sau khi áp dụng concise-answer policy cho nhóm compressed cho thấy:

* Cap-hit giảm mạnh, về **0/30** trong các điều kiện compressed.
* Tuy nhiên, **normalized-overlap proxy giảm đáng kể**.

Điều này cho thấy concise policy giải quyết được vấn đề độ dài output, nhưng lại tạo vấn đề mới về quality proxy. Khi câu trả lời ngắn hơn, overlap với đáp án tham chiếu có thể giảm, dù câu trả lời có thể vẫn đúng về mặt ngữ nghĩa. Vì vậy, QMSum chưa thể được kết luận chỉ dựa trên proxy hiện tại.

Kết quả này dẫn đến nhu cầu triage tiếp theo: cần kiểm tra lại prompt policy và quality proxy cho QMSum trước khi mở rộng lên benchmark lớn hơn.

---

### 4.6. Trạng thái hiện tại của evidence

Tính đến thời điểm hiện tại, evidence của CC-DFlash có thể tóm tắt như sau:

| Nhóm                     | Kết quả hiện có                                                                                                                          | Trạng thái        |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| **GSM8K short-context**  | CC-DFlash-R2 giữ chất lượng tương đương LLMLingua-AR-R2 và nhanh hơn LLMLingua-AR-R2, nhưng DFlash-R1 vẫn nhanh hơn trong short-context. | Có evidence n=30  |
| **QMSum long-context**   | CC-DFlash-R2 nhanh hơn LLMLingua-AR-R2 và giữ proxy tương đương ở setting trước concise policy.                                          | Có evidence n=30  |
| **QMSum concise policy** | Giảm cap-hit về 0/30 nhưng làm normalized-overlap proxy giảm.                                                                            | Cần triage tiếp   |
| **QMSum n=100**          | Chưa nên chạy/chưa nên claim cho đến khi prompt và proxy ổn định hơn.                                                                    | Pending next task |

Từ các kết quả này, project có thể đưa ra nhận định thận trọng: CC-DFlash đã có tín hiệu tích cực khi so với compression-only, đặc biệt trong long-context, nhưng chưa đủ để claim kết luận cuối cùng cho QMSum. Vấn đề còn lại không chỉ là tốc độ, mà là cách kiểm soát output và cách đánh giá chất lượng.

---

### 4.7. Công việc tiếp theo

Bước tiếp theo của project là **Task 74 — QMSum prompt/proxy triage**.

Mục tiêu của bước này là kiểm tra lại cách prompt yêu cầu câu trả lời, cách proxy đánh giá chất lượng, và lý do vì sao concise policy làm giảm normalized-overlap. Sau khi phần này được xử lý, project mới có cơ sở tốt hơn để quyết định có mở rộng QMSum lên n=100 hay không.

Do đó, ở thời điểm hiện tại, report chỉ nên xem kết quả QMSum là evidence trung gian. Các kết luận cuối về long-context benchmark cần được cập nhật sau Task 74.
