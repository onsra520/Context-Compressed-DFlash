export const liveMetricDefinitions = [
    {
        title: 'Original Input Tokens',
        fields: ['original_input_tokens'],
        description: 'Số token của prompt trước khi nén.',
    },
    {
        title: 'Effective Input Tokens',
        fields: ['input_tokens', 'compressed_input_tokens'],
        description: 'Số token thực tế được model xử lý. CC-DFlash dùng prompt đã nén.',
    },
    {
        title: 'Output Tokens',
        fields: ['output_tokens'],
        description: 'Số token được sinh trong lần chạy.',
    },
    {
        title: 'Token Reduction',
        fields: ['reduction_rate'],
        description: 'Tỷ lệ input token bị loại bỏ: 1 − effective/original.',
    },
    {
        title: 'Compression Latency',
        fields: ['compression_latency_ms'],
        description: 'Thời gian nén prompt trên thiết bị đã chọn: CPU hoặc CUDA.',
    },
    {
        title: 'Time to First Token',
        fields: ['ttft_ms'],
        description: 'Thời gian từ lúc bắt đầu chạy đến token đầu tiên được commit và stream.',
    },
    {
        title: 'Generation Latency',
        fields: ['generation_latency_ms'],
        description: 'Thời gian sinh toàn bộ output, không gồm compression.',
    },
    {
        title: 'Pipeline E2E',
        fields: ['pipeline_e2e_ms'],
        description: 'Baseline/D-Flash: generation. CC-DFlash: compression + generation.',
    },
    {
        title: 'Decode Throughput',
        fields: ['decode_tok_s'],
        description: 'Số output token sinh mỗi giây trong generation, đơn vị tok/s.',
    },
    {
        title: 'Draft Acceptance Rate',
        fields: ['acceptance_rate'],
        description: 'Tỷ lệ draft token được target chấp nhận: accepted/proposed.',
    },
    {
        title: 'Verify Loops',
        fields: ['verify_loops'],
        description: 'Số vòng Draft → Verify để hoàn tất output.',
    },
    {
        title: 'Mean Accepted per Loop',
        fields: ['mean_accepted_tokens_per_loop'],
        description: 'Số draft token trung bình được chấp nhận trong mỗi verify loop.',
    },
];
