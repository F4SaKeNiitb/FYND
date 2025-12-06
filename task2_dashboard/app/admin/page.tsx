'use client'

import { useState, useEffect, useCallback } from 'react'
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
  AreaChart,
  Area,
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
  photo_url?: string
  flagged?: boolean
  admin_reply?: string
  sentiment?: string
}

interface WordCloudItem {
  word: string
  count: number
}

interface SentimentTrendItem {
  period: string
  positive: number
  neutral: number
  negative: number
  average: number
}

interface ComparisonData {
  this_week: { total: number; average_rating: number; positive: number; negative: number }
  last_week: { total: number; average_rating: number; positive: number; negative: number }
  change: { total: string; average_rating: string; positive: string; negative: string }
}

export default function AdminDashboard() {
  const [reviews, setReviews] = useState<Review[]>([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [ratingFilter, setRatingFilter] = useState<number | null>(null)
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [wordCloud, setWordCloud] = useState<WordCloudItem[]>([])
  const [sentimentTrends, setSentimentTrends] = useState<SentimentTrendItem[]>([])
  const [comparison, setComparison] = useState<ComparisonData | null>(null)
  const [activeTab, setActiveTab] = useState<'reviews' | 'analytics' | 'trends'>('reviews')
  const [replyModalOpen, setReplyModalOpen] = useState(false)
  const [selectedReview, setSelectedReview] = useState<Review | null>(null)
  const [replyText, setReplyText] = useState('')
  const router = useRouter()

  const fetchReviews = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (searchQuery) params.append('search', searchQuery)
      if (dateFrom) params.append('date_from', dateFrom)
      if (dateTo) params.append('date_to', dateTo)
      if (ratingFilter) params.append('rating', ratingFilter.toString())
      if (flaggedOnly) params.append('flagged_only', 'true')
      
      const url = `${API_ENDPOINTS.getReviews}?${params.toString()}`
      const res = await fetch(url)
      const data = await res.json()
      setReviews(data.reviews || [])
    } catch (error) {
      console.error('Error fetching reviews:', error)
    } finally {
      setLoading(false)
    }
  }, [searchQuery, dateFrom, dateTo, ratingFilter, flaggedOnly])

  const fetchAnalytics = async () => {
    try {
      const [wcRes, trendRes, compRes] = await Promise.all([
        fetch(API_ENDPOINTS.wordCloud),
        fetch(`${API_ENDPOINTS.sentimentTrends}?period=daily`),
        fetch(API_ENDPOINTS.comparison),
      ])
      
      const wcData = await wcRes.json()
      const trendData = await trendRes.json()
      const compData = await compRes.json()
      
      setWordCloud(wcData.words || [])
      setSentimentTrends(trendData.trends || [])
      setComparison(compData)
    } catch (error) {
      console.error('Error fetching analytics:', error)
    }
  }

  useEffect(() => {
    fetchReviews()
    fetchAnalytics()
  }, [fetchReviews])

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchReviews()
        fetchAnalytics()
      }, 30000)
      return () => clearInterval(interval)
    }
  }, [autoRefresh, fetchReviews])

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      const res = await fetch(`${API_ENDPOINTS.export}?format=${format}`)
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `reviews.${format}`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      alert('Error exporting data')
    }
  }

  const handleFlag = async (reviewId: string, flag: boolean) => {
    try {
      await fetch(API_ENDPOINTS.flagReview(reviewId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ flagged: flag }),
      })
      fetchReviews()
    } catch (error) {
      alert('Error updating flag')
    }
  }

  const handleReply = async () => {
    if (!selectedReview || !replyText.trim()) return
    try {
      await fetch(API_ENDPOINTS.replyReview(selectedReview.id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reply: replyText }),
      })
      setReplyModalOpen(false)
      setReplyText('')
      setSelectedReview(null)
      fetchReviews()
    } catch (error) {
      alert('Error sending reply')
    }
  }

  const handleDelete = async (reviewId: string) => {
    if (!confirm('Are you sure you want to delete this review?')) return
    try {
      await fetch(API_ENDPOINTS.deleteReview(reviewId), { method: 'DELETE' })
      fetchReviews()
    } catch (error) {
      alert('Error deleting review')
    }
  }

  // Analytics calculations
  const averageRating = reviews.length > 0
    ? (reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length).toFixed(1)
    : '0'

  const ratingDistribution = [1, 2, 3, 4, 5].map(star => ({
    rating: `${star}★`,
    count: reviews.filter(r => r.rating === star).length,
  }))

  const sentimentBreakdown = [
    { name: 'Positive (4-5★)', value: reviews.filter(r => r.rating >= 4).length, color: '#22c55e' },
    { name: 'Neutral (3★)', value: reviews.filter(r => r.rating === 3).length, color: '#eab308' },
    { name: 'Negative (1-2★)', value: reviews.filter(r => r.rating <= 2).length, color: '#ef4444' },
  ].filter(item => item.value > 0)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Reply Modal */}
      {replyModalOpen && selectedReview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg mx-4">
            <h3 className="text-lg font-semibold mb-4">Reply to Review</h3>
            <p className="text-sm text-gray-600 mb-4">"{selectedReview.review.substring(0, 100)}..."</p>
            <textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              className="w-full border rounded-lg p-3 text-black"
              rows={4}
              placeholder="Type your reply..."
            />
            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => { setReplyModalOpen(false); setReplyText(''); }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleReply}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Send Reply
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <nav className="bg-white shadow-sm border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
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
              <button onClick={() => handleExport('csv')} className="text-sm text-gray-600 hover:text-gray-900">
                Export CSV
              </button>
              <button onClick={() => handleExport('json')} className="text-sm text-gray-600 hover:text-gray-900">
                Export JSON
              </button>
              <button onClick={() => { fetchReviews(); fetchAnalytics(); }} className="text-sm text-gray-600 hover:text-gray-900">
                Refresh Data
              </button>
              <button onClick={() => router.push('/')} className="text-sm text-blue-600 hover:text-blue-800">
                ← User Dashboard
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Tabs */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex gap-6">
            {['reviews', 'analytics', 'trends'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as any)}
                className={`py-4 px-2 font-medium text-sm border-b-2 transition-colors ${
                  activeTab === tab
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

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
                    <span className="text-sm font-semibold text-blue-700">REV</span>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-md p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Average Rating</p>
                    <p className="text-3xl font-bold text-gray-900">{averageRating} / 5</p>
                  </div>
                  <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center">
                    <span className="text-sm font-semibold text-yellow-700">AVG</span>
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
                    <span className="text-sm font-semibold text-green-700">POS</span>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-md p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Flagged</p>
                    <p className="text-3xl font-bold text-red-600">
                      {reviews.filter(r => r.flagged).length}
                    </p>
                  </div>
                  <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                    <span className="text-sm font-semibold text-red-700">FLAG</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Comparison Banner */}
            {comparison && (
              <div className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg shadow-md p-6 mb-8 text-white">
                <h3 className="text-lg font-semibold mb-4">This Week vs Last Week</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-sm opacity-80">Total Reviews</p>
                    <p className="text-2xl font-bold">{comparison.this_week.total}</p>
                    <p className={`text-sm ${comparison.change.total.startsWith('+') ? 'text-green-300' : 'text-red-300'}`}>
                      {comparison.change.total} from last week
                    </p>
                  </div>
                  <div>
                    <p className="text-sm opacity-80">Avg Rating</p>
                    <p className="text-2xl font-bold">{comparison.this_week.average_rating.toFixed(1)}</p>
                    <p className={`text-sm ${comparison.change.average_rating.startsWith('+') ? 'text-green-300' : 'text-red-300'}`}>
                      {comparison.change.average_rating}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm opacity-80">Positive</p>
                    <p className="text-2xl font-bold">{comparison.this_week.positive}</p>
                    <p className={`text-sm ${comparison.change.positive.startsWith('+') ? 'text-green-300' : 'text-red-300'}`}>
                      {comparison.change.positive}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm opacity-80">Negative</p>
                    <p className="text-2xl font-bold">{comparison.this_week.negative}</p>
                    <p className={`text-sm ${comparison.change.negative.startsWith('-') ? 'text-green-300' : 'text-red-300'}`}>
                      {comparison.change.negative}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'reviews' && (
              <>
                {/* Filters */}
                <div className="bg-white rounded-lg shadow-md p-4 mb-6">
                  <div className="flex flex-wrap gap-4 items-end">
                    <div className="flex-1 min-w-[200px]">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Search</label>
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search reviews..."
                        className="w-full border rounded-lg px-3 py-2 text-black"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">From</label>
                      <input
                        type="date"
                        value={dateFrom}
                        onChange={(e) => setDateFrom(e.target.value)}
                        className="border rounded-lg px-3 py-2 text-black"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">To</label>
                      <input
                        type="date"
                        value={dateTo}
                        onChange={(e) => setDateTo(e.target.value)}
                        className="border rounded-lg px-3 py-2 text-black"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Rating</label>
                      <select
                        value={ratingFilter || ''}
                        onChange={(e) => setRatingFilter(e.target.value ? parseInt(e.target.value) : null)}
                        className="border rounded-lg px-3 py-2 text-black"
                      >
                        <option value="">All</option>
                        {[1, 2, 3, 4, 5].map(r => (
                          <option key={r} value={r}>{r} Star</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="flaggedOnly"
                        checked={flaggedOnly}
                        onChange={(e) => setFlaggedOnly(e.target.checked)}
                        className="rounded"
                      />
                      <label htmlFor="flaggedOnly" className="text-sm text-gray-700">Flagged only</label>
                    </div>
                    <button
                      onClick={() => { setSearchQuery(''); setDateFrom(''); setDateTo(''); setRatingFilter(null); setFlaggedOnly(false); }}
                      className="text-sm text-gray-600 hover:text-gray-900"
                    >
                      Clear filters
                    </button>
                  </div>
                </div>

                {/* Reviews List */}
                <div className="bg-white rounded-lg shadow-md">
                  <div className="px-6 py-4 border-b border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-900">All Reviews ({reviews.length})</h3>
                  </div>
                  <div className="divide-y divide-gray-200">
                    {reviews.length === 0 ? (
                      <div className="p-12 text-center text-gray-500">
                        <p className="text-lg">No reviews found</p>
                        <p className="text-sm mt-2">Try adjusting your filters</p>
                      </div>
                    ) : (
                      reviews.slice().reverse().map((review) => (
                        <div key={review.id} className={`p-6 hover:bg-gray-50 transition-colors ${review.flagged ? 'bg-red-50' : ''}`}>
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex items-center gap-3">
                              <div className="flex">
                                {[1, 2, 3, 4, 5].map((star) => (
                                  <svg
                                    key={star}
                                    className={`w-5 h-5 ${star <= review.rating ? 'text-yellow-400 fill-current' : 'text-gray-300'}`}
                                    xmlns="http://www.w3.org/2000/svg"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                  >
                                    <path d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
                                  </svg>
                                ))}
                              </div>
                              <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                review.rating >= 4 ? 'bg-green-100 text-green-800' :
                                review.rating === 3 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'
                              }`}>
                                {review.rating >= 4 ? 'Positive' : review.rating === 3 ? 'Neutral' : 'Needs Attention'}
                              </span>
                              {review.flagged && (
                                <span className="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">
                                  Flagged
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="text-sm text-gray-500">
                                {new Date(review.timestamp).toLocaleString()}
                              </span>
                              <button
                                onClick={() => handleFlag(review.id, !review.flagged)}
                                className={`text-sm px-2 py-1 rounded ${review.flagged ? 'text-gray-600 hover:bg-gray-100' : 'text-red-600 hover:bg-red-50'}`}
                              >
                                {review.flagged ? 'Unflag' : 'Flag'}
                              </button>
                              <button
                                onClick={() => { setSelectedReview(review); setReplyText(review.admin_reply || ''); setReplyModalOpen(true); }}
                                className="text-sm text-blue-600 hover:bg-blue-50 px-2 py-1 rounded"
                              >
                                Reply
                              </button>
                              <button
                                onClick={() => handleDelete(review.id)}
                                className="text-sm text-red-600 hover:bg-red-50 px-2 py-1 rounded"
                              >
                                Delete
                              </button>
                            </div>
                          </div>

                          <div className="space-y-4">
                            <div className="flex gap-4">
                              {review.photo_url && (
                                <img src={review.photo_url} alt="Review photo" className="w-24 h-24 object-cover rounded-lg" />
                              )}
                              <div className="flex-1">
                                <p className="text-sm font-medium text-gray-700 mb-1">User Review:</p>
                                <p className="text-gray-900">{review.review}</p>
                              </div>
                            </div>

                            {review.admin_reply && (
                              <div className="bg-green-50 rounded-lg p-4">
                                <p className="text-sm font-medium text-green-900 mb-1">Admin Reply:</p>
                                <p className="text-green-800">{review.admin_reply}</p>
                              </div>
                            )}

                            <div className="bg-blue-50 rounded-lg p-4">
                              <p className="text-sm font-medium text-blue-900 mb-1">AI Summary:</p>
                              <p className="text-blue-800">{review.aiSummary}</p>
                            </div>

                            <div className="bg-purple-50 rounded-lg p-4">
                              <p className="text-sm font-medium text-purple-900 mb-2">Recommended Actions:</p>
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

            {activeTab === 'analytics' && (
              <div className="space-y-6">
                {/* Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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

                {/* Word Cloud */}
                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Keywords</h3>
                  <div className="flex flex-wrap gap-2">
                    {wordCloud.slice(0, 30).map((item, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                        style={{ fontSize: `${Math.max(12, Math.min(24, 12 + item.count * 2))}px` }}
                      >
                        {item.word} ({item.count})
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'trends' && (
              <div className="space-y-6">
                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Sentiment Trends Over Time</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={sentimentTrends}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="period" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Area type="monotone" dataKey="positive" stackId="1" stroke="#22c55e" fill="#22c55e" name="Positive" />
                      <Area type="monotone" dataKey="neutral" stackId="1" stroke="#eab308" fill="#eab308" name="Neutral" />
                      <Area type="monotone" dataKey="negative" stackId="1" stroke="#ef4444" fill="#ef4444" name="Negative" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Average Rating Trend</h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={sentimentTrends}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="period" />
                      <YAxis domain={[0, 5]} />
                      <Tooltip />
                      <Line type="monotone" dataKey="average" stroke="#8b5cf6" strokeWidth={2} name="Avg Rating" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
