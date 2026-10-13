import os, json, socket, ipaddress, sqlite3, io
from datetime import datetime
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, url_for, send_file, abort
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

app = Flask(__name__)
# Generate secure fallback key in development if SECRET_KEY env is not set
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24).hex()
DB = os.path.join(os.path.dirname(__file__), "seo_history.db")
HEADERS = {"User-Agent": "StudentSEOAnalyzer/1.0"}
TIMEOUT = 8

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS scans(
            id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, created_at TEXT,
            score INTEGER, result_json TEXT)""")

def validate_url(raw):
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Enter a website URL.")
    if "://" not in raw:
        raw = "https://" + raw
    p = urlparse(raw)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("Enter a valid http:// or https:// URL.")
    if p.hostname == "localhost" or p.hostname.endswith(".local"):
        raise ValueError("Local addresses are not supported.")
    try:
        for item in socket.getaddrinfo(p.hostname, None):
            if not ipaddress.ip_address(item[4][0]).is_global:
                raise ValueError("Private or local network addresses are not supported.")
    except socket.gaierror:
        raise ValueError("Could not resolve this domain.")
    return raw

def get_page(url, timeout=TIMEOUT):
    # Revalidate every URL to prevent SSRF against private networks
    valid_url = validate_url(url)
    return requests.get(valid_url, headers=HEADERS, timeout=timeout, allow_redirects=True)

def analyze(url, keyword=""):
    response = get_page(url)
    response.raise_for_status()
    if "html" not in response.headers.get("Content-Type", "").lower():
        raise ValueError("This URL did not return an HTML page.")
    if len(response.content) > 3_000_000:
        raise ValueError("Page exceeds the 3 MB demo limit.")

    soup = BeautifulSoup(response.text, "html.parser")
    title_el = soup.find("title")
    title = title_el.get_text(" ", strip=True) if title_el else ""
    desc_el = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "description"})
    description = desc_el.get("content", "").strip() if desc_el else ""
    canon_el = soup.find("link", rel=lambda v: v and "canonical" in [x.lower() for x in (v if isinstance(v, list) else [v])])
    canonical = urljoin(response.url, canon_el.get("href", "")) if canon_el and canon_el.get("href") else "Not found"
    robots_el = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "robots"})
    robots = robots_el.get("content", "") if robots_el else "Not specified"
    headings = {f"H{i}": [h.get_text(" ", strip=True) for h in soup.find_all(f"h{i}")] for i in range(1, 7)}
    images = soup.find_all("img")
    missing_alt = [urljoin(response.url, im.get("src", "")) or "(unknown image)" for im in images if not im.has_attr("alt") or not im.get("alt", "").strip()]
    
    internal, external = [], []
    host = urlparse(response.url).hostname
    for a in soup.find_all("a", href=True):
        href = urljoin(response.url, a["href"].strip())
        p = urlparse(href)
        if p.scheme in ("http", "https") and p.hostname:
            (internal if p.hostname == host else external).append(href)

    for el in soup(["script", "style", "noscript", "svg", "template"]):
        el.decompose()

    page_text = soup.get_text(" ", strip=True)
    words = page_text.split()
    word_count = len(words)
    keyword = (keyword or "").strip()
    occurrences = page_text.lower().count(keyword.lower()) if keyword else 0
    density = round(occurrences / max(word_count, 1) * 100, 2) if keyword else None

    checks = []
    def add(name, ok, detail, weight=1):
        checks.append({"name": name, "passed": bool(ok), "detail": str(detail), "weight": weight})

    add("Title tag exists", bool(title), f"{len(title)} characters" if title else "Missing", 2)
    add("Title length", 30 <= len(title) <= 60, f"{len(title)} characters; recommended 30–60", 2)
    add("Meta description exists", bool(description), f"{len(description)} characters" if description else "Missing", 2)
    add("Meta description length", 120 <= len(description) <= 160, f"{len(description)} characters; recommended 120–160")
    add("Exactly one H1", len(headings["H1"]) == 1, f"{len(headings['H1'])} H1 headings found", 2)
    add("Images have alt text", not missing_alt, f"{len(missing_alt)} of {len(images)} images missing alt text", 2)
    add("Readable text content", word_count >= 300, f"{word_count} words; 300 is a rough guideline")
    add("Canonical URL", canonical != "Not found", canonical)
    add("Indexing directive", "noindex" not in robots.lower(), f"Robots: {robots}", 2)
    add("Internal links", len(internal) >= 3, f"{len(internal)} found")
    add("External links", len(external) >= 1, f"{len(external)} found")
    add("HTTPS", response.url.startswith("https://"), response.url)

    if keyword:
        add("Keyword in title", keyword.lower() in title.lower(), "Found" if keyword.lower() in title.lower() else "Not found")
        add("Keyword in meta description", keyword.lower() in description.lower(), "Found" if keyword.lower() in description.lower() else "Not found")
        add("Keyword in H1", any(keyword.lower() in h.lower() for h in headings["H1"]), "Found" if any(keyword.lower() in h.lower() for h in headings["H1"]) else "Not found")

    total = sum(c["weight"] for c in checks)
    score = round(100 * sum(c["weight"] for c in checks if c["passed"]) / total)
    advice = {
        "Title tag exists": "Add a descriptive title tag.",
        "Title length": "Consider a title around 30–60 characters.",
        "Meta description exists": "Write a unique meta description summarizing the page.",
        "Meta description length": "Consider a description around 120–160 characters.",
        "Exactly one H1": "Use one clear H1 describing the main page topic.",
        "Images have alt text": "Add descriptive alt text to informative images.",
        "Readable text content": "Review whether the page has enough useful content for its purpose.",
        "Canonical URL": "Add a canonical URL when a preferred page URL should be specified.",
        "Indexing directive": "Review noindex if this page should appear in search results.",
        "Internal links": "Add useful links to related pages on your site.",
        "External links": "Link to trustworthy external resources where useful.",
        "HTTPS": "Enable HTTPS and redirect HTTP traffic to HTTPS.",
        "Keyword in title": "Use the target keyword naturally in the title if relevant.",
        "Keyword in meta description": "Use the target keyword naturally in the meta description if relevant.",
        "Keyword in H1": "Use the target keyword naturally in the H1 if relevant."
    }
    recommendations = [advice[c["name"]] for c in checks if not c["passed"]]

    # Check a small sample only using smaller timeout to prevent long delays
    broken = []
    sampled_links = list(dict.fromkeys(internal + external))[:8]
    for link in sampled_links:
        try:
            r = get_page(link, timeout=3)
            if r.status_code >= 400:
                broken.append({"url": link, "status": r.status_code})
        except requests.exceptions.Timeout:
            broken.append({"url": link, "status": "timeout"})
        except Exception:
            broken.append({"url": link, "status": "unavailable"})

    if broken:
        recommendations.append(f"Review {len(broken)} sampled links that returned an error or were unreachable.")

    origin = f"{urlparse(response.url).scheme}://{urlparse(response.url).netloc}"
    resources = {}
    for name, path in [("robots.txt", "/robots.txt"), ("sitemap.xml", "/sitemap.xml")]:
        res_url = urljoin(origin, path)
        try:
            r = get_page(res_url, timeout=4)
            resources[name] = {"url": res_url, "status": r.status_code, "available": r.status_code == 200}
        except Exception:
            resources[name] = {"url": res_url, "status": "unavailable", "available": False}

    return {
        "url": response.url,
        "status_code": response.status_code,
        "score": score,
        "title": title or "Missing",
        "description": description or "Missing",
        "canonical": canonical,
        "robots": robots,
        "word_count": word_count,
        "headings": headings,
        "images_count": len(images),
        "missing_alt": missing_alt[:30],  # Cap list to prevent unbounded DB storage
        "internal_count": len(internal),
        "external_count": len(external),
        "checks": checks,
        "recommendations": recommendations,
        "keyword": keyword,
        "keyword_count": occurrences,
        "keyword_density": density,
        "title_has_keyword": bool(keyword and keyword.lower() in title.lower()),
        "desc_has_keyword": bool(keyword and keyword.lower() in description.lower()),
        "h1_has_keyword": bool(keyword and any(keyword.lower() in h.lower() for h in headings["H1"])),
        "broken_links": broken,
        "resources": resources
    }

def save(result):
    created = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    with connect() as c:
        cur = c.execute("INSERT INTO scans(url,created_at,score,result_json) VALUES(?,?,?,?)",
            (result["url"], created, result["score"], json.dumps(result)))
        return cur.lastrowid

@app.route("/", methods=["GET", "POST"])
def index():
    result = error = None
    submitted_url = keyword = ""
    if request.method == "POST":
        submitted_url = request.form.get("url", "").strip()
        keyword = request.form.get("keyword", "").strip()
        try:
            valid_url = validate_url(submitted_url)
            result = analyze(valid_url, keyword)
            result["scan_id"] = save(result)
        except (ValueError, requests.RequestException) as e:
            error = str(e) or "Could not analyze the page."
        except Exception:
            app.logger.exception("Analysis error")
            error = "Analysis failed. The site may block automated requests."
    with connect() as c:
        recent = c.execute("SELECT id,url,created_at,score FROM scans ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("index.html", result=result, error=error, submitted_url=submitted_url, keyword=keyword, recent=recent)

@app.route("/history")
def history():
    with connect() as c:
        scans = c.execute("SELECT id,url,created_at,score FROM scans ORDER BY id DESC LIMIT 100").fetchall()
    return render_template("history.html", scans=scans)

@app.route("/history/delete/<int:scan_id>", methods=["POST"])
def delete_scan(scan_id):
    with connect() as c:
        c.execute("DELETE FROM scans WHERE id=?", (scan_id,))
    return redirect(url_for("history"))

@app.route("/history/clear", methods=["POST"])
def clear_history():
    with connect() as c:
        c.execute("DELETE FROM scans")
    return redirect(url_for("history"))

@app.route("/history/<int:scan_id>")
def history_detail(scan_id):
    with connect() as c:
        row = c.execute("SELECT result_json FROM scans WHERE id=?", (scan_id,)).fetchone()
    if not row:
        abort(404)
    result = json.loads(row["result_json"])
    result["scan_id"] = scan_id
    with connect() as c:
        recent = c.execute("SELECT id,url,created_at,score FROM scans ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("index.html", result=result, error=None, submitted_url=result["url"], keyword=result.get("keyword", ""), recent=recent)

@app.route("/report/<int:scan_id>.pdf")
def pdf_report(scan_id):
    with connect() as c:
        row = c.execute("SELECT result_json,created_at FROM scans WHERE id=?", (scan_id,)).fetchone()
    if not row:
        abort(404)
    result = json.loads(row["result_json"])

    # Build PDF directly in memory to avoid unbounded disk accumulation
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    story = [
        Paragraph("Website On-Page SEO Analyzer", styles["Title"]),
        Spacer(1, 5 * mm),
        Paragraph(f"<b>Website:</b> {result['url']}", styles["BodyText"]),
        Paragraph(f"<b>Generated:</b> {row['created_at']}", styles["BodyText"]),
        Paragraph(f"<b>SEO Score:</b> {result['score']}/100", styles["Heading2"]),
        Paragraph("Page summary", styles["Heading2"]),
        Paragraph(f"Title: {result['title']}", styles["BodyText"]),
        Paragraph(f"Meta description: {result['description']}", styles["BodyText"]),
        Paragraph(f"Words: {result['word_count']} | Images: {result['images_count']} | Internal links: {result['internal_count']} | External links: {result['external_count']}", styles["BodyText"]),
        Spacer(1, 4 * mm),
        Paragraph("SEO checks", styles["Heading2"])
    ]
    data = [["Check", "Status", "Details"]]
    for item in result["checks"]:
        data.append([
            Paragraph(item["name"], styles["BodyText"]),
            "PASS" if item["passed"] else "REVIEW",
            Paragraph(item["detail"][:350], styles["BodyText"])
        ])
    table = Table(data, colWidths=[43 * mm, 22 * mm, 100 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf1ff")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9e1ee")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5)
    ]))
    story += [table, Spacer(1, 4 * mm), Paragraph("Recommendations", styles["Heading2"])]
    for rec in result["recommendations"]:
        safe = rec.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph("• " + safe, styles["BodyText"]))
        story.append(Spacer(1, 2 * mm))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Educational heuristic only; this is not an official Google score or ranking guarantee.", styles["Italic"]))
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"seo_report_{scan_id}.pdf", mimetype="application/pdf")

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
