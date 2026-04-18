# 💰 Piggypie: Modern AI-Powered Expense Manager

Piggypie is a high-fidelity, Flask-based financial management application designed to help you track spending, automate recurring transactions, and gain personalized insights with an embedded AI Financial Coach.

<img width="1919" height="859" alt="image" src="https://github.com/user-attachments/assets/88791a10-cead-4df0-9ce4-b7297034816a" />


## ✨ Premium Features

### 🤖 AI Financial Coach
- **Data-Aware Analysis**: Our coach analyzes your real SQLite transaction history to give personalized, actionable advice.
- **Powered by Claude**: Deep financial insights provided by `claude-sonnet-4-20250514`.
- **Suggestion Chips**: Get quick answers to questions like *"Am I saving enough?"* or *"Where am I overspending?"*

### 🎨 High-Fidelity Landing Page & Unified UI
- **Premium Intro**: A standalone animated entrance at `/` featuring falling gold ₹ coins and a bouncy leather wallet animation.
- **"Green Vibes" Theme**: A consistent dark-green aesthetic across the entire app (Landing → Sign Up → Login → Dashboard).
- **Glassmorphism Design**: Modern, transparent UI elements with neon green accents.

### 📊 Smart Dashboard
- **Instant Overview**: Live tracking of your Total Income, Expenses, and Current Balance.
- **Visual Analytics**: Interactive Pie and Bar charts powered by Chart.js for intuitive category breakdowns.
- **Budget Tracking**: Set monthly spending limits and monitor your progress in real-time.

### 🔄 Automation & Recurring Transactions
- **Set & Forget**: Automate weekly, monthly, or yearly transactions (subscriptions, rent, salary).
- **Auto-Processing**: System automatically generates entries on due dates.
- **Status Control**: Easily toggle active/inactive status for any recurring transaction.

### 📧 Intelligent Notifications
- **Weekly Summaries**: Receive automated email reports every Monday with your financial performance.
- **Budget Alerts**: Get notified when you approach or exceed your spending thresholds.
- **Personalized Tips**: Practical, data-driven financial advice generated based on your spending habits.

### 💼 Professional Data Management
- **Filtered History**: Search and filter transactions by date, category, or type.
- **CSV Export**: Download your entire transaction history for external analysis in Excel or other tools.
- **Secure Auth**: Robust user registration and login system with SHA-256 password hashing.

## 🛠️ Technology Stack
- **Backend**: Python / Flask
- **AI Integration**: Claude API (via `claude-sonnet-4-20250514`)
- **Database**: SQLite
- **Frontend**: HTML5, Vanilla CSS3 (Custom Design System), JavaScript (ES6+), Bootstrap 5 (Dashboard only)
- **Visuals**: Canvas API (Falling Coins), SVG Animations
- **Charts**: Chart.js
- **Emails**: SMTP

## 🚀 Quick Start

1. **Install Dependencies**:
   ```bash
   pip install flask
   ```

2. **Run the Application**:
   ```bash
   python app.py
   ```
   Visit `http://localhost:5000` to see the high-fidelity landing page.

## 🚀 Deployment (Vercel)

This app is ready to be deployed to **Vercel** with a persistent **PostgreSQL** database.

### 1. Create a Database
1. Go to your [Vercel Dashboard](https://vercel.com/dashboard).
2. Create a new **Postgres** storage.
3. Once created, go to the **Settings > Environment Variables** of your project and ensure `POSTGRES_URL` (or `DATABASE_URL`) is present.

### 2. Set Environment Variables
In your Vercel Project Settings, add these variables:
- `SECRET_KEY`: A long random string to secure your sessions.
- `DATABASE_URL`: Your Vercel Postgres connection string (usually handled automatically by Vercel if you use their Postgres).

### 3. Deploy
1. Push your code to a GitHub repository.
2. Connect the repository to Vercel.
3. Vercel will detect the `vercel.json` and `requirements.txt` and deploy automatically!

---
*Built with ❤️ for better financial clarity.*
