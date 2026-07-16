import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell.jsx";
import SignalScreen from "./screens/SignalScreen.jsx";
import SignalLogScreen from "./screens/SignalLogScreen.jsx";
import PortfolioScreen from "./screens/PortfolioScreen.jsx";
import DiscoverScreen from "./screens/DiscoverScreen.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/signal" replace />} />
        <Route path="/signal" element={<SignalScreen />} />
        <Route path="/portfolio" element={<PortfolioScreen />} />
        <Route path="/history" element={<SignalLogScreen />} />
        <Route path="/discover" element={<DiscoverScreen />} />
        <Route path="*" element={<Navigate to="/signal" replace />} />
      </Route>
    </Routes>
  );
}
