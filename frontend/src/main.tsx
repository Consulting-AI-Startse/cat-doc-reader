import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";

import { AppShell } from "./components/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { DocumentDetail } from "./pages/DocumentDetail";
import { PartNumbers } from "./pages/PartNumbers";
import { Suppliers } from "./pages/Suppliers";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/documents/:id" element={<DocumentDetail />} />
            {/* Antes do catch-all, senao cai no Navigate para "/". */}
            <Route path="/part-numbers" element={<PartNumbers />} />
            <Route path="/fornecedores" element={<Suppliers />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
