import ResearchSources from "./research-sources/index";
import DataChart from "./data-chart/index";
import PythonCode from "./python-code/index";
import EmailDraft from "./email-draft/index";

const ComponentMap = {
  "research-sources": ResearchSources,
  "data-chart": DataChart,
  "python-code": PythonCode,
  "email-draft": EmailDraft,
} as const;

export default ComponentMap;
