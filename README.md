# 💰 Piggypie: Modern Expense Manager

Piggypie is a powerful, Flask-based financial management application designed to help you track spending, automate recurring transactions, and gain deep insights into your financial health with beautiful visualizations.

![Screenshot Placeholder](https://via.placeholder.com/800x450/0f172a/0ea5ff?text=Piggypie+Dashboard+Preview)

## ✨ Premium Features

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

### 🎨 Fully Customizable UI
- **Dynamic Themes**: Toggle between a sleek Dark Mode and a crisp Light Mode.
- **Color Personalization**: Customize the theme, background, and card colors to match your style.
- **Responsive Design**: Seamless experience across desktop and mobile devices.

### 💼 Professional Data Management
- **Filtered History**: Search and filter transactions by date, category, or type.
- **CSV Export**: Download your entire transaction history for external analysis in Excel or other tools.
- **Secure Auth**: Robust user registration and login system with SHA-256 password hashing.

## 🛠️ Technology Stack
- **Backend**: Python / Flask
- **Database**: SQLite
- **Frontend**: HTML5, Vanilla CSS3, JavaScript (ES6+), Bootstrap 5
- **Charts**: Chart.js
- **Emails**: SMTP (Gmail integration ready)

## 🚀 Quick Start

1. **Install Dependencies**:
   ```bash
   pip install flask
   ```

2. **Configure Email (Optional)**:
   Update `EMAIL_CONFIG` in `app.py` with your SMTP details.

3. **Run the Application**:
   ```bash
   python app.py
   ```
   Visit `http://localhost:5000` in your browser.

---
*Built with ❤️ for better financial clarity.*
