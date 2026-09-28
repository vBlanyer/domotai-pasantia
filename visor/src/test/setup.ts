import "@testing-library/jest-dom/vitest"
import { afterEach } from "vitest"
import { cleanup } from "@testing-library/react"

// Sin `globals`, Testing Library no desmonta solo entre tests: cada test empieza con el DOM vacío.
afterEach(() => cleanup())
