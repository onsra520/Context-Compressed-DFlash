import { data, metricDefs } from "../mocks/mock-data.js";
import { initArchitectureGraph } from "./architecture-graph.js";
import { initBenchmarkShowdown } from "./benchmark-showdown.js";
import { initMetricsExplained } from "./metrics-explained.js";

initArchitectureGraph();
initBenchmarkShowdown({ data, metricDefs });
initMetricsExplained({ metricDefs });

