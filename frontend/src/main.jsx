import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { useCssVars } from './tokens'

const rootElement = document.getElementById('root')
Object.assign(rootElement.style, useCssVars())

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
