import { NextResponse } from 'next/server'
import { readFile } from 'fs/promises'
import { existsSync } from 'fs'
import path from 'path'

const DATA_FILE = path.join(process.cwd(), 'data', 'reviews.json')

export async function GET() {
  try {
    if (!existsSync(DATA_FILE)) {
      return NextResponse.json({ reviews: [] })
    }

    const data = await readFile(DATA_FILE, 'utf-8')
    const parsed = JSON.parse(data)
    
    return NextResponse.json({ reviews: parsed.reviews || [] })
  } catch (error) {
    console.error('Error reading reviews:', error)
    return NextResponse.json({ reviews: [] })
  }
}

// Enable dynamic rendering to avoid static generation
export const dynamic = 'force-dynamic'
