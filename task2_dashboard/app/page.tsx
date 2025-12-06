'use client'

import { useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { API_ENDPOINTS } from '@/lib/api-config'

export default function Home() {
  const [rating, setRating] = useState(0)
  const [hoveredRating, setHoveredRating] = useState(0)
  const [review, setReview] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<any>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        alert('Image too large. Maximum size is 5MB.')
        return
      }
      setPhoto(file)
      setPhotoPreview(URL.createObjectURL(file))
    }
  }

  const removePhoto = () => {
    setPhoto(null)
    setPhotoPreview(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (rating === 0 || review.trim() === '') {
      alert('Please provide both a rating and a review')
      return
    }

    setLoading(true)
    setResponse(null)

    try {
      const formData = new FormData()
      formData.append('rating', rating.toString())
      formData.append('review', review)
      formData.append('timestamp', new Date().toISOString())
      if (photo) {
        formData.append('photo', photo)
      }

      const res = await fetch(API_ENDPOINTS.submitReview, {
        method: 'POST',
        body: formData,
      })

      const data = await res.json()
      
      if (res.ok) {
        setResponse(data)
        setTimeout(() => {
          setRating(0)
          setReview('')
          setPhoto(null)
          setPhotoPreview(null)
          setResponse(null)
        }, 5000)
      } else if (res.status === 429) {
        alert('Too many requests. Please wait a moment and try again.')
      } else {
        alert('Error submitting review: ' + (data.detail || data.error))
      }
    } catch (error) {
      alert('Error submitting review. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Navigation */}
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-gray-900">⭐ Yelp Feedback</h1>
            </div>
            <button
              onClick={() => router.push('/admin')}
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Admin Dashboard →
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center mb-8">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Share Your Experience
          </h2>
          <p className="text-lg text-gray-600">
            Your feedback helps us improve. Tell us about your visit!
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Star Rating */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                How would you rate your experience?
              </label>
              <div className="flex gap-2 justify-center">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    onMouseEnter={() => setHoveredRating(star)}
                    onMouseLeave={() => setHoveredRating(0)}
                    className="transition-transform hover:scale-110"
                  >
                    <svg
                      className={`w-12 h-12 ${
                        star <= (hoveredRating || rating)
                          ? 'text-yellow-400 fill-current'
                          : 'text-gray-300'
                      }`}
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth="1"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"
                      />
                    </svg>
                  </button>
                ))}
              </div>
              {rating > 0 && (
                <p className="text-center mt-2 text-sm text-gray-600">
                  You selected {rating} {rating === 1 ? 'star' : 'stars'}
                </p>
              )}
            </div>

            {/* Review Text */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Tell us more about your experience
              </label>
              <textarea
                value={review}
                onChange={(e) => setReview(e.target.value)}
                rows={6}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none text-black"
                placeholder="What did you love? What could we improve? Your detailed feedback helps us serve you better..."
                required
              />
              <p className="text-sm text-gray-500 mt-1">
                {review.length} characters
              </p>
            </div>

            {/* Photo Upload */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Add a photo (optional)
              </label>
              <div className="flex items-center gap-4">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoChange}
                  className="hidden"
                  id="photo-upload"
                />
                <label
                  htmlFor="photo-upload"
                  className="cursor-pointer inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
                >
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  Choose Photo
                </label>
                {photoPreview && (
                  <div className="relative">
                    <img
                      src={photoPreview}
                      alt="Preview"
                      className="w-20 h-20 object-cover rounded-lg"
                    />
                    <button
                      type="button"
                      onClick={removePhoto}
                      className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm hover:bg-red-600"
                    >
                      ×
                    </button>
                  </div>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-1">Max 5MB. JPG, PNG, GIF, WebP</p>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || rating === 0 || review.trim() === ''}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold py-4 rounded-lg hover:from-blue-700 hover:to-purple-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin h-5 w-5 mr-3" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Processing...
                </span>
              ) : (
                'Submit Feedback'
              )}
            </button>
          </form>

          {/* AI Response */}
          {response && (
            <div className="mt-8 p-6 bg-gradient-to-r from-green-50 to-blue-50 rounded-lg border-2 border-green-200 animate-fade-in">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    Thank You for Your Feedback!
                  </h3>
                  <p className="text-gray-700 leading-relaxed">
                    {response.aiResponse}
                  </p>
                  {response.rateLimitRemaining !== undefined && (
                    <p className="text-xs text-gray-500 mt-2">
                      Submissions remaining this minute: {response.rateLimitRemaining}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Info Card */}
        <div className="mt-8 bg-white rounded-lg shadow-md p-6 border-l-4 border-blue-500">
          <h3 className="font-semibold text-gray-900 mb-2">Why your feedback matters</h3>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>✓ Helps us understand your experience</li>
            <li>✓ Enables us to make improvements</li>
            <li>✓ Gets reviewed by our team within 24 hours</li>
            <li>✓ Powered by AI for instant acknowledgment</li>
          </ul>
        </div>
      </main>
    </div>
  )
}
