import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import About from "./pages/About";
import Context from "./pages/Context";
import Result from "./pages/Result";
import Review from "./pages/Review";
import Start from "./pages/Start";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Start />} />
        <Route path="/forms/:id/context" element={<Context />} />
        <Route path="/forms/:id/review" element={<Review />} />
        <Route path="/forms/:id/result" element={<Result />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<p className="muted">Page not found.</p>} />
      </Route>
    </Routes>
  );
}
