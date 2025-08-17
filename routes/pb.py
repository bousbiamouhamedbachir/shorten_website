import uuid
import io
import json
import zipfile
import requests
from flask import Blueprint, render_template, request, jsonify, redirect, send_file
from models import db, Link, Stat
from sqlalchemy import func
from collections import defaultdict

bp = Blueprint("main", __name__)

# ----------------- GEOIP HELPER -----------------
def get_client_ip():
    """Get real client IP even behind PythonAnywhere reverse proxy"""
    if request.headers.get("X-Forwarded-For"):
        # X-Forwarded-For can contain multiple IPs
        ip = request.headers['X-Forwarded-For'].split(',')[0].strip()
    else:
        ip = request.remote_addr
    return ip

def get_country(ip):
    """Get country from IP using ipapi.co"""
    try:
        response = requests.get(f"https://ipapi.co/{ip}/country/", timeout=2)
        if response.status_code == 200:
            return response.text.strip()
        else:
            return "Unknown"
    except:
        return "Unknown"

# ----------------- INDEX -----------------
@bp.route("/")
def index():
    if request.args.get("json") == "1":
        total_links = Link.query.count()
        print(total_links)
        total_redirects = db.session.query(func.sum(Link.total_redirect)).scalar() or 0
        top_countries = (
            db.session.query(Stat.country, func.count(Stat.id).label("cnt"))
            .group_by(Stat.country)
            .order_by(func.count(Stat.id).desc())
            .limit(3)
            .all()
        )
        return jsonify({
            "total_links": total_links,
            "total_redirects": total_redirects,
            "top_countries": [{"country": c[0], "count": c[1]} for c in top_countries],
        })
    return render_template("index.html")


# ----------------- ADD LINK -----------------
@bp.route("/add_link", methods=["POST"])
def add_link():
    data = request.get_json()
    link = data.get("link")
    if not link:
        return jsonify({"error": "Missing link"}), 400

    link_id = str(uuid.uuid4())[:8]  # short UUID
    new_link = Link(id=link_id, link=link)
    db.session.add(new_link)
    db.session.commit()
    return jsonify({"id": link_id, "link": link})

# ----------------- REDIRECT -----------------
@bp.route("/<string:link_id>")
def redirect_link(link_id):
    link = Link.query.get(link_id)
    if not link:
        return jsonify({"error": "Link not found"}), 404

    # Update total_redirect
    link.total_redirect += 1

    # Detect country using real client IP
    ip = get_client_ip()
    country = get_country(ip)

    # Convert query parameters into JSON (safe validated)
    params = request.args.to_dict(flat=True)
    safe_meta = Stat.validate_metadata(params) if params else None

    # Save stat
    stat = Stat(link=link_id, country=country, meta=safe_meta)
    db.session.add(stat)
    db.session.commit()

    return redirect(link.link)

# ----------------- STATS FOR LINK -----------------
@bp.route("/<string:link_id>/stats")
def link_stats(link_id):
    link = Link.query.get(link_id)
    if not link:
        return jsonify({"error": "Link not found"}), 404

    countries = (
        db.session.query(Stat.country, func.count(Stat.id).label("cnt"))
        .filter(Stat.link == link_id)
        .group_by(Stat.country)
        .order_by(func.count(Stat.id).desc())
        .limit(10)
        .all()
    )

    weekday_stats = defaultdict(int)
    stats = Stat.query.filter_by(link=link_id).all()
    for s in stats:
        if s.at:
            day = s.at.strftime("%A")
            weekday_stats[day] += 1

    return render_template("stats.html", countries=countries, weekday_stats=weekday_stats, link=link)

# ----------------- GENERAL STATS -----------------
@bp.route("/stats")
def general_stats():
    countries = (
        db.session.query(Stat.country, func.count(Stat.id).label("cnt"))
        .group_by(Stat.country)
        .order_by(func.count(Stat.id).desc())
        .limit(10)
        .all()
    )

    weekday_stats = defaultdict(int)
    stats = Stat.query.all()
    for s in stats:
        if s.at:
            day = s.at.strftime("%A")
            weekday_stats[day] += 1

    return render_template("stats.html", countries=countries, weekday_stats=weekday_stats, link=None)

# ----------------- ABOUT & DOCS -----------------
@bp.route("/about")
def about():
    return render_template("about.html")

@bp.route("/docs")
def docs():
    return render_template("docs.html")

# ----------------- DOWNLOAD ALL STATS -----------------
@bp.route("/<string:link_id>/all")
def download_all_stats(link_id):
    link = Link.query.get(link_id)
    if not link:
        return jsonify({"error": "Link not found"}), 404

    stats = Stat.query.filter_by(link=link_id).all()
    stats_data = []
    for s in stats:
        stats_data.append({
            "id": s.id,
            "link": s.link,
            "at": s.at.isoformat() if s.at else None,
            "country": s.country,
            "metadata": s.meta
        })

    json_bytes = json.dumps(stats_data, indent=2).encode("utf-8")
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{link_id}_stats.json", json_bytes)

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{link_id}_stats.zip"
    )
@bp.route("/api/global_stats")
def global_stats():
    countries = (
        db.session.query(Stat.country, func.count(Stat.id).label("cnt"))
        .group_by(Stat.country)
        .order_by(func.count(Stat.id).desc())
        .limit(10)
        .all()
    )
    total_links = Link.query.count()
    total_redirects = db.session.query(func.sum(Link.total_redirect)).scalar() or 0

    return jsonify({
        "total_links": total_links,
        "total_redirects": total_redirects,
        "top_countries": [{"country": c[0], "count": c[1]} for c in countries]
    })
