import { BrowserRouter, Route, Routes } from 'react-router-dom'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<div style={{ color: 'white', padding: 32, background: '#0f1117', minHeight: '100vh' }}>
          <h1>Digital Twin Supply Chain</h1>
          <p style={{ color: '#94a3b8', marginTop: 8 }}>Platform loading — Phase -1 scaffold running ✓</p>
        </div>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
