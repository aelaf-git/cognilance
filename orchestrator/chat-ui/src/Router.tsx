import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./App";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { useIntegrations } from "./hooks/useIntegrations";

function IntegrationsRoute() {
  const { integrations, refresh, connect, disconnect, banner } = useIntegrations();
  return (
    <IntegrationsPage
      integrations={integrations}
      onRefresh={refresh}
      onConnect={connect}
      onDisconnect={disconnect}
      banner={banner}
    />
  );
}

export function RootRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/chat" element={<App />} />
        <Route path="/integrations" element={<IntegrationsRoute />} />
        <Route path="/" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
