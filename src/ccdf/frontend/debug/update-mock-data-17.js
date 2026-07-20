const fs = require('fs');

const mockDataContent = `export const architectureSteps = [
  {
    id: "original-prompt",
    node: "nInput",
    activeEdge: null,
    title: "ORIGINAL PROMPT",
    description: "Nhận yêu cầu ban đầu gồm context, câu hỏi và các ràng buộc cần được giữ nguyên.",
    accent: "yellow",
    trace: {
      metric: "184 TOKENS",
      input: "Bữa tối cho 8 người, gồm yêu cầu ăn uống, ngân sách và thời gian.",
      operation: "NHẬN PROMPT",
      output: "184 tokens · context + question + output rules"
    }
  },
  {
    id: "prompt-segmenter",
    node: "nSplit",
    activeEdge: "original-to-context-compression",
    title: "PROMPT SEGMENTER",
    description: "Tách phần context có thể nén khỏi câu hỏi và các chỉ dẫn quan trọng.",
    accent: "cyan",
    trace: {
      metric: "184 → 120 + 64",
      input: "184-token original prompt",
      operation: "TÁCH CONTEXT VÀ RÀNG BUỘC",
      output: "Context: 120 tokens · Protected block: 64 tokens"
    }
  },
  {
    id: "llmlingua-2",
    node: "nCompress",
    activeEdge: "segmenter-to-llmlingua",
    title: "LLMLINGUA-2",
    description: "Rút gọn phần context, giữ lại các chi tiết liên quan đến yêu cầu.",
    accent: "pink",
    trace: {
      metric: "120 → 60 TOKENS",
      input: "120 context tokens · món Việt · bếp 2 vùng · chuẩn bị nhanh",
      operation: "NÉN CONTEXT · KEEP 50%",
      output: "60 compressed tokens · giữ các chi tiết liên quan đến thực đơn"
    }
  },
  {
    id: "protected-question",
    node: "nProtect",
    activeEdge: "segmenter-to-protected-question",
    title: "PROTECTED QUESTION",
    description: "Giữ nguyên câu hỏi và các ràng buộc số bên ngoài vùng context được nén.",
    accent: "lime",
    trace: {
      metric: "64 TOKENS · GIỮ NGUYÊN",
      input: "3 món · 8 người · 2 suất chay · tối đa 1.500.000đ",
      operation: "BYPASS COMPRESSION",
      output: "18:30–21:00 · đúng 4 gạch đầu dòng · không dùng đậu phộng"
    }
  },
  {
    id: "prompt-compression",
    node: "nMerge",
    activeEdge: "context-compression-to-prompt-compression",
    title: "PROMPT COMPRESSION",
    description: "Ghép context đã nén với câu hỏi và các chỉ dẫn được bảo vệ.",
    accent: "purple",
    trace: {
      metric: "60 + 64 → 124",
      input: "60 compressed context tokens + 64 protected tokens",
      operation: "GHÉP LẠI PROMPT",
      output: "124 prompt tokens · context rút gọn + toàn bộ ràng buộc gốc"
    }
  },
  {
    id: "target-prefill",
    node: "nPrefill",
    activeEdge: "prompt-compression-to-target-prefill",
    title: "TARGET PREFILL",
    description: "Mô hình đích xử lý prompt đã rút gọn và tạo context state cho D-Flash.",
    accent: "orange",
    trace: {
      metric: "124 INPUT TOKENS",
      input: "124 prompt tokens · context nén + ràng buộc nguyên vẹn",
      operation: "TARGET PREFILL",
      output: "Target cache ready · sẵn sàng cho D-Flash generation"
    }
  },
  {
    id: "enter-dflash",
    node: "nDraft",
    activeEdge: "target-prefill-to-dflash-container",
    title: "ENTER D-FLASH",
    description: "Target Prefill chuyển trạng thái context đã xử lý vào vòng sinh D-Flash.",
    accent: "cyan",
    trace: {
      metric: "CYCLE 1 / 3",
      input: "Target cache + empty output buffer",
      operation: "KHỞI TẠO D-FLASH",
      output: "Generation state ready · bắt đầu Draft Cycle 1"
    }
  },
  {
    id: "draft-cycle-1",
    node: "nDraft",
    activeEdge: "draft-to-verify",
    title: "DRAFT — CYCLE 1",
    description: "Đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.",
    accent: "cyan",
    trace: {
      metric: "16 CANDIDATE TOKENS",
      input: "Target cache + output prefix rỗng",
      operation: "DRAFT · CYCLE 1 / 3",
      output: "Ứng viên: “• Gỏi cuốn chay cho 2 người...”"
    }
  },
  {
    id: "verify-cycle-1",
    node: "nVerify",
    activeEdge: "verify-to-output-buffer",
    title: "VERIFY — CYCLE 1",
    description: "Mô hình đích kiểm chứng block ứng viên và chấp nhận prefix phù hợp.",
    accent: "purple",
    trace: {
      metric: "11 / 16 ACCEPTED",
      input: "16 candidate tokens từ Cycle 1",
      operation: "TARGET VERIFY · CYCLE 1 / 3",
      output: "11 accepted · 5 rejected · Buffer: 11 tokens"
    }
  },
  {
    id: "loop-cycle-1",
    node: "nBuffer",
    activeEdge: "output-buffer-to-draft-loop",
    title: "LOOP — CYCLE 1",
    description: "Tích lũy các token đã được target chấp nhận qua từng cycle.",
    accent: "blue",
    trace: {
      metric: "BUFFER 11",
      input: "11 accepted tokens",
      operation: "COMMIT VÀ LOOP",
      output: "Đã lưu món chay · bắt đầu Cycle 2 / 3"
    }
  },
  {
    id: "draft-cycle-2",
    node: "nDraft",
    activeEdge: "draft-to-verify",
    title: "DRAFT — CYCLE 2",
    description: "Đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.",
    accent: "cyan",
    trace: {
      metric: "16 CANDIDATE TOKENS",
      input: "Output prefix: 11 committed tokens",
      operation: "DRAFT · CYCLE 2 / 3",
      output: "Ứng viên: “• Gà kho gừng, không dùng đậu phộng...”"
    }
  },
  {
    id: "verify-cycle-2",
    node: "nVerify",
    activeEdge: "verify-to-output-buffer",
    title: "VERIFY — CYCLE 2",
    description: "Mô hình đích kiểm chứng block ứng viên và chấp nhận prefix phù hợp.",
    accent: "purple",
    trace: {
      metric: "13 / 16 ACCEPTED",
      input: "16 candidate tokens từ Cycle 2",
      operation: "TARGET VERIFY · CYCLE 2 / 3",
      output: "13 accepted · 3 rejected · Buffer: 24 tokens"
    }
  },
  {
    id: "loop-cycle-2",
    node: "nBuffer",
    activeEdge: "output-buffer-to-draft-loop",
    title: "LOOP — CYCLE 2",
    description: "Tích lũy các token đã được target chấp nhận qua từng cycle.",
    accent: "blue",
    trace: {
      metric: "BUFFER 24",
      input: "13 accepted tokens",
      operation: "COMMIT VÀ LOOP",
      output: "Hai phần nội dung đã lưu · bắt đầu Cycle 3 / 3"
    }
  },
  {
    id: "draft-cycle-3",
    node: "nDraft",
    activeEdge: "draft-to-verify",
    title: "DRAFT — CYCLE 3",
    description: "Đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.",
    accent: "cyan",
    trace: {
      metric: "16 CANDIDATE TOKENS",
      input: "Output prefix: 24 committed tokens",
      operation: "DRAFT · CYCLE 3 / 3",
      output: "Ứng viên: “• Tổng chi phí dự kiến 1.350.000đ...”"
    }
  },
  {
    id: "verify-cycle-3",
    node: "nVerify",
    activeEdge: "verify-to-output-buffer",
    title: "VERIFY — CYCLE 3",
    description: "Mô hình đích kiểm chứng block ứng viên và chấp nhận prefix phù hợp.",
    accent: "purple",
    trace: {
      metric: "9 / 16 ACCEPTED",
      input: "16 candidate tokens từ Cycle 3",
      operation: "TARGET VERIFY · CYCLE 3 / 3",
      output: "9 accepted · 7 rejected · Buffer: 33 tokens"
    }
  },
  {
    id: "buffer-complete",
    node: "nBuffer",
    activeEdge: "dflash-container-to-final-output",
    title: "OUTPUT BUFFER COMPLETE",
    description: "Hoàn tất output buffer sau khi thực thi đủ các cycle D-Flash.",
    accent: "blue",
    trace: {
      metric: "BUFFER 33",
      input: "33 committed tokens sau ba cycle",
      operation: "HOÀN TẤT OUTPUT BUFFER",
      output: "Đủ 3 món · đúng ngân sách · giữ nguyên ràng buộc ăn uống"
    }
  },
  {
    id: "final-output",
    node: "nFinal",
    activeEdge: null,
    title: "FINAL OUTPUT",
    description: "Hoàn tất câu trả lời sau ba cycle draft–verify.",
    accent: "blue",
    trace: {
      metric: "FINAL RESPONSE",
      input: "Completed Output Buffer · 33 committed tokens",
      operation: "FINALIZE",
      output: "3 món · đúng 4 gạch đầu dòng · ≤ 1.500.000đ · không đậu phộng"
    }
  }
];

export const demoPresets = {
    gsm8k: {
        label: 'GSM8K · short numeric prompt',
        prompt: \`Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?\\n\\nReturn the result on the final line using: Final answer: <number>\`
    },
    qmsum: {
        label: 'QMSum · long meeting context',
        prompt: \`Meeting transcript:\\n\\nAlice: We need to decide how the mobile release should handle offline synchronization. The current build retries every ten seconds, but this causes duplicate uploads when the connection is unstable.\\n\\nBob: The backend team can add idempotency keys, although that will not land before the next release candidate. For the short term, the client could queue changes locally and retry only after the network state has been stable for thirty seconds.\\n\\nCarla: Product wants the release this Friday. We can accept a limited offline mode if the interface clearly shows which records are pending. We should not silently discard edits.\\n\\nAlice: Then the proposal is to keep local changes, display a pending badge, wait for a stable connection, and retry. Duplicate protection will be added on the server in the following sprint.\\n\\nBob: I agree, but analytics events should not be queued with business records. They can be dropped if the app is closed.\\n\\nCarla: Please document that distinction in the release notes and create a follow-up ticket for server-side idempotency.\\n\\nQuestion: What decision did the team make about offline synchronization for the upcoming release, and what work was deferred?\`
    },
    custom: {
        label: 'Custom prompt',
        prompt: 'Tối thứ Bảy tôi mời 8 người ăn tối. Có 2 người ăn chay, 1 người dị ứng đậu phộng và 1 người không ăn cay. Nhà có 2 vùng nấu, 1 nồi và 1 chảo; mọi người thích món Việt, dễ chia phần và chuẩn bị nhanh.\\n\\nHãy đề xuất thực đơn 3 món, tổng chi phí không quá 1.500.000đ. Bắt đầu lúc 18:30, xong trước 21:00. Trả lời đúng 4 gạch đầu dòng và không dùng đậu phộng.'
    }
};

export const metricDefs = [
    ['Original input tokens', 'Estimated tokens in the full prompt before any compression.'],
    ['Effective prefill tokens', 'Tokens actually processed during target prefill. Baseline-AR and D-Flash use the full input; CC-DFlash uses the compressed prompt.'],
    ['Compression ratio', 'Original input tokens divided by compressed input tokens. Only applies to CC-DFlash.'],
    ['Compression overhead', 'CPU time spent compressing the context before model inference.'],
    ['Prefill latency', 'Time required for the target model to process the input prompt and initialize the cache.'],
    ['Generation latency', 'Time spent generating output tokens after prefill.'],
    ['End-to-end latency', 'Compression overhead + prefill + generation. This is the conservative comparison metric.'],
    ['Generation throughput', 'Output tokens divided by generation latency. It does not include compression or prefill.'],
    ['Acceptance length τ', 'Average number of draft tokens accepted per DFlash verification step. Not applicable to Baseline-AR.'],
    ['Numeric quality proxy', 'GSM8K uses final numeric answer matching as a deterministic quality signal.'],
    ['Lexical overlap proxy', 'QMSum uses normalized overlap as diagnostic evidence, not semantic correctness.'],
    ['Workload class', 'Short, medium, or long context. Compression becomes more useful as prefill savings can offset its overhead.']
];
`;
fs.writeFileSync('mocks/mock-data.js', mockDataContent);
console.log('Updated mock-data.js');
