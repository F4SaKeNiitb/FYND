'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
} from 'recharts'
import { API_ENDPOINTS } from '@/lib/api-config'

interface Review {
  id: string
  rating: number
  review: string
  timestamp: string
  aiResponse: string
  aiSummary: string
  recommendedActions: string[]
}

export default function AdminDashboard() {
  const [reviews, setReviews] = useState<Review[]>([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const router = useRouter()

  const fetchReviews = async () => {
    try {
      const res = await fetch(API_ENDPOINTS.getReviews)
      const data = await res.json()
      setReviews(data.reviews || [])
    } catch (error) {
      console.error('Error fetching reviews:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchReviews()
  }, [])

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchReviews, 10000) // Refresh every 10 seconds
      return () => clearInterval(interval)
    }
  }, [autoRefresh])

  // Analytics calculations
  const averageRating = reviews.length > 0
    ? (reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length).toFixed(1)
    : '0'

  const ratingDistribution = [1, 2, 3, 4, 5].map(star => ({
    rating: `${star} ⭐`,
    count: reviews.filter(r => r.rating === star).length,
  }))

  const COLORS = ['#ef4444', '#f97316', '#eab308', '#84cc16', '#22c55e']

  const recentTrend = reviews
    .slice(-10)
    .reverse()
    .map((r, idx) => ({
      index: reviews.length - 10 + idx + 1,
      rating: r.rating,
    }))

  const sentimentBreakdown = [
    { name: 'Positive (4-5★)', value: reviews.filter(r => r.rating >= 4).length, color: '#22c55e' },
    { name: 'Neutral (3★)', value: reviews.filter(r => r.rating === 3).length, color: '#eab308' },
    { name: 'Negative (1-2★)', value: reviews.filter(r => r.rating <= 2).length, color: '#ef4444' },
  ].filter(item => item.value > 0)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <nav className="bg-white shadow-sm border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <h1 className="text-2xl font-bold text-gray-900">📊 Admin Dashboard</h1>
              <div className="flex items-center gap-2 text-sm">
                <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">
                  Live
                </span>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoRefresh}
                    onChange={(e) => setAutoRefresh(e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-gray-600">Auto-refresh</span>
                </label>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={fetchReviews}
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                🔄 Refresh
              </button>
              <button
                onClick={() => router.push('/')}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                ← User Dashboard
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading reviews...</p>
            </div>
          </div>
        ) : (
          <>
            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <div className="bg-white rounded-lg shadow-md p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Total Reviews</p>
                    <p className="text-3xl font-bold text-gray-900">{reviews.length}</p>
                  </div>
                  <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                    <span className="text-2xl">📝</span>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-md p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Average Rating</p>
                    <p className="text-3xl font-bold text-gray-900">{averageRating} ⭐</p>
                  </div>
                  <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center">
                    <span className="text-2xl">⭐</span>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-md p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Positive Reviews</p>
                    <p className="text-3xl font-bold text-green-600">
                      {reviews.filter(r => r.rating >= 4).length}
                    </p>
                  </div>
                  <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
                    <span className="text-2xl">😊</span>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-md p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Needs Attention</p>
                    <p className="text-3xl font-bold text-red-600">
                      {reviews.filter(r => r.rating <= 2).length}
                    </p>
                  </div>
                  <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                    <span className="text-2xl">⚠️</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              {/* Rating Distribution */}
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Rating Distribution</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={ratingDistribution}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="rating" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Sentiment Breakdown */}
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Sentiment Breakdown</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={sentimentBreakdown}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {sentimentBreakdown.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Recent Trend */}
            {reviews.length >= 5 && (
              <div className="bg-white rounded-lg shadow-md p-6 mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Rating Trend</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={recentTrend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="index" label={{ value: 'Review #', position: 'insideBottom', offset: -5 }} />
                    <YAxis domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} />
                    <Tooltip />
                    <Line type="monotone" dataKey="rating" stroke="#8b5cf6" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Reviews List */}
            <div className="bg-white rounded-lg shadow-md">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">All Reviews</h3>
              </div>
              <div className="divide-y divide-gray-200">
                {reviews.length === 0 ? (
                  <div className="p-12 text-center text-gray-500">
                    <p className="text-lg">No reviews yet</p>
                    <p className="text-sm mt-2">Reviews will appear here as they are submitted</p>
                  </div>
                ) : (
                  reviews
                    .slice()
                    .reverse()
                    .map((review) => (
                      <div key={review.id} className="p-6 hover:bg-gray-50 transition-colors">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <div className="flex">
                              {[1, 2, 3, 4, 5].map((star) => (
                                <svg
                                  key={star}
                                  className={`w-5 h-5 ${
                                    star <= review.rating ? 'text-yellow-400 fill-current' : 'text-gray-300'
                                  }`}
                                  xmlns="http://www.w3.org/2000/svg"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                >
                                  <path d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
                                </svg>
                              ))}
                            </div>
                            <span
                              className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                review.rating >= 4
                                  ? 'bg-green-100 text-green-800'
                                  : review.rating === 3
                                  ? 'bg-yellow-100 text-yellow-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              {review.rating >= 4 ? 'Positive' : review.rating === 3 ? 'Neutral' : 'Needs Attention'}
                            </span>
                          </div>
                          <span className="text-sm text-gray-500">
                            {new Date(review.timestamp).toLocaleString()}
                          </span>
                        </div>

                        <div className="space-y-4">
                          <div>
                            <p className="text-sm font-medium text-gray-700 mb-1">User Review:</p>
                            <p className="text-gray-900">{review.review}</p>
                          </div>

                          <div className="bg-blue-50 rounded-lg p-4">
                            <p className="text-sm font-medium text-blue-900 mb-1">📊 AI Summary:</p>
                            <p className="text-blue-800">{review.aiSummary}</p>
                          </div>

                          <div className="bg-purple-50 rounded-lg p-4">
                            <p className="text-sm font-medium text-purple-900 mb-2">💡 Recommended Actions:</p>
                            <ul className="space-y-1">
                              {review.recommendedActions.map((action, idx) => (
                                <li key={idx} className="text-purple-800 text-sm flex items-start gap-2">
                                  <span className="text-purple-600 mt-0.5">•</span>
                                  <span>{action}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    ))
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
