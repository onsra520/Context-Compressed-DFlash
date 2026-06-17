# CC-DFlash Final Report


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

## 1. Lý do chuyển hướng

### 1.1. Mục tiêu ban đầu

Ban đầu, project đi theo hướng tăng tốc inference bằng speculative decoding. Mục tiêu chính là giảm thời gian sinh output token bằng cách để một mô hình hoặc cơ chế draft dự đoán trước nhiều token, sau đó mô hình chính kiểm tra và chấp nhận một phần token hợp lệ. Nếu acceptance tốt, hệ thống có thể sinh nhiều token hơn trong mỗi bước và giảm latency so với autoregressive decoding thông thường.

Hướng ban đầu được nghiên cứu theo tinh thần HTFSD, tức cố gắng kết hợp nhiều ý tưởng tăng tốc decoding vào một pipeline. Về mặt lý thuyết, hướng này có thể hấp dẫn vì speculative decoding tập trung trực tiếp vào bottleneck sinh token. Tuy nhiên, khi triển khai thực tế trên môi trường giới hạn tài nguyên, project bắt đầu gặp các vấn đề về độ phức tạp tích hợp, overhead và khả năng kiểm chứng.

### 1.2. Blocker của hướng HTFSD

Blocker lớn nhất của hướng HTFSD là độ phức tạp kiến trúc. Hướng này không chỉ đơn giản là chạy một baseline và một drafter, mà còn phải xử lý quan hệ giữa drafter, verifier, acceptance ratio, số token dự đoán trước, prompt format và cơ chế fallback khi token không được chấp nhận. Khi các thành phần này không khớp tốt với nhau, phần overhead có thể lớn hơn phần lợi ích đạt được.

Trong benchmark thử nghiệm ban đầu trên môi trường low-tier, tín hiệu tốc độ không tốt. Baseline GPU có thời gian khoảng 3403 ms, trong khi hướng Full Replay với K=4 mất khoảng 9672 ms, tức chậm hơn baseline khoảng 2.84 lần. Hướng Incremental KV với K=8 còn chậm hơn, khoảng 15650 ms, tức chậm hơn baseline khoảng 4.60 lần. Mặc dù một số output vẫn tương đương, tốc độ không đạt được mục tiêu ban đầu.

Ngoài ra, acceptance ratio thấp cũng là một blocker quan trọng. Khi số token được chấp nhận không đủ cao, speculative decoding không còn mang lại lợi ích thực tế. Thay vì giảm số lần gọi mô hình chính, pipeline lại phải trả thêm chi phí cho draft, verify và fallback. Điều này làm hướng HTFSD trở nên rủi ro để dùng làm MVP đầu tiên.

### 1.3. Vì sao cần chuyển hướng

Từ các blocker trên, project không kết luận rằng speculative decoding là hướng sai. Vấn đề là hướng HTFSD quá phức tạp để làm MVP trong điều kiện thời gian, tài nguyên và khả năng kiểm chứng hiện tại. Nếu tiếp tục theo hướng này, project có nguy cơ bị kẹt ở phần tích hợp kỹ thuật mà chưa tạo được một benchmark rõ ràng để trả lời câu hỏi nghiên cứu.

Vì vậy, project chuyển sang một hướng đơn giản hơn và dễ kiểm chứng hơn: CC-DFlash. Thay vì can thiệp sâu vào speculative decoding pipeline, CC-DFlash giữ DFlash như một thành phần decoding và thêm một lớp context compression ở phía trước. Như vậy, project không cố sửa DFlash core, mà kiểm tra một giả thuyết độc lập hơn: nếu context đầu vào được nén trước, liệu DFlash có thể chạy hiệu quả hơn trong một số setting hay không.

### 1.4. Ý nghĩa của việc chuyển sang CC-DFlash

Việc chuyển hướng sang CC-DFlash giúp project có một câu hỏi nghiên cứu rõ hơn. Thay vì hỏi "làm sao ghép nhiều cơ chế speculative decoding để nhanh hơn", project chuyển sang hỏi:

**Context compression có thể hỗ trợ DFlash bằng cách giảm input tokens và prefill cost hay không, sau khi đã tính cả chi phí nén và chất lượng đầu ra?**

Câu hỏi này phù hợp hơn với một MVP vì có thể kiểm chứng bằng benchmark có điều kiện rõ ràng. Project có thể tách riêng baseline, DFlash-only, compression-only và compression + DFlash để biết phần nào tạo ra lợi ích, phần nào tạo ra overhead và phần nào làm giảm chất lượng.

Tóm lại, quyết định chuyển hướng không phải là bỏ mục tiêu tăng tốc inference, mà là đổi sang một giả thuyết dễ đo hơn, dễ audit hơn và phù hợp hơn với phạm vi project hiện tại.

---

## 2. CC-DFlash và Conditions

### 2.1. Ý tưởng chính của CC-DFlash

CC-DFlash là viết tắt của Context-Compressed DFlash. Ý tưởng chính là đặt một lớp nén context ở phía trước DFlash. Pipeline tổng quát có thể mô tả như sau:

**Original context → Context compression → Compressed natural text → DFlash → Output**

Trong pipeline này, context gốc được đưa qua một compressor trước. Compressor tạo ra phiên bản context đã nén, nhưng output của compressor vẫn là natural text. Sau đó, context đã nén được đưa vào DFlash như một prompt bình thường. DFlash tiếp tục thực hiện vai trò decoding trên compressed context.

Điểm quan trọng là CC-DFlash không sửa DFlash core. Project không thêm meta-token, không truyền hidden state trung gian, không thay đổi vocabulary và không yêu cầu kiến trúc model chính thay đổi. Phần compression được đặt như một lớp độc lập ở phía trước pipeline.

Cách làm này giúp giảm rủi ro tích hợp so với hướng HTFSD ban đầu. Thay vì cố ghép nhiều cơ chế speculative decoding phức tạp, CC-DFlash giữ DFlash ổn định và kiểm tra tác động của việc rút gọn input context.

### 2.2. Vì sao context compression có thể hữu ích

Trong long-context inference, chi phí không chỉ nằm ở quá trình sinh token đầu ra. Trước khi model sinh output, toàn bộ input context cần được xử lý trong giai đoạn prefill. Khi context dài, prefill có thể chiếm một phần đáng kể của tổng latency.

Nếu context được nén từ số token lớn xuống số token nhỏ hơn, chi phí xử lý input có thể giảm. Khi kết hợp với DFlash, pipeline có thể hưởng lợi từ hai phía:

- compression giảm số lượng input tokens cần xử lý;
- DFlash giúp tăng tốc giai đoạn decoding;
- nếu phần tiết kiệm từ input/prefill và decoding lớn hơn chi phí nén, end-to-end runtime có thể cải thiện.

Tuy nhiên, compression không miễn phí. LLMLingua-2 cần thời gian để nén context, được ghi nhận bằng `T_compress`. Vì vậy, câu hỏi của CC-DFlash không phải chỉ là "context có được nén không", mà là:

**Sau khi tính cả `T_compress`, pipeline có nhanh hơn và quality proxy có còn ổn định hay không?**

### 2.3. CC-DFlash không phải pipeline lossless end-to-end

Một điểm cần nhấn mạnh là CC-DFlash không claim lossless full pipeline. DFlash có thể verify token trên compressed context, nhưng compressed context đã là kết quả của một bước nén có mất mát thông tin. Nếu compressor làm mất chi tiết quan trọng, output cuối cùng vẫn có thể sai.

Vì vậy, cách diễn giải đúng là:

**Lossy input compression + DFlash trên compressed context không đồng nghĩa với lossless full pipeline.**

Điều này làm cho phần evaluation trở nên rất quan trọng. Project không chỉ đo tốc độ, mà còn phải kiểm tra quality proxy để biết compression có làm mất thông tin cần thiết hay không.

### 2.4. Vì sao cần bốn conditions

CC-DFlash có hai thành phần tác động chính: compression và DFlash. Nếu chỉ so sánh CC-DFlash với baseline, project sẽ không biết kết quả đến từ đâu. Một kết quả nhanh hơn có thể đến từ DFlash, từ compression, hoặc từ sự kết hợp của cả hai. Một kết quả chậm hơn cũng có thể đến từ `T_compress`, từ DFlash không hiệu quả sau compression, hoặc từ output bị lỗi.

Vì vậy, project sử dụng bốn conditions chính để tách riêng từng tác động.

| Condition           | Compression | DFlash | Vai trò                                        |
| ------------------- | ----------: | -----: | ---------------------------------------------- |
| **Baseline-AR**     |       Không |  Không | Mốc gốc, autoregressive decoding bình thường   |
| **DFlash-R1**       |       Không |     Có | Đo riêng tác động của DFlash trên full context |
| **LLMLingua-AR-R2** |          Có |  Không | Đo riêng tác động của compression              |
| **CC-DFlash-R2**    |          Có |     Có | Pipeline chính: compression kết hợp với DFlash |

Trong đó, **R1** đại diện cho full-context setting, tức không nén. **R2** đại diện cho compressed-context setting, thường với keep rate khoảng 0.5.

### 2.5. Ma trận 2 × 2

Bốn conditions có thể được nhìn như một ma trận 2 × 2:

|                       | Không DFlash    | Có DFlash    |
| --------------------- | --------------- | ------------ |
| **Không compression** | Baseline-AR     | DFlash-R1    |
| **Có compression**    | LLMLingua-AR-R2 | CC-DFlash-R2 |

Ma trận này giúp benchmark có khả năng attribution. Project có thể đọc từng cặp so sánh như sau:

| Comparison                          | Câu hỏi cần trả lời                                                             |
| ----------------------------------- | ------------------------------------------------------------------------------- |
| **DFlash-R1 vs Baseline-AR**        | DFlash có giúp tăng tốc khi không có compression không?                         |
| **LLMLingua-AR-R2 vs Baseline-AR**  | Compression một mình có lợi hay bị `T_compress` kéo chậm?                       |
| **CC-DFlash-R2 vs LLMLingua-AR-R2** | Sau khi context đã nén, DFlash có giúp pipeline tốt hơn compression-only không? |
| **CC-DFlash-R2 vs DFlash-R1**       | Compression trước DFlash có thật sự giúp hơn DFlash trên full context không?    |
| **CC-DFlash-R2 vs Baseline-AR**     | Toàn pipeline compression + DFlash có lợi hơn baseline gốc không?               |

Trong các so sánh này, cặp **CC-DFlash-R2 vs LLMLingua-AR-R2** đặc biệt quan trọng. Nếu CC-DFlash-R2 nhanh hơn LLMLingua-AR-R2 trong khi quality proxy tương đương, đó là tín hiệu cho thấy DFlash vẫn tạo thêm lợi ích sau khi context đã được nén.

Tuy nhiên, cặp **CC-DFlash-R2 vs DFlash-R1** cần đọc thận trọng. Trong short-context như GSM8K, DFlash-R1 có thể vẫn nhanh hơn vì input ngắn khiến compression khó bù lại `T_compress`. Điều đó không tự động bác bỏ giả thuyết long-context của CC-DFlash.

---

## 3. Thiết kế benchmark và Evaluation

### 3.1. Mục tiêu của benchmark

Sau khi định nghĩa pipeline và bốn conditions, project cần một thiết kế benchmark có thể đọc được công bằng. Với CC-DFlash, benchmark không chỉ cần trả lời "pipeline có nhanh hơn không", mà còn phải trả lời "nhanh hơn hoặc chậm hơn vì lý do gì".

Điểm khó là CC-DFlash có nhiều thành phần cùng tác động đến kết quả. DFlash ảnh hưởng đến decoding. Compression ảnh hưởng đến input tokens, prefill, quality của context và `T_compress`. Nếu chỉ nhìn tổng thời gian hoặc một chỉ số throughput đơn lẻ, kết quả sẽ rất dễ bị hiểu sai.

Benchmark được thiết kế để kiểm tra bốn câu hỏi chính:

1. DFlash có cải thiện tốc độ so với autoregressive baseline không?
2. Compression có giảm input tokens nhưng bị `T_compress` làm mất lợi ích end-to-end không?
3. Sau khi context đã nén, DFlash có còn tạo thêm lợi ích so với compression-only không?
4. Quality proxy có còn ổn định sau khi context bị nén không?

Vì vậy, benchmark phải đo cả chất lượng, tốc độ, compression ratio và overhead.

### 3.2. Generation-only và end-to-end

Một điểm quan trọng trong benchmark là phân biệt **generation-only speed** và **end-to-end speed**.

Generation-only tok/s cho biết tốc độ sinh output sau khi prompt đã sẵn sàng. Chỉ số này hữu ích để hiểu decoding behavior. Tuy nhiên, với compressed pipeline, generation-only không tính phần chi phí nén context.

End-to-end latency hoặc end-to-end tok/s phản ánh thực tế hơn vì có tính cả `T_compress`. Nếu một condition có generation-only nhanh hơn nhưng `T_compress` quá lớn, pipeline vẫn có thể chậm hơn về tổng thể.

| Metric                         | Ý nghĩa                                      | Rủi ro nếu đọc sai                                |
| ------------------------------ | -------------------------------------------- | ------------------------------------------------- |
| **Generation-only tok/s**      | Tốc độ sinh token sau khi prompt đã sẵn sàng | Có thể nhìn nhanh hơn nhưng chưa tính chi phí nén |
| **End-to-end latency / tok/s** | Tốc độ khi tính cả overhead                  | Phù hợp hơn để đánh giá compressed pipeline       |

Vì vậy, khi đọc kết quả CC-DFlash, không được chỉ nhìn generation-only speed. Với các condition có compression, end-to-end metric là cách đọc thận trọng hơn.

### 3.3. Thay máu dataset gần giai đoạn test

Một bước chuyển quan trọng của project là thay đổi setup dataset gần giai đoạn test. Dataset ban đầu theo hướng GSM8K kết hợp context dài kiểu Wikipedia/SQuAD có ích cho giai đoạn thử nghiệm, nhưng chưa tách rõ hai mục tiêu đánh giá khác nhau của CC-DFlash: chất lượng trên short-context và hiệu quả trên long-context.

Vì vậy, project chuyển sang hai dataset chính:

| Dataset                                 | Loại context | Vai trò chính                                                                                                         |
| --------------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------- |
| **GSM8K short-context**                 | Ngắn         | Kiểm tra numeric-quality proxy và khả năng giữ đáp án số                                                              |
| **QMSum-style meeting QA long-context** | Dài          | Quan sát long-context diagnostic behavior: latency, prefill, compression overhead, compression ratio và lexical proxy |

Việc thay dataset này làm project phải quay lại nhiều bước kiểm chứng. Khi dataset thay đổi, prompt policy, output cap, metric và cách đọc kết quả cũng phải được rà lại. Vì vậy, phần lớn thời gian gần giai đoạn benchmark được dùng để kiểm chứng pipeline thay vì chỉ chạy benchmark cuối.

Cách đọc mới là:

- GSM8K không dùng để chứng minh long-context speedup.
- QMSum không dùng để chứng minh semantic correctness.
- GSM8K dùng để kiểm tra numeric-quality proxy.
- QMSum dùng để quan sát long-context diagnostic behavior.

### 3.4. GSM8K: short-context numeric-quality evaluation

GSM8K được dùng để kiểm tra chất lượng ở dạng short-context. Vì câu trả lời thường có đáp án số rõ ràng, project có thể dùng numeric extraction để đánh giá output theo cách deterministic.

Vai trò chính của GSM8K là kiểm tra xem khi context bị nén, pipeline còn giữ được thông tin quan trọng để sinh đáp án số hay không. Điều này đặc biệt hữu ích khi so sánh LLMLingua-AR-R2 và CC-DFlash-R2, vì cả hai đều dùng compressed context nhưng chỉ CC-DFlash-R2 có DFlash.

Tuy nhiên, GSM8K có giới hạn rõ ràng. Đây là short-context dataset, nên không phải nơi tốt nhất để chứng minh lợi ích long-context của compression. Numeric exact match cũng chỉ là proxy chất lượng, không phải semantic correctness tổng quát. Ngoài ra, vì context ngắn, `T_compress` có thể lớn hơn lợi ích từ việc giảm input tokens.

Do đó, GSM8K nên được đọc như short-context numeric-quality proxy, không phải final proof về chất lượng tổng quát của CC-DFlash.

### 3.5. QMSum: long-context diagnostic evaluation

QMSum-style meeting QA được dùng để quan sát hành vi long-context của pipeline. Dataset này phù hợp hơn với giả thuyết CC-DFlash vì context dài làm input tokens, prefill, compression ratio và `T_compress` trở nên quan trọng hơn.

Vai trò chính của QMSum là kiểm tra các tín hiệu diagnostic:

- input token reduction;
- compression ratio;
- `T_compress`;
- `T_prefill`;
- generation tok/s;
- end-to-end latency;
- lexical/normalized quality proxy.

Tuy nhiên, QMSum không được dùng như bằng chứng semantic correctness. Câu trả lời trong QMSum có thể dài, có thể diễn đạt khác reference, và proxy dựa trên lexical overlap hoặc normalized containment có thể không phản ánh đầy đủ chất lượng ngữ nghĩa.

Do đó, QMSum trong project này được giữ như long-context diagnostic evidence, không phải final quality benchmark.

### 3.6. Metric scope

Benchmark sử dụng nhiều metric vì mỗi metric trả lời một phần khác nhau của câu hỏi nghiên cứu.

| Metric                         | Dùng để đọc gì                                                                              |
| ------------------------------ | ------------------------------------------------------------------------------------------- |
| **Numeric exact-match proxy**  | Chất lượng trên GSM8K                                                                       |
| **Normalized / lexical proxy** | Tín hiệu chẩn đoán trên QMSum                                                               |
| **Input tokens**               | Context có thật sự được rút gọn không                                                       |
| **Compression ratio**          | Mức độ nén thực tế                                                                          |
| **`T_compress`**               | Chi phí của LLMLingua-2 compression                                                         |
| **`T_prefill`**                | Chi phí xử lý input context trước decoding, dùng khi artifact hoặc diagnostic summary có đo |
| **Generation tok/s**           | Tốc độ sinh token sau khi prompt đã sẵn sàng                                                |
| **End-to-end latency / tok/s** | Tốc độ thực tế khi tính cả overhead                                                         |
| **Cap-hit / truncation**       | Output có bị giới hạn bởi `max_new_tokens` không                                            |
| **`tau_mean`**                 | Tín hiệu acceptance của DFlash                                                              |

Trong các metric này, end-to-end latency là metric thận trọng hơn khi so sánh compressed pipeline. Generation-only tok/s có ích để hiểu decoding behavior, nhưng không đủ để claim speedup nếu chưa tính `T_compress`.

---

## 4. Quá trình thực nghiệm: từ blocker đến evidence và Limitations

### 4.1. Vì sao phần thực nghiệm phải đi qua nhiều vòng audit

Quá trình thực nghiệm của CC-DFlash không đi thẳng từ prototype đến benchmark cuối cùng. Lý do là pipeline có nhiều thành phần có thể làm kết quả bị sai lệch: dataset, prompt policy, output length, compression overhead, generated text, artifact schema và metric đánh giá.

Nếu một kết quả nhanh hơn xuất hiện, project cần biết đó là do DFlash, do compression, do dataset, hay do cách tính metric. Nếu một kết quả chậm hơn xuất hiện, project cũng cần biết đó là do `T_compress`, do output cap, do quality proxy, hay do runtime noise.

Vì vậy, project đi theo flow:

**Blocker → Fix/Audit → Evidence → Limitation**

Phần nào đã kiểm chứng được thì trở thành evidence. Phần nào chưa đủ chắc thì được đưa vào limitation thay vì overclaim.

### 4.2. Dataset blocker

Blocker đầu tiên là dataset. Setup dataset ban đầu chưa còn khớp hoàn toàn với câu hỏi nghiên cứu cuối cùng. Project cần tách short-context quality khỏi long-context efficiency. Vì vậy, dataset được thay sang GSM8K short-context và QMSum-style meeting QA long-context.

Sau khi thay dataset, project có thể đọc GSM8K như numeric-quality proxy và QMSum như long-context diagnostic. Đây là bước tích cực vì benchmark không còn gom nhiều mục tiêu vào cùng một dataset.

Tuy nhiên, limitation còn lại là QMSum không thể được dùng để claim semantic correctness nếu chưa có manual review hoặc semantic judge. QMSum chỉ đủ an toàn để dùng như diagnostic evidence cho latency, compression overhead, compression ratio và lexical proxy behavior.

### 4.3. Compression overhead blocker

Blocker tiếp theo là compression overhead. Compression có thể giảm input tokens, nhưng LLMLingua-2 cần thời gian để chạy. Nếu `T_compress` lớn hơn phần tiết kiệm từ prefill và decoding, compressed pipeline có thể chậm hơn end-to-end.

Để xử lý blocker này, project tách riêng generation-only metrics và end-to-end metrics. Điều này giúp nhận diện trường hợp một condition nhìn nhanh hơn về generation tok/s nhưng không thật sự nhanh hơn khi tính cả `T_compress`.

Evidence sau audit là project có thể đọc rõ hơn tradeoff giữa token reduction, `T_compress` và end-to-end speed. Limitation còn lại là chưa thể claim compression đã được chứng minh hữu ích end-to-end trong mọi trường hợp.

### 4.4. Output/cap-hit blocker

Một số kết quả ban đầu bị ảnh hưởng bởi output quá ngắn hoặc chạm `max_new_tokens`. Nếu output bị cắt, quality proxy sẽ không phản ánh đúng năng lực thật của condition. Điều này đặc biệt quan trọng với GSM8K, vì output cần sinh đủ reasoning hoặc ít nhất là final answer.

Project xử lý bằng cách tăng output cap, lưu generated text, thêm final-answer policy và dùng protected suffix để đảm bảo instruction quan trọng không bị mất sau compression. Các vòng calibration giúp compressed GSM8K ổn định hơn và dễ audit hơn.

Evidence tích cực là GSM8K numeric-quality pattern trở nên rõ hơn sau các bước calibration. Limitation còn lại là việc tăng output cap có thể làm latency tăng, và không phải mọi failure đều là do truncation. Một số failure vẫn là reasoning failure.

### 4.5. QMSum proxy blocker

QMSum có đặc điểm khác GSM8K. Đây là long-answer QA, nên câu trả lời có thể dài và có nhiều cách diễn đạt đúng khác nhau. Proxy dạng lexical overlap hoặc normalized containment có thể không phản ánh chính xác semantic correctness.

Project đã thử nhiều hướng: concise-answer policy, balanced-answer policy, evidence-focused policy và evidence-retention audit. Các bước này giúp xác định rằng vấn đề QMSum không chỉ là output cap. Sau khi cap-hit được giảm, vẫn còn vấn đề về evidence targeting, answer completeness và lexical proxy.

Evidence tích cực là QMSum vẫn hữu ích để quan sát hành vi long-context: latency, compression overhead, compression ratio và lexical proxy. Limitation là QMSum không được dùng để claim semantic correctness.

### 4.6. Runtime/rerun caveat

Ở giai đoạn rerun/verification cuối, GSM8K n=30 hoàn thành đủ bốn condition, nhưng phần QMSum không hoàn chỉnh: DFlash-R1 trên QMSum chỉ chạy được 2 rows trước khi dừng theo safety rule, còn các rerun QMSum có compression bị skip để tránh mở rộng benchmark khi điều kiện chưa ổn định.

Sau đó, project thực hiện một bước phân tích issue sau rerun để kiểm tra xem đây có phải lỗi cấu trúc của DFlash-R1 hay không. Kết luận an toàn là không có đủ cơ sở để nói DFlash-R1 bị broken. Vấn đề này được giữ như một caveat về runtime/local rerun, không phải bằng chứng cho lỗi thuật toán.

### 4.7. Bảng tổng hợp blocker → evidence → limitation

Bảng dưới đây tổng hợp lại flow **Blocker → Fix/Audit → Evidence → Limitation** cho từng nhóm vấn đề đã trình bày ở trên:

| Blocker              | Fix/Audit                        | Evidence                                                                                    | Limitation còn lại                    |
| -------------------- | -------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------- |
| Dataset mismatch     | Chuyển GSM8K + QMSum             | Tách short-quality và long-diagnostic                                                       | QMSum không phải semantic correctness |
| Compression overhead | Tách generation-only và e2e      | Đọc được `T_compress` impact                                                                | Chưa claim compression proven e2e     |
| Output/cap-hit       | Tăng cap, suffix, generated text | GSM8K ổn định hơn                                                                           | Một số failure vẫn là reasoning       |
| QMSum proxy          | Prompt/proxy triage              | Có tín hiệu diagnostic về latency, compression overhead, compression ratio và lexical proxy | Không claim QMSum correctness         |
| Rerun caveat         | Phân tích issue sau rerun        | Không mở nhánh fix/rerun bổ sung                                                            | Local runtime caveat                  |

---

## 5. Results Summary và Claim-Safety Boundary

### 5.1. Cách đọc phần kết quả

Kết quả của CC-DFlash cần đi kèm claim-safety boundary vì rất dễ bị hiểu quá mức. Nếu chỉ nhìn bảng số, người đọc có thể nghĩ project đã chứng minh universal speedup hoặc semantic correctness. Thực tế, evidence hiện tại có điều kiện theo dataset, metric và runtime setting đã mô tả ở Phần 3.

Phần này chỉ tập trung vào hai câu hỏi: kết quả đọc ra sao, và từ đó có thể claim gì hoặc không được claim gì.

### 5.2. GSM8K Results Summary

Trên GSM8K, hai vòng kiểm chứng n=30 cho thấy numeric-quality pattern tương đối ổn định. Kết quả chính được đọc theo numeric exact-match proxy:

| Condition           | GSM8K numeric-quality result |
| ------------------- | ---------------------------: |
| **Baseline-AR**     |                        25/30 |
| **DFlash-R1**       |                        24/30 |
| **LLMLingua-AR-R2** |                        24/30 |
| **CC-DFlash-R2**    |                        24/30 |

CC-DFlash-R2 giữ numeric-quality proxy tương đương LLMLingua-AR-R2, dù timing trên GSM8K vẫn là local/preliminary nên Trong vòng QMSum n=30 diagnostic, CC-DFlash-R2 từng được quan sát là nhanh hơn LLMLingua-AR-R2 trong local setting, với overlap proxy tương tự, nhưng kết quả này không được dùng để claim universal speedup.

Câu diễn giải an toàn:

**GSM8K cho thấy compressed DFlash path không làm numeric-quality proxy tệ hơn compression-only trong setting đã test, nhưng đây vẫn là short-context numeric proxy, không phải semantic correctness tổng quát.**

**Bridge sang hypothesis:** Kết quả GSM8K không chứng minh long-context speedup, nhưng nó hỗ trợ điều kiện chất lượng tối thiểu: compressed path không làm numeric-quality proxy sụp so với compression-only. Điều này cho phép tiếp tục đọc QMSum như long-context diagnostic, nhưng không chuyển QMSum thành semantic correctness claim.

### 5.3. QMSum Diagnostic Summary

QMSum được giữ như long-context diagnostic evidence. Trong vòng QMSum n=30 diagnostic, CC-DFlash-R2 từng được quan sát là nhanh hơn LLMLingua-AR-R2 trong local setting, với overlap proxy tương tự. Tuy nhiên, các vòng triage sau đó cho thấy nhiều limitation: cap-hit, proxy degradation, câu trả lời quá ngắn và evidence targeting chưa tốt.

Sau các bước triage, project quyết định freeze QMSum như diagnostic long-context evidence, không phải semantic correctness evidence. Vòng rerun cuối của QMSum cũng không hoàn chỉnh: DFlash-R1 trên QMSum dừng sau 2 rows và các rerun QMSum có compression bị skip theo safety rule.

Câu diễn giải an toàn:

**QMSum giúp quan sát behavior của pipeline trong long-context setting, nhưng chưa đủ để claim semantic correctness nếu chưa có manual review hoặc semantic judge.**

### 5.4. Claim-safety boundary

Từ kết quả trên, project cần giữ các giới hạn claim sau:

| Evidence          | Có thể nói                                                         | Không được nói                       |
| ----------------- | ------------------------------------------------------------------ | ------------------------------------ |
| **GSM8K**         | Numeric-quality proxy ổn định trong setting n=30                   | Semantic correctness tổng quát       |
| **QMSum**         | Long-context diagnostic behavior                                   | QMSum semantic correctness           |
| **Timing**        | Local runtime observation                                          | Universal speedup                    |
| **Compression**   | Có tradeoff giữa token reduction, `T_compress` và end-to-end speed | Compression proven useful end-to-end |
| **Runtime issue** | QMSum rerun caveat                                                 | DFlash-R1 broken                     |
| **Deployment**    | Không claim                                                        | Confirmed 8GB hoặc deploy-ready      |

### 5.5. Những claim không được dùng

Project không nên đưa ra các claim sau:

1. CC-DFlash có universal speedup.
2. CC-DFlash có final correctness.
3. QMSum chứng minh semantic correctness.
4. Compression đã được chứng minh luôn hữu ích end-to-end.
5. DFlash-R1 bị broken.
6. Project đã deploy-ready.
7. Project đã confirmed chạy ổn trong 8GB VRAM.

Các giới hạn này không làm kết quả yếu đi. Ngược lại, nó giúp report đáng tin hơn vì kết quả được đọc đúng với phạm vi kiểm chứng.

---

## 6. Conclusion

### 6.1. Kết luận về hướng nghiên cứu

Project bắt đầu từ mục tiêu tăng tốc inference bằng speculative decoding, nhưng hướng HTFSD ban đầu gặp nhiều blocker về kiến trúc, overhead và tín hiệu tốc độ. Vì vậy, project chuyển sang CC-DFlash, một hướng MVP rõ ràng hơn: nén context đầu vào trước DFlash để kiểm tra xem compression có thể hỗ trợ long-context inference hay không.

Sự chuyển hướng này giúp project có một giả thuyết dễ kiểm chứng hơn. Thay vì can thiệp sâu vào DFlash core, CC-DFlash thêm một lớp compression độc lập và đánh giá bằng các condition có khả năng attribution.

### 6.2. Kết luận về thiết kế benchmark

Đóng góp quan trọng của project không chỉ là một kết quả benchmark, mà là một framework đánh giá có cấu trúc. Bốn condition Baseline-AR, DFlash-R1, LLMLingua-AR-R2 và CC-DFlash-R2 giúp tách riêng tác động của baseline, DFlash-only, compression-only và compression + DFlash.

Two-dataset setup cũng giúp tách rõ hai mục tiêu:

- GSM8K cho short-context numeric-quality proxy.
- QMSum cho long-context diagnostic behavior.

Nhờ vậy, project có thể đọc kết quả thận trọng hơn và tránh gán nhầm nguyên nhân.

### 6.3. Kết luận về evidence hiện tại

Evidence hiện tại là partial và conditional. Trên GSM8K, CC-DFlash-R2 giữ numeric-quality proxy tương đương LLMLingua-AR-R2 trong setting n=30. Điều này cho thấy việc thêm DFlash sau compression không làm numeric-quality proxy tệ hơn compression-only trong setting đã test.

Trên QMSum, project có diagnostic evidence cho long-context behavior, nhưng không có đủ cơ sở để claim semantic correctness. Các issue về proxy, evidence targeting và rerun caveat cho thấy QMSum nên được giữ như diagnostic-only.

### 6.4. Kết luận về claim boundary

Project chưa claim universal speedup, chưa claim final correctness, chưa claim deployment readiness và chưa claim confirmed 8GB deployment. Project cũng chưa claim compression đã được chứng minh hữu ích end-to-end trong mọi trường hợp.

Claim an toàn nhất là:

**CC-DFlash là một hypothesis-driven MVP với evidence một phần: pipeline có tín hiệu đáng quan sát khi kết hợp compression và DFlash trong một số setting, nhưng kết luận cuối phải được giữ trong phạm vi dataset, metric và local runtime đã kiểm chứng.**

### 6.5. Hướng tiếp theo

Nếu tiếp tục phát triển, project nên tập trung vào ba hướng:

1. Bổ sung semantic/manual evaluation cho long-context QA.
2. Tối ưu hoặc giảm `T_compress` để kiểm tra lại end-to-end benefit.
3. Rerun QMSum trong điều kiện ổn định hơn để giảm runtime caveat.

Với phạm vi hiện tại, CC-DFlash chưa phải là kết luận cuối về speedup hay correctness, mà là một MVP có evidence có điều kiện và một hướng tiếp tục rõ ràng để củng cố đánh giá long-context.
