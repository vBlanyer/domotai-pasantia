import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { TemaProvider } from './tema.tsx'
import { Toaster } from './components/ui/toast.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TemaProvider>
      <Toaster>
        <App />
      </Toaster>
    </TemaProvider>
  </StrictMode>,
)
