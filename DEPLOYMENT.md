# Deployment Guide - Task 2: Dashboard System

## Architecture Overview

This application has **two separate components** that need to be deployed:

| Component | Technology | Default Port | Purpose |
|-----------|------------|--------------|---------|
| **Backend** | FastAPI (Python) | 8000 | API server, AI processing, data storage |
| **Frontend** | Next.js (React) | 3000 | User interface, dashboards |

---

## Local Development

### Prerequisites
- Python 3.8+
- Node.js 18+
- Google API Key from https://aistudio.google.com/app/apikey

### Step 1: Start Backend (Terminal 1)
```bash
cd task2_dashboard/backend

# Create and activate virtual environment (first time only)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Create .env file with your API key
echo "GOOGLE_API_KEY=your-api-key-here" > .env

# Start the server
python -m uvicorn main:app --reload --port 8000
```

### Step 2: Start Frontend (Terminal 2)
```bash
cd task2_dashboard

# Install dependencies (first time only)
npm install

# Start the dev server
npm run dev
```

### Step 3: Access the Application
- **User Dashboard**: http://localhost:3000
- **Admin Dashboard**: http://localhost:3000/admin
- **API Health Check**: http://localhost:8000

---

## Production Deployment Options

### Option 1: Render (Recommended for Full-Stack)

Deploy both backend and frontend on Render's free tier.

#### Deploy Backend (FastAPI)

1. Go to https://render.com -> New -> Web Service
2. Connect your GitHub repository
3. Configure:
   - **Name**: `yelp-feedback-api`
   - **Root Directory**: `task2_dashboard/backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add Environment Variable:
   - `GOOGLE_API_KEY` = `your-api-key`
5. Deploy!
6. Note your backend URL: `https://yelp-feedback-api.onrender.com`

#### Deploy Frontend (Next.js)

1. Update `task2_dashboard/lib/api-config.ts`:
```typescript
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://yelp-feedback-api.onrender.com';
```

2. Go to Render -> New -> Web Service
3. Configure:
   - **Name**: `yelp-feedback-frontend`
   - **Root Directory**: `task2_dashboard`
   - **Runtime**: Node
   - **Build Command**: `npm install && npm run build`
   - **Start Command**: `npm start`
4. Add Environment Variable:
   - `NEXT_PUBLIC_API_URL` = `https://yelp-feedback-api.onrender.com`
5. Deploy!

#### Access Your App
- Frontend: `https://yelp-feedback-frontend.onrender.com`
- Admin: `https://yelp-feedback-frontend.onrender.com/admin`

---

### Option 2: Railway

#### Deploy Backend
```bash
cd task2_dashboard/backend
railway login
railway init
railway variables set GOOGLE_API_KEY=your-api-key
railway up
```
Note the backend URL.

#### Deploy Frontend
```bash
cd task2_dashboard
railway init
railway variables set NEXT_PUBLIC_API_URL=https://your-backend.railway.app
railway up
```

---

### Option 3: Vercel (Frontend) + Render (Backend)

Best for Next.js frontend with separate Python backend.

#### Backend on Render
Follow "Deploy Backend" steps from Option 1.

#### Frontend on Vercel
```bash
cd task2_dashboard
npm i -g vercel
vercel login
vercel
```

Configure in Vercel Dashboard:
- Environment Variable: `NEXT_PUBLIC_API_URL` = `https://your-backend.onrender.com`

---

### Option 4: Self-Hosted (VPS)

For full control on AWS EC2, DigitalOcean, etc.

#### Setup Server (Ubuntu 22.04)
```bash
# Install Python
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install PM2
sudo npm install -g pm2
```

#### Deploy Backend
```bash
cd task2_dashboard/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env
echo "GOOGLE_API_KEY=your-api-key" > .env

# Start with PM2
pm2 start "uvicorn main:app --host 0.0.0.0 --port 8000" --name api
pm2 save
```

#### Deploy Frontend
```bash
cd task2_dashboard
npm install
npm run build

# Update API URL in .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Start with PM2
pm2 start npm --name frontend -- start
pm2 save
```

#### Setup Nginx
```bash
sudo apt install nginx
sudo nano /etc/nginx/sites-available/yelp-feedback
```

Add:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/yelp-feedback /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### SSL (Optional)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

### Option 5: Docker Deployment

#### Create `docker-compose.yml` in project root:
```yaml
version: '3.8'

services:
  backend:
    build: ./task2_dashboard/backend
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
    volumes:
      - backend-data:/app/data

  frontend:
    build: ./task2_dashboard
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend

volumes:
  backend-data:
```

#### Create `task2_dashboard/backend/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Create `task2_dashboard/Dockerfile`:
```dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
```

#### Deploy:
```bash
GOOGLE_API_KEY=your-api-key docker-compose up -d
```

---

## Environment Variables

### Backend (`task2_dashboard/backend/.env`)
```bash
GOOGLE_API_KEY=your-google-api-key-here
```

### Frontend (`task2_dashboard/.env.local`)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000  # or your deployed backend URL
```

---

## Data Storage

Reviews are stored in:
```
task2_dashboard/backend/data/reviews.json
```

For production, consider upgrading to:
- PostgreSQL
- MongoDB
- Cloud storage (S3, Cloudflare R2)

---

## Testing Deployment

```bash
# Test Backend Health
curl https://your-backend-url.com/

# Test Submit Review
curl -X POST https://your-backend-url.com/api/submit-review \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "review": "Great service!",
    "timestamp": "2025-12-06T10:00:00.000Z"
  }'

# Test Get Reviews
curl https://your-backend-url.com/api/get-reviews

# Test Analytics
curl https://your-backend-url.com/api/analytics
```

---

## Post-Deployment Checklist

- [ ] Backend health check responds
- [ ] Frontend loads at root URL
- [ ] Admin dashboard loads at `/admin`
- [ ] Can submit a review
- [ ] AI response appears after submission
- [ ] Reviews appear in admin dashboard
- [ ] Analytics charts display correctly
- [ ] Delete review works (admin)

---

## Troubleshooting

### CORS Errors
Update `task2_dashboard/backend/main.py` to include your frontend domain:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://your-frontend-domain.com"
    ],
    ...
)
```

### Backend Not Responding
```bash
# Check if running
curl http://localhost:8000/

# Check logs
pm2 logs api  # if using PM2
```

### Frontend Can't Connect to Backend
- Verify `NEXT_PUBLIC_API_URL` is set correctly
- Check CORS settings include your frontend domain
- Ensure backend is running and accessible

### Data Not Persisting
- Check `backend/data/` directory exists and is writable
- For Docker: ensure volume is mounted correctly

---

## Cost Estimates

| Platform | Backend | Frontend | Total |
|----------|---------|----------|-------|
| Render | Free | Free | **Free** |
| Railway | ~$5/mo | ~$5/mo | ~$10/mo |
| Vercel + Render | Free (Render) | Free (Vercel) | **Free** |
| DigitalOcean | $5/mo | $5/mo | $10/mo |
| Self-Hosted VPS | Combined | Combined | $5-10/mo |

**Additional**: Google Gemini API - Free tier is generous (~1500 requests/day)

---

## Quick Start Summary

```bash
# Clone and setup
git clone <your-repo>
cd FYND

# Terminal 1 - Backend
cd task2_dashboard/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
echo "GOOGLE_API_KEY=your-key" > .env
uvicorn main:app --reload --port 8000

# Terminal 2 - Frontend
cd task2_dashboard
npm install
npm run dev

# Open http://localhost:3000
```

---

**Deploy and enjoy!**
