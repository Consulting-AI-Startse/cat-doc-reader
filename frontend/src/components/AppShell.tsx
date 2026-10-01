import { Link, NavLink, Outlet } from "react-router-dom";

export function AppShell() {
  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="sticky top-0 z-20 border-b border-neutral-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-2.5">
          <Link to="/" className="flex items-center">
            <img src="/cat-logo-mark.png" alt="Caterpillar" className="h-6" />
          </Link>
          <span className="h-5 w-px bg-neutral-200" />
          <span className="text-sm font-semibold text-neutral-500">Document Reader</span>
          {/* Ate aqui nao havia menu: so se navegava pelo Dashboard, entao a
              tela de part numbers seria inalcancavel sem isto. */}
          <nav className="ml-4 flex items-center gap-1">
            {[
              { to: "/", rotulo: "Documentos", exato: true },
              { to: "/part-numbers", rotulo: "Part numbers", exato: false },
              { to: "/fornecedores", rotulo: "Fornecedores", exato: false },
            ].map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.exato}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-neutral-100 text-neutral-900"
                      : "text-neutral-500 hover:bg-neutral-50 hover:text-neutral-900"
                  }`
                }
              >
                {item.rotulo}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
