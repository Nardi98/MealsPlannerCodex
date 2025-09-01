import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { useCssVars } from './tokens.js'

// eslint-disable-next-line react-hooks/rules-of-hooks
const cssVars = useCssVars()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <div style={cssVars}>
      <App />
    </div>
  </StrictMode>,
)
