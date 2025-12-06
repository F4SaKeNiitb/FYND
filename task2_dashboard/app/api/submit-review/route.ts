import { NextRequest, NextResponse } from 'next/server'
import { writeFile, readFile, mkdir } from 'fs/promises'
import { existsSync } from 'fs'
import path from 'path'
import { GoogleGenerativeAI } from '@google/generative-ai'

const genAI = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY || '')
const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash-preview-05-20' })

const DATA_DIR = path.join(process.cwd(), 'data')
const DATA_FILE = path.join(DATA_DIR, 'reviews.json')

// Ensure data directory exists
async function ensureDataDir() {
  if (!existsSync(DATA_DIR)) {
    await mkdir(DATA_DIR, { recursive: true })
  }
}

// Read existing reviews
async function readReviews() {
  await ensureDataDir()
  
  if (!existsSync(DATA_FILE)) {
    await writeFile(DATA_FILE, JSON.stringify({ reviews: [] }, null, 2))
    return []
  }
  
  const data = await readFile(DATA_FILE, 'utf-8')
  const parsed = JSON.parse(data)
  return parsed.reviews || []
}

// Write reviews
async function writeReviews(reviews: any[]) {
  await ensureDataDir()
  await writeFile(DATA_FILE, JSON.stringify({ reviews }, null, 2))
}

// Generate AI response for user
async function generateUserResponse(rating: number, review: string): Promise<string> {
  const prompt = `You are a friendly customer service representative. A customer just left a ${rating}-star review with this feedback:

"${review}"

Respond with a brief, empathetic message (2-3 sentences) that:
- Thanks them for their feedback
- Acknowledges their experience appropriately based on the rating
- For positive reviews (4-5 stars): Express appreciation
- For neutral reviews (3 stars): Show willingness to improve
- For negative reviews (1-2 stars): Apologize and commit to doing better

Keep it warm, genuine, and concise.`

  try {
    const result = await model.generateContent({
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.7,
        maxOutputTokens: 150,
      },
    })

    return result.response.text() || 'Thank you for your feedback!'
  } catch (error) {
    console.error('Error generating user response:', error)
    return 'Thank you for your valuable feedback! We truly appreciate you taking the time to share your experience with us.'
  }
}

// Generate AI summary for admin
async function generateAdminSummary(rating: number, review: string): Promise<string> {
  const prompt = `Summarize this customer review in one concise sentence for internal admin use:

Rating: ${rating} stars
Review: "${review}"

Focus on the key points and sentiment.`

  try {
    const result = await model.generateContent({
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.5,
        maxOutputTokens: 100,
      },
    })

    return result.response.text() || 'Customer feedback received.'
  } catch (error) {
    console.error('Error generating summary:', error)
    return `${rating}-star review: ${review.substring(0, 100)}...`
  }
}

// Generate recommended actions
async function generateRecommendedActions(rating: number, review: string): Promise<string[]> {
  const prompt = `Based on this ${rating}-star review, suggest 2-3 specific, actionable steps the business should take:

"${review}"

Provide practical recommendations that address the feedback. Format as a simple list.`

  try {
    const result = await model.generateContent({
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.7,
        maxOutputTokens: 200,
      },
    })

    const content = result.response.text() || ''
    
    // Parse the response into an array
    const actions = content
      .split('\n')
      .filter(line => line.trim().length > 0)
      .map(line => line.replace(/^[-•*\d.)\s]+/, '').trim())
      .filter(line => line.length > 0)
      .slice(0, 3)

    return actions.length > 0 ? actions : ['Review customer feedback with team', 'Monitor similar issues', 'Follow up if necessary']
  } catch (error) {
    console.error('Error generating actions:', error)
    
    // Fallback actions based on rating
    if (rating >= 4) {
      return [
        'Continue delivering excellent service',
        'Share positive feedback with team',
        'Request customer testimonial if appropriate'
      ]
    } else if (rating === 3) {
      return [
        'Identify areas for improvement mentioned in review',
        'Discuss with team how to enhance experience',
        'Monitor for similar patterns'
      ]
    } else {
      return [
        'Immediate follow-up with customer to address concerns',
        'Review processes to prevent similar issues',
        'Schedule team training if needed'
      ]
    }
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { rating, review, timestamp } = body

    if (!rating || !review || !timestamp) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    // Validate rating
    if (rating < 1 || rating > 5) {
      return NextResponse.json(
        { error: 'Rating must be between 1 and 5' },
        { status: 400 }
      )
    }

    // Generate AI responses in parallel for efficiency
    const [userResponse, adminSummary, recommendedActions] = await Promise.all([
      generateUserResponse(rating, review),
      generateAdminSummary(rating, review),
      generateRecommendedActions(rating, review),
    ])

    // Create review object
    const newReview = {
      id: `review_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      rating,
      review,
      timestamp,
      aiResponse: userResponse,
      aiSummary: adminSummary,
      recommendedActions,
    }

    // Save to file
    const reviews = await readReviews()
    reviews.push(newReview)
    await writeReviews(reviews)

    return NextResponse.json({
      success: true,
      aiResponse: userResponse,
      reviewId: newReview.id,
    })
  } catch (error) {
    console.error('Error processing review:', error)
    return NextResponse.json(
      { error: 'Failed to process review' },
      { status: 500 }
    )
  }
}
