export const demoData = {
    context: "ê tui đang tìm cái bài nổi nổi trên toktok, hình như có câu “gòi mưa giông đến đây thiếu vắng một bóng hình hông phai”, nó là remix giực giưc nghe quen lắm mà không nhớ  bài gì",
    protectedQuestion: "lyric tiếp theo là gì nhỉ?",
    compressedContext: "bài nổi trên toktok, câu “gòi mưa giông đến đây thiếu vắng một bóng hình hông phai”, remix giực giưc"
};
demoData.originalPrompt = `${demoData.context}\n\n${demoData.protectedQuestion}`;
demoData.finalCompressedPrompt = `${demoData.compressedContext}\n\n${demoData.protectedQuestion}`;

const estimateTokens = (text) => Math.ceil(text.length / 4);

const originalTokens = estimateTokens(demoData.originalPrompt);
const contextTokens = estimateTokens(demoData.context);
const protectedTokens = estimateTokens(demoData.protectedQuestion);
const compressedTokens = estimateTokens(demoData.compressedContext);
const finalTokens = estimateTokens(demoData.finalCompressedPrompt);
const reduction = Math.round((contextTokens - compressedTokens) / contextTokens * 100) + '%';

export const architectureSteps = [
  {
    id: "original-prompt",
    node: "nInput",
    activeEdge: null,
    title: "ORIGINAL PROMPT",
    description: "Nhận nguyên văn prompt do người dùng nhập trước khi phân tách và xử lý.",
    accent: "yellow",
    trace: {
      "TRẠNG THÁI": "PROMPT RECEIVED",
      "TOKENS ƯỚC TÍNH": originalTokens.toString()
    }
  },
  {
    id: "prompt-segmenter",
    node: "nSplit",
    activeEdge: ["segmenter-to-llmlingua", "segmenter-to-protected-question"],
    title: "PROMPT SEGMENTER",
    description: "Tách prompt thành hai nhánh được xử lý đồng thời: ngữ cảnh cần nén và câu hỏi cần giữ nguyên.",
    accent: "cyan",
    trace: {
      "TRẠNG THÁI": "SPLIT INTO 2 BRANCHES",
      "BRANCH": "2",
      "CONTEXT TOKENS": contextTokens.toString(),
      "PROTECTED TOKENS": protectedTokens.toString()
    }
  },
  {
    id: "llmlingua-2",
    node: "nCompress",
    activeEdge: "segmenter-to-llmlingua",
    title: "COMPRESSOR",
    description: "LLMLingua-2 loại bỏ phần diễn đạt dư thừa và giữ lại thông tin cần thiết trong ngữ cảnh.",
    accent: "pink",
    trace: {
      "TRẠNG THÁI": "CONTEXT COMPRESSED",
      "INPUT TOKENS": contextTokens.toString(),
      "OUTPUT TOKENS": compressedTokens.toString(),
      "REDUCTION": reduction
    }
  },
  {
    id: "protected-question",
    node: "nProtect",
    activeEdge: "segmenter-to-protected-question",
    title: "PROTECTED QUESTION",
    description: "Giữ nguyên câu hỏi và yêu cầu trả lời, không đưa phần này qua bộ nén.",
    accent: "lime",
    trace: {
      "TRẠNG THÁI": "QUESTION LOCKED",
      "TOKENS": protectedTokens.toString(),
      "CHANGE": "NONE"
    }
  },
  {
    id: "prompt-compression",
    node: "nMerge",
    activeEdge: ["context-compression-to-prompt-compression", "prompt-compression-to-dflash"],
    title: "PROMPT COMPRESSION",
    description: "Ghép ngữ cảnh sau xử lý với câu hỏi được bảo vệ để tạo prompt cuối.",
    accent: "purple",
    trace: {
      "TRẠNG THÁI": "PROMPT MERGED",
      "OUTPUT TOKENS": finalTokens.toString(),
      "SOURCES": "2"
    }
  },
  {
    id: "target-prefill",
    node: "nPrefill",
    activeEdge: "prefill-to-draft",
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
    id: "draft-cycle-1",
    node: "nDraft",
    activeEdge: "draft-to-verify",
    title: "DRAFT — CYCLE 1",
    description: "Đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.",
    accent: "cyan",
    trace: {
      metric: "8 CANDIDATE TOKENS",
      input: "Target cache + output prefix rỗng",
      operation: "DRAFT · CYCLE 1 / 3",
      output: "Ứng viên: “[lyric] [tiếp] [theo] [là] [đây]...”"
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
      metric: "4 / 8 ACCEPTED",
      input: "8 candidate tokens từ Cycle 1",
      operation: "TARGET VERIFY · CYCLE 1 / 3",
      output: "4 accepted · 1 rejected (đây -> Bàn) · Buffer: 5 tokens"
    }
  },
  {
    id: "loop-cycle-1",
    node: "nBuffer",
    activeEdge: "output-buffer-to-prefill",
    title: "LOOP — CYCLE 1",
    description: "Tích lũy các token đã được target chấp nhận qua từng cycle.",
    accent: "blue",
    trace: {
      metric: "BUFFER 5",
      input: "4 accepted tokens + 1 corrected",
      operation: "COMMIT VÀ LOOP",
      output: "Đã lưu: lyric tiếp theo là Bàn · bắt đầu Cycle 2 / 3"
    }
  },
  {
    id: "draft-cycle-2",
    node: "nDraft",
    activeEdge: "draft-to-verify",
    title: "DRAFT — CYCLE 2",
    description: "Đề xuất một block gồm 8 candidate token từ trạng thái generation hiện tại.",
    accent: "cyan",
    trace: {
      metric: "8 CANDIDATE TOKENS",
      input: "Output prefix: 5 committed tokens",
      operation: "DRAFT · CYCLE 2 / 3",
      output: "Ứng viên: “[chân] [ai] [chờ] [ai]...”"
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
      metric: "2 / 8 ACCEPTED",
      input: "8 candidate tokens từ Cycle 2",
      operation: "TARGET VERIFY · CYCLE 2 / 3",
      output: "2 accepted · 1 rejected (chờ -> đợi) · Buffer: 8 tokens"
    }
  },
  {
    id: "loop-cycle-2",
    node: "nBuffer",
    activeEdge: "output-buffer-to-prefill",
    title: "LOOP — CYCLE 2",
    description: "Tích lũy các token đã được target chấp nhận qua từng cycle.",
    accent: "blue",
    trace: {
      metric: "BUFFER 8",
      input: "2 accepted tokens + 1 corrected",
      operation: "COMMIT VÀ LOOP",
      output: "Đã lưu: Bàn chân ai đợi · bắt đầu Cycle 3 / 3"
    }
  },
  {
    id: "draft-cycle-3",
    node: "nDraft",
    activeEdge: "draft-to-verify",
    title: "DRAFT — CYCLE 3",
    description: "Đề xuất một block gồm 8 candidate token từ trạng thái generation hiện tại.",
    accent: "cyan",
    trace: {
      metric: "8 CANDIDATE TOKENS",
      input: "Output prefix: 8 committed tokens",
      operation: "DRAFT · CYCLE 3 / 3",
      output: "Ứng viên: “[ai] [nghe] [tiếng] [khóc]...”"
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
      metric: "7 / 8 ACCEPTED",
      input: "8 candidate tokens từ Cycle 3",
      operation: "TARGET VERIFY · CYCLE 3 / 3",
      output: "7 accepted · 1 empty · Buffer: 15 tokens"
    }
  },
  {
    id: "buffer-complete",
    node: "nBuffer",
    activeEdge: "dflash-to-final-output",
    title: "OUTPUT BUFFER COMPLETE",
    description: "Hoàn tất output buffer sau khi thực thi đủ các cycle D-Flash.",
    accent: "blue",
    trace: {
      metric: "BUFFER 15",
      input: "15 committed tokens sau ba cycle",
      operation: "HOÀN TẤT OUTPUT BUFFER",
      output: "Đã tạo xong câu trả lời cho người dùng"
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
      input: "Completed Output Buffer",
      operation: "FINALIZE",
      output: "lyric tiếp theo là Bàn chân ai đợi ai nghe tiếng khóc trong đêm dài"
    }
  }
];

export const demoPresets = {
    gsm8k: {
        label: 'GSM8K · short numeric prompt',
        prompt: `Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?\n\nReturn the result on the final line using: Final answer: <number>`
    },
    qmsum: {
        label: 'QMSum · long meeting context',
        prompt: `Meeting transcript:\n\nAlice: We need to decide how the mobile release should handle offline synchronization. The current build retries every ten seconds, but this causes duplicate uploads when the connection is unstable.\n\nBob: The backend team can add idempotency keys, although that will not land before the next release candidate. For the short term, the client could queue changes locally and retry only after the network state has been stable for thirty seconds.\n\nCarla: Product wants the release this Friday. We can accept a limited offline mode if the interface clearly shows which records are pending. We should not silently discard edits.\n\nAlice: Then the proposal is to keep local changes, display a pending badge, wait for a stable connection, and retry. Duplicate protection will be added on the server in the following sprint.\n\nBob: I agree, but analytics events should not be queued with business records. They can be dropped if the app is closed.\n\nCarla: Please document that distinction in the release notes and create a follow-up ticket for server-side idempotency.\n\nQuestion: What decision did the team make about offline synchronization for the upcoming release, and what work was deferred?`
    },
    custom: {
        label: 'Custom prompt',
        prompt: 'Tối thứ Bảy tôi mời 8 người ăn tối. Có 2 người ăn chay, 1 người dị ứng đậu phộng và 1 người không ăn cay. Nhà có 2 vùng nấu, 1 nồi và 1 chảo; mọi người thích món Việt, dễ chia phần và chuẩn bị nhanh.\n\nHãy đề xuất thực đơn 3 món, tổng chi phí không quá 1.500.000đ. Bắt đầu lúc 18:30, xong trước 21:00. Trả lời đúng 4 gạch đầu dòng và không dùng đậu phộng.'
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
