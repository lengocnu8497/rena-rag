import { NavLink, Outlet } from 'react-router-dom';
import { BarChart2, Search, Database, Upload, DollarSign } from 'lucide-react';

const NAV = [
  { to: '/', label: 'Eval Results', icon: BarChart2, exact: true },
  { to: '/inspector', label: 'Retrieval Inspector', icon: Search },
  { to: '/knowledge', label: 'Knowledge Base', icon: Database },
  { to: '/ingestion', label: 'Ingestion', icon: Upload },
  { to: '/costs', label: 'Cost Dashboard', icon: DollarSign },
];

export function Layout() {
  return (
    <div className="min-h-screen flex bg-gray-50">
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-200">
          <div className="text-lg font-semibold text-gray-900">Rena RAG</div>
          <div className="text-xs text-gray-500 mt-0.5">Engineering Dashboard</div>
        </div>
        <nav className="flex-1 py-3">
          {NAV.map(({ to, label, icon: Icon, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-4 py-2 text-sm mx-2 rounded-md transition-colors ${
                  isActive
                    ? 'bg-purple-50 text-purple-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-gray-200 text-xs text-gray-400">
          FastAPI: localhost:8000
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
