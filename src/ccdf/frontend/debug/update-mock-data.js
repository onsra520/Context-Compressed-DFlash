const fs = require('fs');

const mockDataContent = `export const architectureSteps = [
    {
        title: 'ORIGINAL PROMPT',
        description: 'Nhận yêu cầu ban đầu gồm context, câu hỏi và các ràng buộc cần được giữ nguyên.',
        node: 'nInput',
        activeEdge: null,
        metric: '184 TOKENS',
        inputPreview: 'Yêu cầu bữa tối cho 8 người,\\nkèm ngân sách, thời gian và dị ứng.',
        operation: 'NHẬN PROMPT',
        outputPreview: '184 tokens\\nContext + question + output rules',
        accent: 'yellow'
    },
    {
        title: 'PROMPT SEGMENTER',
        description: 'Tách phần context có thể nén khỏi câu hỏi và các chỉ dẫn quan trọng.',
        node: 'nSplit',
        activeEdge: 'original-to-context-compression',
        metric: '184 → 120 + 64',
        inputPreview: '184-token original prompt',
        operation: 'TÁCH CONTEXT VÀ RÀNG BUỘC',
        outputPreview: 'Context: 120 tokens\\nProtected block: 64 tokens',
        accent: 'cyan'
    },
    {
        title: 'LLMLINGUA-2',
        description: 'Rút gọn phần context, giữ lại các chi tiết liên quan đến yêu cầu.',
        node: 'nCompress',
        activeEdge: 'segmenter-to-llmlingua',
        metric: '120 → 60 TOKENS',
        inputPreview: '120 context tokens\\nMón Việt · bếp 2 vùng · chuẩn bị nhanh',
        operation: 'NÉN CONTEXT · KEEP 50%',
        outputPreview: '60 compressed tokens\\nGiữ các chi tiết liên quan đến thực đơn',
        accent: 'pink'
    },
    {
        title: 'PROTECTED QUESTION',
        description: 'Giữ nguyên câu hỏi và các ràng buộc số bên ngoài vùng context được nén.',
        node: 'nProtect',
        activeEdge: 'segmenter-to-protected-question',
        metric: '64 TOKENS · GIỮ NGUYÊN',
        inputPreview: '3 món · 8 người · 2 suất chay\\n≤ 1.500.000đ',
        operation: 'BYPASS COMPRESSION',
        outputPreview: '18:30–21:00 · đúng 4 gạch đầu dòng\\nKhông dùng đậu phộng',
        accent: 'lime'
    },
    {
        title: 'PROMPT COMPRESSION',
        description: 'Ghép context đã nén với câu hỏi và các chỉ dẫn được bảo vệ.',
        node: 'nMerge',
        activeEdge: 'context-compression-to-prompt-compression',
        metric: '60 + 64 → 124',
        inputPreview: '60 compressed context tokens\\n+ 64 protected tokens',
        operation: 'GHÉP LẠI PROMPT',
        outputPreview: '124 prompt tokens\\nContext rút gọn + toàn bộ ràng buộc gốc',
        accent: 'purple'
    },
    {
        title: 'TARGET PREFILL',
        description: 'Mô hình đích xử lý prompt đã rút gọn và tạo context state cho D-Flash.',
        node: 'nPrefill',
        activeEdge: 'prompt-compression-to-target-prefill',
        metric: '124 INPUT TOKENS',
        inputPreview: '124 prompt tokens\\nContext nén + ràng buộc nguyên vẹn',
        operation: 'TARGET PREFILL',
        outputPreview: 'Target cache ready\\nSẵn sàng cho D-Flash generation',
        accent: 'orange'
    },
    {
        title: 'DFLASH DRAFT',
        description: 'Đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.',
        node: 'nDraft',
        activeEdge: 'target-prefill-to-dflash-container',
        metric: 'CYCLE 1 / 3',
        inputPreview: 'Target cache\\n+ empty output buffer',
        operation: 'KHỞI TẠO D-FLASH',
        outputPreview: 'Generation state ready\\nDraft Cycle 1',
        accent: 'cyan',
        cycleBadge: 'CYCLE 1 / 3'
    },
    {
        title: 'DFLASH DRAFT',
        description: 'Đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.',
        node: 'nDraft',
        activeEdge: 'draft-to-verify',
        metric: '16 CANDIDATE TOKENS',
        inputPreview: 'Target cache\\n+ current output prefix',
        operation: 'DRAFT · CYCLE 1 / 3',
        outputPreview: '“• Gỏi cuốn chay cho 2 người...”',
        accent: 'cyan',
        cycleBadge: 'CYCLE 1 / 3'
    },
    {
        title: 'TARGET VERIFY',
        description: 'Mô hình đích kiểm chứng block ứng viên và chấp nhận prefix phù hợp.',
        node: 'nVerify',
        activeEdge: 'verify-to-output-buffer',
        metric: '11 / 16 ACCEPTED',
        inputPreview: '16 candidate tokens',
        operation: 'TARGET VERIFY · CYCLE 1 / 3',
        outputPreview: '11 accepted · 5 rejected\\nBuffer: 11 tokens',
        accent: 'purple',
        cycleBadge: 'CYCLE 1 / 3'
    },
    {
        title: 'OUTPUT BUFFER',
        description: 'Tích lũy các token đã được target chấp nhận qua từng cycle.',
        node: 'nBuffer',
        activeEdge: 'output-buffer-to-draft-loop',
        metric: 'BUFFER 11',
        inputPreview: '11 accepted tokens',
        operation: 'COMMIT VÀ LOOP',
        outputPreview: 'Output prefix đã lưu\\nBắt đầu Cycle 2 / 3',
        accent: 'blue',
        cycleBadge: 'CYCLE 1 / 3'
    },
    {
        title: 'DFLASH DRAFT',
        description: 'Đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.',
        node: 'nDraft',
        activeEdge: 'draft-to-verify',
        metric: '16 CANDIDATE TOKENS',
        inputPreview: 'Output prefix: 11 tokens',
        operation: 'DRAFT · CYCLE 2 / 3',
        outputPreview: '“• Gà kho gừng, không đậu phộng...”',
        accent: 'cyan',
        cycleBadge: 'CYCLE 2 / 3'
    },
    {
        title: 'TARGET VERIFY',
        description: 'Mô hình đích kiểm chứng block ứng viên và chấp nhận prefix phù hợp.',
        node: 'nVerify',
        activeEdge: 'verify-to-output-buffer',
        metric: '13 / 16 ACCEPTED',
        inputPreview: '16 candidate tokens',
        operation: 'TARGET VERIFY · CYCLE 2 / 3',
        outputPreview: '13 accepted · 3 rejected\\nBuffer: 24 tokens',
        accent: 'purple',
        cycleBadge: 'CYCLE 2 / 3'
    },
    {
        title: 'OUTPUT BUFFER',
        description: 'Tích lũy các token đã được target chấp nhận qua từng cycle.',
        node: 'nBuffer',
        activeEdge: 'output-buffer-to-draft-loop',
        metric: 'BUFFER 24',
        inputPreview: '13 accepted tokens',
        operation: 'COMMIT VÀ LOOP',
        outputPreview: '24 committed tokens\\nBắt đầu Cycle 3 / 3',
        accent: 'blue',
        cycleBadge: 'CYCLE 2 / 3'
    },
    {
        title: 'DFLASH DRAFT',
        description: 'Đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.',
        node: 'nDraft',
        activeEdge: 'draft-to-verify',
        metric: '16 CANDIDATE TOKENS',
        inputPreview: 'Output prefix: 24 tokens',
        operation: 'DRAFT · CYCLE 3 / 3',
        outputPreview: '“• Tổng chi phí dự kiến 1.350.000đ...”',
        accent: 'cyan',
        cycleBadge: 'CYCLE 3 / 3'
    },
    {
        title: 'TARGET VERIFY',
        description: 'Mô hình đích kiểm chứng block ứng viên và chấp nhận prefix phù hợp.',
        node: 'nVerify',
        activeEdge: 'verify-to-output-buffer',
        metric: '9 / 16 ACCEPTED',
        inputPreview: '16 candidate tokens',
        operation: 'TARGET VERIFY · CYCLE 3 / 3',
        outputPreview: '9 accepted · 7 rejected\\nBuffer: 33 tokens',
        accent: 'purple',
        cycleBadge: 'CYCLE 3 / 3'
    },
    {
        title: 'FINAL OUTPUT',
        description: 'Hoàn tất câu trả lời sau ba cycle draft–verify.',
        node: 'nFinal',
        activeEdge: 'dflash-container-to-final-output',
        metric: '33 COMMITTED TOKENS',
        inputPreview: 'Completed Output Buffer',
        operation: 'FINALIZE',
        outputPreview: '3 món · 4 gạch đầu dòng\\n≤ 1.500.000đ · không đậu phộng',
        accent: 'blue',
        cycleBadge: 'CYCLE 3 / 3'
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
