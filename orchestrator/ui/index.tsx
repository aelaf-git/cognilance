import ResearchSources from "./research-sources/index";
import DataChart from "./data-chart/index";
import PythonCode from "./python-code/index";

const ComponentMap = {
  "research-sources": ResearchSources,
  "data-chart": DataChart,
  "python-code": PythonCode,
} as const;

export default ComponentMap;
