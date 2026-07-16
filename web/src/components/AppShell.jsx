import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar.jsx";
import Topbar from "./Topbar.jsx";
import { NorthStar } from "./atoms.jsx";

export default function AppShell() {
  const { pathname } = useLocation();
  return (
    <div className="app">
      <Sidebar />
      <main className="main">
        <NorthStar size={520} opacity={0.04} />
        <Topbar path={pathname} />
        <section className="content">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
