import { configure } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// Lazy routes load their module on first render, which can exceed the 1s
// default on slower machines or a cold transform cache.
configure({ asyncUtilTimeout: 5000 });
