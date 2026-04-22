import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { sendQuery, QueryResponse } from '../services/api'

interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  meta?: Pick<QueryResponse, 'confidence' | 'sources' | 'evidence_count' | 'latency_ms' | 'cached'>
}

// Sample queries shown to officers
const SAMPLE_QUERIES = [
  'Were there any violence incidents in Varanasi during Kawad Yatra in the last 5 years?',
  'पिछले 30 दिनों में मथुरा में कौन से हादसे हुए?',
  'What is public sentiment about the new highway project in Lucknow?',
  'Was there a stampede at any temple in UP due to misinformation on social media?',
]

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '0',
      role: 'assistant',
      text: '**नमस्ते। PHQ Government Intelligence Bot में आपका स्वागत है।**\n\nHello. You can ask questions in Hindi or English about incidents, events, public sentiment, or social media trends across Uttar Pradesh districts.\n\n*How can I assist you today?*',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const submit = async (queryText: string) => {
    if (!queryText.trim() || loading) return
    const userMsg: Message = { id: Date.now().toString(), role: 'user', text: queryText }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await sendQuery(queryText)
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: res.answer,
        meta: {
          confidence: res.confidence,
          sources: res.sources,
          evidence_count: res.evidence_count,
          latency_ms: res.latency_ms,
          cached: res.cached,
        },
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          text: 'Sorry, an error occurred. Please try again.',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const confidenceColor = (c: number) =>
    c >= 0.7 ? 'text-green-600' : c >= 0.4 ? 'text-yellow-600' : 'text-red-500'

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(msg => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-2xl rounded-2xl px-4 py-3 shadow-sm ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-sm'
                  : 'bg-white text-gray-800 rounded-bl-sm border border-gray-200'
              }`}
            >
              <ReactMarkdown className="prose prose-sm max-w-none">
                {msg.text}
              </ReactMarkdown>

              {msg.meta && (
                <div className="mt-2 pt-2 border-t border-gray-100 text-xs text-gray-500 flex flex-wrap gap-2">
                  <span className={`font-medium ${confidenceColor(msg.meta.confidence)}`}>
                    Confidence: {Math.round(msg.meta.confidence * 100)}%
                  </span>
                  <span>{msg.meta.evidence_count} records</span>
                  <span>{msg.meta.latency_ms}ms</span>
                  <span>Sources: {msg.meta.sources.join(', ')}</span>
                  {msg.meta.cached && (
                    <span className="bg-green-100 text-green-700 px-1 rounded">cached</span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
              <div className="flex space-x-1 items-center h-5">
                {[0, 1, 2].map(i => (
                  <div
                    key={i}
                    className="w-2 h-2 rounded-full bg-blue-400 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Sample queries */}
      {messages.length <= 1 && (
        <div className="px-4 pb-2">
          <p className="text-xs text-gray-500 mb-2">Sample queries:</p>
          <div className="flex flex-wrap gap-2">
            {SAMPLE_QUERIES.map(q => (
              <button
                key={q}
                onClick={() => submit(q)}
                className="text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 px-3 py-1.5 rounded-full border border-blue-200 transition-colors"
              >
                {q.length > 60 ? q.slice(0, 60) + '…' : q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-gray-200 bg-white px-4 py-3">
        <form
          onSubmit={e => { e.preventDefault(); submit(input) }}
          className="flex gap-3 items-end"
        >
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(input) }
            }}
            placeholder="Ask in Hindi or English… e.g. 'Were there any riots in Meerut this year?'"
            rows={2}
            className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-5 py-2.5 rounded-xl font-medium text-sm transition-colors"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
