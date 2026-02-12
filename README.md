# 🤖 AI-Powered Upwork Job Scraper

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Automated system for discovering, analyzing, and applying to Upwork freelance jobs. Uses AI to classify jobs, match against your preferences, and generate customized proposals.

![Dashboard Screenshot](https://via.placeholder.com/800x400?text=Streamlit+Dashboard+Screenshot)

---

## ✨ Features

- 🔍 **Smart Scraping** - Bypasses Cloudflare using real Chrome browser
- 🤖 **AI Classification** - Categorizes jobs using Groq AI (free tier: 100K tokens/day)
- 🎯 **Intelligent Matching** - Scores jobs against your skills and preferences
- ✍️ **Proposal Generation** - Creates personalized proposals with AI
- 📧 **Email Notifications** - Sends proposals directly to your inbox
- 📊 **Live Dashboard** - Streamlit web interface with real-time filtering
- ⭐ **Favorites System** - Bookmark interesting jobs
- 🔄 **Crash Recovery** - Incremental saves allow resuming from any point

---

## 🚀 Quick Start

```bash
# 1. Clone and setup
git clone <repo-url>
cd upwork-scrap
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Configure (add your API keys)
cp .env.example .env
nano .env

# 3. Run your first scrape
python main.py scrape --keyword "machine learning" --pages 2

# 4. Launch dashboard
streamlit run dashboard/app.py
```

**Full setup guide:** [USER_GUIDE.md](USER_GUIDE.md)

---

## 📖 Documentation

- **[User Guide](USER_GUIDE.md)** - Complete setup, configuration, and usage instructions
- **[Analysis Report](ANALYSIS_REPORT.md)** - System architecture and code quality analysis
- **[Fixes Completed](FIXES_COMPLETED.md)** - Recent improvements and bug fixes
- **[PRD](docs/PRD.md)** - Product requirements and feature specifications
- **[Workflow](docs/WORKFLOW.md)** - Implementation phases and development roadmap

---

## 🎯 How It Works

### 1. Scraping
```bash
python main.py scrape --new  # Scrape latest jobs (2 pages per keyword)
```
- Uses real Chrome (not Playwright's Chromium) to bypass Cloudflare
- Scrapes public Upwork search results (no login required)
- Saves incrementally to SQLite database (crash-safe)
- Memory cleanup every 5 keywords prevents OOM crashes

### 2. AI Classification
```bash
python -m classifier.ai  # Classify unprocessed jobs
```
- Batch processes 20 jobs per API call (efficient)
- Adds categories, key tools, and summaries
- Uses Groq AI (free tier: 100K tokens/day)
- Tracks rate limits to prevent quota exhaustion

### 3. Job Matching
```bash
# Runs automatically in monitor pipeline
python main.py monitor --new
```
- Scores jobs 0-100 based on:
  - Budget match (30%)
  - Skills overlap (25%)
  - Experience level (15%)
  - Client quality (15%)
  - Competition (10%)
  - Job type (5%)
- Filters by threshold (default: 50)

### 4. Proposal Generation
```bash
# Generates proposals for top 50 matches
python main.py monitor --new
```
- Uses your profile, portfolio, and guidelines
- Customizes each proposal to job requirements
- References relevant past projects
- Sends email with all proposals

### 5. Dashboard
```bash
streamlit run dashboard/app.py
```
- Real-time job filtering (category, budget, skills)
- Proposal management (approve/reject/edit)
- Analytics dashboard (charts and metrics)
- Export to CSV

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```bash
# Groq API Key (get free key at: https://console.groq.com/keys)
GROQ_API_KEY=your_groq_api_key_here

# Gmail App Password (generate at: https://myaccount.google.com/apppasswords)
GMAIL_APP_PASSWORD=your_16_char_app_password_here
```

### Job Preferences (`config/job_preferences.yaml`)

```yaml
budget:
  hourly_min: 25        # Minimum hourly rate
  fixed_min: 500        # Minimum fixed budget

preferred_skills:
  - Python
  - Machine Learning
  - TensorFlow

threshold: 50           # Minimum match score (0-100)
```

### Freelancer Profile (`config/freelancer_profile.yaml`)

```yaml
name: "Your Name"
title: "Full-Stack AI/ML Engineer"
skills:
  - Python, TensorFlow
  - FastAPI, React
hourly_rate: 50
```

**See [USER_GUIDE.md](USER_GUIDE.md#configuration) for complete configuration options.**

---

## 📊 Dashboard

The Streamlit dashboard provides a comprehensive interface for managing jobs and proposals:

### Jobs Tab
- **Filters:** Category, Budget, Experience, Skills, Location
- **Actions:** Favorite, View Details, Open in Upwork
- **Sorting:** Newest, Highest Budget, Most Proposals

### Proposals Tab
- **Status:** Pending Review, Approved, Rejected
- **Actions:** Approve, Reject, Edit, Copy, Rate
- **Details:** Match score, reasons, job info, AI-identified tools

### Analytics Tab
- Jobs by category (pie chart)
- Budget distribution (histogram)
- Skills frequency (bar chart)
- Match rate and proposal success metrics

---

## 🛠️ Commands

### Scraping

```bash
# Daily scrape (2 pages per keyword, ~1,500 jobs)
python main.py scrape --new

# Full scrape (all pages, all keywords)
python main.py scrape --full

# Specific keyword (10 pages)
python main.py scrape --keyword "tensorflow" --pages 10

# Resume from page 8 (if crashed)
python main.py scrape --keyword "ai" --pages 10 --start-page 8
```

### Classification

```bash
# Classify unprocessed jobs
python -m classifier.ai

# Check classification progress
python -m classifier.ai --status
```

### Monitoring Pipeline

```bash
# Full pipeline (scrape → classify → match → generate → email)
python main.py monitor --new

# Dry run (test without sending emails)
python main.py monitor --new --dry-run
```

### Stats & Reports

```bash
# Terminal summary
python main.py stats

# API usage
python api_usage_tracker.py

# Dashboard
streamlit run dashboard/app.py
```

---

## 📈 System Architecture

```
┌─────────────┐
│   Scraper   │  Chrome CDP + Cloudflare bypass
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  SQLite DB  │  Incremental saves, WAL mode
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ AI Classify │  Groq API (batch processing)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Matcher   │  Weighted scoring algorithm
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Proposals  │  AI-generated with profile
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Notifier  │  Email + Dashboard
└─────────────┘
```

**Key Design Decisions:**
- **Real Chrome, not Playwright's Chromium** - Bypasses Cloudflare detection
- **Incremental saves** - Data persists after each page (crash-safe)
- **Batch classification** - 20 jobs per API call (efficient)
- **Rate limit tracking** - Prevents API quota exhaustion
- **Memory cleanup** - Prevents OOM crashes during long runs

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_matcher.py

# Run with coverage
pytest --cov=. --cov-report=html
```

**Test Coverage:**
- Unit tests for matcher, database, config
- Integration tests for proposal generation
- Fixtures in `tests/fixtures/`

---

## 🔧 Troubleshooting

### Common Issues

**1. "Target page closed" Error**
- Cause: Cloudflare challenge timeout
- Solution: Increase timeout in `scraper/browser.py` or manually solve CAPTCHA

**2. "Rate limit exceeded"**
- Cause: Exceeded Groq API free tier (100K tokens/day)
- Solution: Check usage with `python api_usage_tracker.py`, wait until tomorrow

**3. Memory Crash (Exit Code 137)**
- Cause: Chrome consuming too much RAM
- Solution: Automatic cleanup every 5 keywords (already implemented)

**4. No Matches Found**
- Cause: Preferences too strict
- Solution: Lower `threshold` to 40, reduce `hourly_min` to 20

**See [USER_GUIDE.md](USER_GUIDE.md#troubleshooting) for complete troubleshooting guide.**

---

## 📊 Performance Metrics

### Current Performance
- **Scraping:** 100 jobs/keyword (2 pages × 50 jobs)
- **Classification:** 2,725 jobs classified (100% success)
- **Matching:** 30.7% match rate (838/2,725 jobs)
- **Proposals:** 86% success rate (43/50 generated)
- **Email Delivery:** 100% (43 proposals delivered)

### System Requirements
- **RAM:** 4GB minimum (8GB recommended)
- **Disk:** 500MB for data directory
- **Network:** Stable connection for Cloudflare challenges
- **Browser:** Chrome installed (any version)

---

## 🛡️ Security & Privacy

- ✅ **No Upwork login required** - Scrapes public data only
- ✅ **Secrets in .env** - Not tracked by git
- ✅ **Gmail app password** - Not your main password
- ✅ **Local processing** - All data stays on your machine
- ✅ **No external tracking** - No analytics or telemetry

**Security Best Practices:**
- Never commit `.env` file (already in `.gitignore`)
- Use Gmail app passwords, not account password
- Review proposals before sending to clients
- Keep API keys confidential

---

## 🗺️ Roadmap

### Phase 3 (Completed ✅)
- ✅ Live Streamlit dashboard
- ✅ Groq-only AI (simplified from multi-provider)
- ✅ Quality feedback loop (rate proposals)
- ✅ Email notification system

### Phase 4 (Current)
- ⏳ Rate limit tracking (completed)
- ⏳ Memory management (completed)
- ⏳ Match score fix (completed)
- ⏳ Parallel proposal generation
- ⏳ Advanced analytics dashboard

### Phase 5 (Future)
- 🔮 Scheduled monitoring (cron jobs)
- 🔮 Webhook integration (Slack/Discord)
- 🔮 A/B testing for proposals
- 🔮 ML-based match optimization

**See [docs/WORKFLOW.md](docs/WORKFLOW.md) for complete roadmap.**

---

## 📜 License

MIT License - See [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Groq** - Fast AI inference with generous free tier
- **Playwright** - Reliable browser automation
- **Streamlit** - Beautiful dashboard framework
- **Upwork** - Platform for freelance opportunities

---

## 📞 Support

### Getting Help

1. **Check documentation:**
   - [User Guide](USER_GUIDE.md) - Complete usage instructions
   - [Analysis Report](ANALYSIS_REPORT.md) - System overview
   - [Troubleshooting](USER_GUIDE.md#troubleshooting) - Common issues

2. **Check logs:**
   ```bash
   cat data/monitor.log
   python api_usage_tracker.py
   ```

3. **GitHub Issues:**
   - Search existing issues
   - Create new issue with error logs

### Useful Commands

```bash
# Database info
sqlite3 data/jobs.db "SELECT COUNT(*) FROM jobs"

# Check rate limits
python api_usage_tracker.py

# View last pipeline run
cat data/last_run_status.json

# Kill stuck processes
pkill -9 -f streamlit
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Development Setup:**
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black .

# Lint
flake8 .
```

---

## ⭐ Star History

If this project helps you land more gigs, consider giving it a star! ⭐

---

**Built with ❤️ by freelancers, for freelancers.**

**Happy job hunting! 🚀**
