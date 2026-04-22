import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { ChatInterface } from './components/ChatInterface'
import { Dashboard } from './pages/Dashboard'

const queryClient = new QueryClient()

const navClass = ({ isActive }: { isActive: boolean }) =>
  `px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
    isActive
      ? 'bg-blue-600 text-white'
      : 'text-gray-600 hover:bg-gray-100'
  }`

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex h-screen flex-col bg-gray-50">
          {/* Top Nav */}
          <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <span className="text-white text-xs font-bold">UP</span>
              </div>
              <div>
                <h1 className="text-sm font-bold text-gray-900">PHQ Intelligence Bot</h1>
                <p className="text-xs text-gray-400">Police HQ, Uttar Pradesh</p>
              </div>
            </div>
            <nav className="flex gap-2">
              <NavLink to="/" end className={navClass}>Dashboard</NavLink>
              <NavLink to="/chat" className={navClass}>Intelligence Query</NavLink>
            </nav>
          </header>

          {/* Content */}
          <main className="flex-1 overflow-hidden">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/chat" element={
                <div className="h-full max-w-4xl mx-auto">
                  <ChatInterface />
                </div>
              } />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
