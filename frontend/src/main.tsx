import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles/tokens.css'
import './styles/fonts.css'
import './styles/base.css'

const root = ReactDOM.createRoot(document.getElementById('root')!)

if (window.location.pathname === '/api') {
  // Public API docs — standalone, no router or auth context.
  import('./pages/ApiPage').then(({ ApiPage }) => {
    root.render(<React.StrictMode><ApiPage /></React.StrictMode>)
  })
} else {
  Promise.all([import('./App'), import('./i18n/config')]).then(([{ App }]) => {
    root.render(<React.StrictMode><App /></React.StrictMode>)
  })
}
