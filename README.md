# 🎬 Nexus Scraper Engine API

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright)
![Python](https://img.shields.io/badge/Python-3.10-blue?style=for-the-badge&logo=python)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker)

Nexus Engine is a highly optimized, asynchronous web scraping API built with **FastAPI** and **Playwright**. Designed for extreme speed and scalability, it features smart routing, auto-healing browser pooling, and stealth mode to bypass modern protections seamlessly.

## ✨ Core Features
*   **Asynchronous Architecture:** Built on FastAPI for lightning-fast, non-blocking requests.
*   **Stealth Mode:** Custom Chromium arguments to bypass Cloudflare and basic bot-detection.
*   **Memory Safe:** Implements global browser lifecycle management to prevent memory leaks in cloud environments.
*   **Auto-Sorting & Filtering:** Automatically filters out dead servers and ranks links based on quality (4K, 1080p) and server reliability.
*   **Ad & Tracker Blocking:** Intercepts and blocks unnecessary network requests (ads/popups) at the proxy level to speed up extraction by 2x.

## ⚠️ Legal & Ethical Disclaimer
**STRICTLY FOR EDUCATIONAL AND RESEARCH PURPOSES.**
Nexus Engine is a standalone API tool designed to demonstrate modern web scraping techniques, DOM parsing, and headless browser automation.

*   We **do not** host, store, or distribute any copyrighted media, files, or torrents on our servers.
*   We **do not** promote piracy. The engine merely crawls publicly available links from third-party sources across the internet.
*   The author is not responsible for how this software is used. Users are strictly advised to adhere to the terms of service of the websites they interact with and comply with their local copyright laws.

## 🚀 Deployment (Docker / Hugging Face)
This project is fully containerized and ready to be deployed on platforms like Hugging Face Spaces, Render, or Railway.

# Clone the repository
git clone https://github.com/SachinYedav/nexus-scraper-engine.git
cd nexus-scraper-engine

# Build and run using Docker
docker build -t nexus-api .
docker run -p 7860:7860 nexus-api

## 📜 License
This project is licensed under the MIT License.


