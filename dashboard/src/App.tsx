import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import EvalResults from './pages/EvalResults';
import RetrievalInspector from './pages/RetrievalInspector';
import KnowledgeBase from './pages/KnowledgeBase';
import Ingestion from './pages/Ingestion';
import CostDashboard from './pages/CostDashboard';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<EvalResults />} />
          <Route path="inspector" element={<RetrievalInspector />} />
          <Route path="knowledge" element={<KnowledgeBase />} />
          <Route path="ingestion" element={<Ingestion />} />
          <Route path="costs" element={<CostDashboard />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
