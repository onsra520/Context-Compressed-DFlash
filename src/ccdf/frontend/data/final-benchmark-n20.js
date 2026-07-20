export const finalBenchmarkN20 = {
    label: 'FINAL BENCHMARK',
    sampleSize: 'N=20',
    conditions: [
        'Baseline-AR',
        'DFlash-R1',
        'LLMLingua-AR-R2',
        'CC-DFlash-R2',
    ],
    datasets: {
        gsm8k: {
            throughput: [
                { name: 'Baseline-AR', value: 31.98 },
                { name: 'DFlash-R1', value: 114.64 },
                { name: 'LLMLingua-AR-R2', value: 31.64 },
                { name: 'CC-DFlash-R2', value: 110.45 },
            ],
            reduction: {
                original: 96.25,
                effective: 94.05,
                reduced: 2.20,
                reductionRate: 0.0227,
                originalLabel: 'Original',
                effectiveLabel: 'Final effective input',
                note: 'SHORT PROMPTS CHỨA ÍT PHẦN DƯ NÊN MỨC GIẢM TOKEN RẤT NHỎ.',
            },
            quality: {
                metric: 'Numeric Exact Match',
                scaleMaximum: 20,
                values: [
                    { name: 'Baseline-AR', value: 18, display: '18/20' },
                    { name: 'DFlash-R1', value: 18, display: '18/20' },
                    { name: 'LLMLingua-AR-R2', value: 18, display: '18/20' },
                    { name: 'CC-DFlash-R2', value: 18, display: '18/20' },
                ],
                note: 'Cả bốn conditions đều đạt 18/20 trên GSM8K.',
            },
            latency: {
                dflash: { generation: 1126.05, total: 1126.05 },
                ccdflash: { compression: 87.16, generation: 1089.12, total: 1176.28 },
                deltaMs: 50.22,
                deltaRate: 0.0446,
            },
        },
        qmsum: {
            throughput: [
                { name: 'Baseline-AR', value: 22.74 },
                { name: 'DFlash-R1', value: 41.60 },
                { name: 'LLMLingua-AR-R2', value: 23.86 },
                { name: 'CC-DFlash-R2', value: 40.90 },
            ],
            reduction: {
                original: 11675.65,
                selected: 932.35,
                effective: 846.80,
                originalLabel: 'Original full transcript',
                effectiveLabel: 'Final effective context',
                effectiveSublabel: 'SELECTED + COMPRESSED',
                note: 'PHẦN LỚN MỨC GIẢM ĐẾN TỪ QUERY-AWARE CONTEXT SELECTION; LLMLINGUA CHỈ NÉN THÊM CONTEXT ĐÃ ĐƯỢC CHỌN.',
            },
            quality: {
                metric: 'ROUGE-L F1',
                scaleMaximum: 0.22,
                values: [
                    { name: 'Baseline-AR', value: 0.1914, display: '0.1914' },
                    { name: 'DFlash-R1', value: 0.1984, display: '0.1984' },
                    { name: 'LLMLingua-AR-R2', value: 0.1933, display: '0.1933' },
                    { name: 'CC-DFlash-R2', value: 0.1922, display: '0.1922' },
                ],
                note: 'ROUGE-L đo mức trùng khớp chuỗi từ với bản tham chiếu. Điểm gần nhau chỉ phản ánh độ giống bề mặt, không bảo đảm câu trả lời đúng nghĩa hoặc đầy đủ.',
            },
            latency: {
                dflash: { generation: 2012.81, total: 2012.81 },
                ccdflash: { compression: 619.75, generation: 2223.29, total: 2843.05 },
                deltaMs: 830.24,
                deltaRate: 0.4125,
            },
        },
    },
    throughputNote: 'DFlash tăng tốc generation; tok/s không bao gồm compression overhead.',
    latencyNote: 'Decode có thể nhanh, nhưng pipeline end-to-end vẫn chịu compression overhead.',
    conclusions: [
        'DFlash tăng decode throughput rõ rệt so với autoregressive decoding.',
        'CC-DFlash giảm mạnh input trên QMSum long context, nhưng giảm rất ít trên GSM8K short prompt.',
        'GSM8K đạt kết quả tốt nhất 18/20.',
        'QMSum giữ lexical overlap gần baseline, nhưng không claim semantic correctness.',
        'CC-DFlash chậm hơn DFlash end-to-end trên cả hai dataset.',
    ],
};
