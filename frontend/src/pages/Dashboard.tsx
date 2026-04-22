import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { getDistrictSummary, getRecentEvents } from '../services/api'

const EVENT_TYPE_COLORS: Record<string, string> = {
  violence: 'bg-red-100 text-red-700',
  stampede: 'bg-orange-100 text-orange-700',
  protest: 'bg-yellow-100 text-yellow-700',
  accident: 'bg-blue-100 text-blue-700',
  crime: 'bg-purple-100 text-purple-700',
  fire: 'bg-red-50 text-red-500',
  misinformation: 'bg-gray-100 text-gray-700',
  general: 'bg-slate-100 text-slate-600',
}

export function Dashboard() {
  const [selectedDays, setSelectedDays] = useState(7)

  const { data: summary = [] } = useQuery({
    queryKey: ['districtSummary', selectedDays],
    queryFn: () => getDistrictSummary(selectedDays),
    refetchInterval: 60_000,
  })

  const { data: recentEvents = [] } = useQuery({
    queryKey: ['recentEvents', selectedDays],
    queryFn: () => getRecentEvents({ days: selectedDays, limit: 30 }),
    refetchInterval: 60_000,
  })

  const topDistricts = summary.slice(0, 10)

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Intelligence Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Uttar Pradesh — Real-time Incident Overview</p>
        </div>
        <select
          value={selectedDays}
          onChange={e => setSelectedDays(Number(e.target.value))}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {[1, 7, 30, 90].map(d => (
            <option key={d} value={d}>Last {d} {d === 1 ? 'day' : 'days'}</option>
          ))}
        </select>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Events', value: recentEvents.length },
          { label: 'Districts Active', value: topDistricts.length },
          { label: 'High Severity', value: recentEvents.filter(e => e.sentiment === -1).length },
          { label: 'Avg Credibility', value: recentEvents.length > 0
              ? (recentEvents.reduce((s, e) => s + (e.credibility || 0), 0) / recentEvents.length * 100).toFixed(0) + '%'
              : '—' },
        ].map(stat => (
          <div key={stat.label} className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <p className="text-xs text-gray-500">{stat.label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Chart */}
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
        <h2 className="text-base font-semibold text-gray-800 mb-4">Events by District</h2>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={topDistricts} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="district" tick={{ fontSize: 11 }} angle={-30} textAnchor="end" height={50} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recent Events */}
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
        <h2 className="text-base font-semibold text-gray-800 mb-4">Recent Events</h2>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {recentEvents.length === 0 && (
            <p className="text-gray-400 text-sm">No events found for this period.</p>
          )}
          {recentEvents.map(ev => (
            <div key={ev.event_id} className="flex gap-3 items-start py-2 border-b border-gray-50 last:border-0">
              <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 font-medium ${EVENT_TYPE_COLORS[ev.event_type] || EVENT_TYPE_COLORS.general}`}>
                {ev.event_type}
              </span>
              <div className="min-w-0">
                <p className="text-sm text-gray-800 line-clamp-2">{ev.content}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {ev.district} · {new Date(ev.occurred_at).toLocaleDateString('en-IN')} · {ev.source}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
