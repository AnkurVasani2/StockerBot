# StockerBot 🚀

![StockerBot Logo](https://github.com/ankurvasani2/stockerbot/logo.jpg?raw=true)

Welcome to **StockerBot** – a smart Telegram bot designed to help you manage your stock portfolio, receive real-time predictions, and stay updated with the latest market news using advanced predictive analytics and AI.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
---

## Features 🌟

- **Portfolio Management:**  
  Add, view, and remove stocks from your portfolio with ease.

- **Real-Time Price Updates:**  
  Fetch current stock prices and compare with your buy price.

- **Daily Predictions:**  
  Receive daily buy/sell recommendations powered by the Groq LLM API.

- **Latest News:**  
  Get the most recent stock news to stay informed on market trends.

- **Notifications:**  
  Schedule notifications to be delivered directly to your Telegram account.

- **User-Friendly Commands:**  
  Simple commands like `/start`, `/add`, `/view`, `/remove`, `/news`, `/schedule`, and `/cancel`.

---

## Architecture 🏗️

- **Backend:**  
  Built using Python and the [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) framework.

- **Data Storage:**  
  Utilizes MongoDB (hosted on MongoDB Atlas) for storing portfolio data and user settings.

- **APIs:**  
  - **Stock Data & News:** Powered by an Indian stock exchange API via RapidAPI.
  - **AI Predictions:** Integrated with Groq LLM API for generating trade recommendations.

- **Scheduler:**  
  Uses [APScheduler](https://apscheduler.readthedocs.io/en/stable/) for daily prediction tasks, configured with timezone support.

---
## Contributing 🤝
Contributions are welcome! Please follow these guidelines:

- Fork the repository.
- Create a feature branch:
 `git checkout -b feature/your-feature`
- Commit your changes:
`git commit -m "Add some feature"`
- Push to the branch:
`git push origin feature/your-feature`
- Open a Pull Request.
