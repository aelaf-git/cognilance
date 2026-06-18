import ResearchSources from "./research-sources/index";
import DataChart from "./data-chart/index";
import CodeFindings from "./code-findings/index";

const ComponentMap = {
  "research-sources": ResearchSources,
  "data-chart": DataChart,
  "code-findings": CodeFindings,
} as const;

export default ComponentMap;
