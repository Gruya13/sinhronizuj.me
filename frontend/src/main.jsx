import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { StudioProvider } from './context/StudioContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <StudioProvider>
      <App />
    </StudioProvider>
  </StrictMode>,
)
