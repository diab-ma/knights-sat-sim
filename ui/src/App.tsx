import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ChallengePage, NotFound, Workstation } from "@/Workstation";

const ComponentExamples = import.meta.env.DEV
  ? lazy(() => import("@/ComponentExamples"))
  : null;

export default function App() {
  return (
    <BrowserRouter>
      <TooltipProvider>
        <Routes>
          <Route element={<Workstation />}>
            <Route
              index
              element={<Navigate to="/challenges/hello-satellite" replace />}
            />
            <Route
              path="challenges/:challenge_id"
              element={<ChallengePage />}
            />
            {ComponentExamples && (
              <Route
                path="dev/components"
                element={
                  <Suspense fallback={<p>Loading component examples…</p>}>
                    <ComponentExamples />
                  </Suspense>
                }
              />
            )}
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </TooltipProvider>
    </BrowserRouter>
  );
}
