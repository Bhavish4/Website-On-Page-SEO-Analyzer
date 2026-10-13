# 🌐 Website On-Page SEO Analyzer 

A complete, lightweight, full-stack Python & Flask application designed to crawl, audit, and analyze website on-page SEO health. It inspects metadata, content quality, heading structures, image accessibility, link distributions, and technical signals, scoring pages out of 100 and generating instant downloadable PDF reports and local SQLite scan histories.

---

## 🚀 Key Features

### 🔍 Comprehensive On-Page SEO Checks
- **Title Tag Audit**: Verifies presence and optimal length (recommended 30–60 characters).
- **Meta Description Audit**: Verifies presence and optimal snippet length (recommended 120–160 characters).
- **Heading Hierarchy**: Inspects heading tags (H1–H6) and verifies that exactly one `<h1>` tag is present.
- **Image Accessibility**: Detects all `<img>` elements and lists up to 30 images lacking descriptive `alt` attributes.
- **Content Quality**: Evaluates clean extracted text word count against readable content benchmarks (>= 300 words).
- **Technical Signals**:
  - **HTTPS Enforcement**: Verifies secure protocol transport.
  - **Canonical URL**: Detects `rel="canonical"` to prevent duplicate content issues.
  - **Robots Directive**: Inspects meta robots directives (flags `noindex` blocks).
  - **Site Discoverability**: Tests availability of `/robots.txt` and `/sitemap.xml`.

### 🏷️ Keyword Intelligence (Optional)
- Input an optional target keyword to measure:
  - Exact keyword occurrence count & keyword density percentage.
  - Presence in the `<title>` tag, `<meta name="description">`, and `<h1>` heading.

### 🔗 Link Analysis & Sampling
- Counts internal vs. external links.
- Performs lightweight sampling (up to 8 unique links) with short timeouts to flag broken links (`4xx`/`5xx`), timeouts, or unreachable resources.

### 📊 Reports & Data Persistence
- **Interactive UI Dashboard**: Modern, responsive interface displaying score badges, diagnostic cards, and actionable tips.
- **Dynamic PDF Reports**: Exports professional, styled A4 audit reports using ReportLab generated directly in memory.
- **SQLite History**: Automatically logs previous audit runs with timestamps and scores for comparative tracking.

### 🛡️ Built-in Security Safeguards
- **SSRF Protection**: Resolves domain hostnames via DNS and blocks internal, private, loopback, and local network IP addresses (`127.0.0.1`, `10.x`, `192.168.x`, etc.).
- **Payload Limits**: Rejects responses over 3 MB to safeguard server resources.
- **In-Memory PDF Generation**: Generates PDF documents via `io.BytesIO` streams without accumulating temp files on disk.

---

## 📁 Project Structure

```text
Website_On_Page_SEO_Analyzer_Full/
├── app.py                  # Main Flask application, routing, crawler, scoring & PDF generator
├── requirements.txt        # Python dependency declarations
├── README.md               # Project documentation and guide
├── .gitignore              # Git ignore rules for virtual environments, DB, and caches
├── seo_history.db          # SQLite database storing audit scan history
├── static/
│   └── style.css           # Modern stylesheet with responsive design and theme tokens
└── templates/
    ├── index.html          # Main audit interface, search bar, and report viewer
    └── history.html        # Scan history listing and past audit viewer
```

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, Flask 3.0+
- **Parsing & Scraping**: Requests, BeautifulSoup4
- **PDF Generation**: ReportLab
- **Database**: SQLite3 (built into Python standard library)
- **Frontend**: HTML5, Vanilla CSS3 (Custom Design System, Flexbox, CSS Grid), Vanilla JavaScript

---

## ⚙️ Installation & Running Locally

### Prerequisites
- Python 3.10 or higher installed on your system.

---

### Windows

1. Open PowerShell or Command Prompt in the project directory:

   ```powershell
   # 1. Create a virtual environment
   python -m venv .venv

   # 2. Activate the virtual environment
   # In PowerShell:
   .\.venv\Scripts\Activate.ps1
   # (If PowerShell blocks script execution, run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)

   # In Command Prompt (cmd.exe):
   .\.venv\Scripts\activate.bat

   # 3. Install dependencies
   pip install -r requirements.txt

   # 4. Start the Flask development server
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

---

### macOS & Linux

1. Open Terminal in the project root directory:

   ```bash
   # 1. Create a virtual environment
   python3 -m venv .venv

   # 2. Activate the virtual environment
   source .venv/bin/activate

   # 3. Install dependencies
   pip install -r requirements.txt

   # 4. Start the application
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

---

## 🧭 Application Routes

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/` | `GET`, `POST` | Audit input form, score computation, and live report dashboard |
| `/history` | `GET` | Displays database log of previous scans |
| `/history/<scan_id>` | `GET` | Re-opens and inspects a saved historical audit |
| `/history/delete/<scan_id>` | `POST` | Deletes a specific scan record from SQLite database |
| `/history/clear` | `POST` | Clears all scan history records from database |
| `/report/<scan_id>.pdf` | `GET` | Generates and downloads an on-the-fly A4 PDF audit summary |

---

## 📐 Scoring Formula & Heuristics

The overall SEO score (0–100) is calculated based on weighted pass/fail checks:

| Check | Weight | Passing Criteria |
| :--- | :---: | :--- |
| **Title Tag Exists** | 2 | `<title>` is present in HTML head |
| **Title Tag Length** | 2 | Character length is between 30 and 60 characters |
| **Meta Description Exists** | 2 | `<meta name="description">` is present |
| **Meta Description Length** | 1 | Character length is between 120 and 160 characters |
| **Single H1 Tag** | 2 | Exactly one `<h1>` heading exists on the page |
| **Image Alt Attributes** | 2 | All detected `<img>` elements have non-empty `alt` text |
| **Content Volume** | 1 | Clean body text contains 300 or more words |
| **Canonical URL** | 1 | `<link rel="canonical">` is specified |
| **Indexing Directive** | 2 | Meta robots directive does not contain `noindex` |
| **Internal Links** | 1 | At least 3 internal links found |
| **External Links** | 1 | At least 1 outbound link found |
| **HTTPS Protocol** | 1 | Page served securely over `https://` |
| **Keyword in Title** *(if keyword provided)* | 1 | Keyword appears in `<title>` |
| **Keyword in Description** *(if keyword provided)* | 1 | Keyword appears in meta description |
| **Keyword in H1** *(if keyword provided)* | 1 | Keyword appears in `<h1>` |

$$\text{Final Score} = \text{round}\left(100 \times \frac{\sum \text{Passed Weights}}{\sum \text{Total Check Weights}}\right)$$

---

## ⚠️ Limitations & Security Notice

- **Educational Heuristic**: This tool provides educational on-page heuristic scores and does not represent official Google Search rankings or indexing algorithms.
- **JavaScript-Rendered SPAs**: Sites requiring client-side JavaScript rendering (e.g., pure React/Vue/Angular SPAs without SSR) may not reveal dynamically populated content to BeautifulSoup.
- **Bot Mitigation**: Some websites employ Cloudflare, Akamai, or custom WAFs that may block automated bot requests with `403 Forbidden` or CAPTCHAs.
- **Production Deployment**:
  - Set a persistent and cryptographically secure `SECRET_KEY` environment variable.
  - Disable Flask debug mode (`debug=False`).
  - Deploy behind a production WSGI server such as **Gunicorn** or **Waitress** with reverse proxy (e.g., NGINX).
  - Configure rate limiting to prevent abuse.
