import { data, metricDefs } from "../mocks/mock-data.js";
import { initArchitectureGraph } from "./architecture-graph.js";
import { initBenchmarkShowdown } from "./benchmark-showdown.js";

initArchitectureGraph();
initBenchmarkShowdown({ data, metricDefs });

