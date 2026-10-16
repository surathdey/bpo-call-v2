import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "@/components/rpi/Layout";
import CampaignsPage from "@/pages/CampaignsPage";
import CampaignDetailPage from "@/pages/CampaignDetailPage";
import SettingsPage from "@/pages/SettingsPage";
import AuditPage from "@/pages/AuditPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/rpi/campaigns" replace />} />
          <Route path="/rpi/campaigns" element={<CampaignsPage />} />
          <Route path="/rpi/campaigns/:id" element={<CampaignDetailPage />} />
          <Route path="/rpi/settings" element={<SettingsPage />} />
          <Route path="/rpi/audit" element={<AuditPage />} />
          <Route path="*" element={<Navigate to="/rpi/campaigns" replace />} />
        </Route>
      </Routes>
      <Toaster theme="dark" position="bottom-right" richColors />
    </BrowserRouter>
  );
}

export default App;
