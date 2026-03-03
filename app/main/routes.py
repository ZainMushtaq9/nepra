from flask import render_template, flash, redirect, url_for, request, send_from_directory, Response, jsonify
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from urllib.parse import urlsplit
import os
import json
import logging
import time
from collections import defaultdict
from werkzeug.utils import secure_filename
from flask import send_file

from app import db
from app.main import bp
from app.models import User, Bill, Chat
from app.main.forms import LoginForm, RegistrationForm, UploadForm, ChatForm, DirectFetchForm, SettingsForm
from app.logic.ocr import extract_text_from_image, parse_bill_data
from app.logic.reasoning import analyze_bill
from app.logic.ai import generate_ai_response
from app.logic.generator import generate_complaint_docx
from app.logic.scraper import scrape_pitc_bill

logger = logging.getLogger(__name__)

# ─── Rate Limiting (In-Memory) ───
_rate_limit_store = defaultdict(list)  # user_id -> [timestamps]
RATE_LIMIT_MAX = 20  # max messages per window
RATE_LIMIT_WINDOW = 60  # seconds
MAX_MESSAGE_LENGTH = 2000  # max chars per message


def _check_rate_limit(user_id):
    """Returns True if rate limit is exceeded."""
    now = time.time()
    # Clean old entries
    _rate_limit_store[user_id] = [t for t in _rate_limit_store[user_id] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[user_id]) >= RATE_LIMIT_MAX:
        return True
    _rate_limit_store[user_id].append(now)
    return False

# ─── Public Routes ───

@bp.route('/')
@bp.route('/index')
def index():
    return render_template('index.html', title='Home')

@bp.route('/robots.txt')
@bp.route('/sitemap.xml')
def static_from_root():
    from flask import current_app
    return send_from_directory(current_app.static_folder, request.path[1:])

# ─── Auth Routes ───

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == form.email.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password', 'danger')
            return redirect(url_for('main.login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(name=form.name.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Register', form=form)

# ─── Bill Processing Routes ───

def _get_latest_bill_context():
    """Get the most recent bill context for the current user (for chat injection)."""
    latest_bill = Bill.query.filter_by(user_id=current_user.id).order_by(Bill.created_at.desc()).first()
    if latest_bill:
        return {
            'bill_json': latest_bill.bill_json,
            'fault_type': latest_bill.fault_type,
            'analysis_result': latest_bill.analysis_result,
            'bill_id': latest_bill.id
        }
    return None

@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    form = UploadForm()
    fetch_form = DirectFetchForm()
    if form.validate_on_submit():
        f = form.bill_image.data
        filename = secure_filename(f.filename)
        from flask import current_app
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        f.save(filepath)
        
        # OCR Processing
        raw_text = extract_text_from_image(filepath)
        bill_data = parse_bill_data(raw_text)
        
        # Layer 1 – Deterministic Reason Detection
        analysis_text, fault_type = analyze_bill(bill_data)
        
        # Save to DB
        bill = Bill(
            user_id=current_user.id,
            bill_json=json.dumps(bill_data),
            analysis_result=analysis_text,
            fault_type=fault_type
        )
        db.session.add(bill)
        db.session.commit()
        
        flash('Bill analyzed successfully!', 'success')
        return redirect(url_for('main.results', bill_id=bill.id)) 
    return render_template('upload.html', title='Upload Bill', form=form, fetch_form=fetch_form)

@bp.route('/fetch', methods=['POST'])
@login_required
def fetch():
    fetch_form = DirectFetchForm()
    if fetch_form.validate_on_submit():
        ref_no = fetch_form.ref_no.data
        company = fetch_form.company.data
        
        try:
            result = scrape_pitc_bill(ref_no, company)
            if result and result.get('data'):
                bill_data = result['data']
                raw_html = result.get('raw_html', '')
                
                # Layer 1 – Deterministic Reason Detection
                analysis_text, fault_type = analyze_bill(bill_data)
                
                bill = Bill(
                    user_id=current_user.id,
                    bill_json=json.dumps(bill_data),
                    analysis_result=analysis_text,
                    fault_type=fault_type,
                    raw_html=raw_html
                )
                db.session.add(bill)
                db.session.commit()
                
                flash('Bill fetched and analyzed successfully!', 'success')
                return redirect(url_for('main.results', bill_id=bill.id))
            else:
                flash('Could not fetch bill data. Please check the reference number.', 'warning')
        except Exception as e:
            logger.error(f"Bill fetch error: {e}")
            flash('Error fetching bill. Please try again later.', 'danger')
    
    form = UploadForm()
    return render_template('upload.html', title='Upload Bill', form=form, fetch_form=fetch_form)

@bp.route('/results/<int:bill_id>')
@login_required
def results(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    if bill.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    try:
        bill_data = json.loads(bill.bill_json)
    except:
        bill_data = {}
        
    return render_template('results.html', title='Analysis Results', bill=bill, bill_data=bill_data)

@bp.route('/download/<int:bill_id>')
@login_required
def download_complaint(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    if bill.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    filename, filepath = generate_complaint_docx(bill)
    return send_file(filepath, as_attachment=True, download_name=filename)

@bp.route('/download_html/<int:bill_id>')
@login_required
def download_html(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    if bill.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    if not bill.raw_html:
        flash('No original web bill available for this entry.', 'warning')
        return redirect(url_for('main.results', bill_id=bill.id))
        
    return Response(
        bill.raw_html,
        mimetype="text/html",
        headers={"Content-Disposition": f"inline; filename=original_bill_{bill.id}.html"}
    )

# ─── Chatbot Routes (Core Interface) ───

@bp.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    form = ChatForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        user_message = form.message.data
        
        # Input validation
        if len(user_message) > MAX_MESSAGE_LENGTH:
            if request.headers.get('Accept') == 'application/json':
                return jsonify({"status": "error", "response": f"Message too long. Maximum {MAX_MESSAGE_LENGTH} characters."}), 400
            flash(f'Message too long. Maximum {MAX_MESSAGE_LENGTH} characters.', 'warning')
            return redirect(url_for('main.chat'))
        
        # Rate limiting
        if _check_rate_limit(current_user.id):
            if request.headers.get('Accept') == 'application/json':
                return jsonify({"status": "error", "response": "Too many messages. Please wait a moment."}), 429
            flash('Too many messages. Please wait a moment before sending again.', 'warning')
            return redirect(url_for('main.chat'))
        
        # Get bill context if user has uploaded a bill (Layer 1 data injection)
        bill_context = _get_latest_bill_context()
        
        # Build context snapshot for this chat entry
        context_snapshot_data = json.dumps(bill_context) if bill_context else None
        bill_id = bill_context.get('bill_id') if bill_context else None
        
        # Save user message to DB with context
        chat_entry = Chat(
            user_id=current_user.id,
            bill_id=bill_id,
            message=user_message,
            response="",
            context_snapshot=context_snapshot_data
        )
        db.session.add(chat_entry)
        db.session.commit()
        
        # Get conversation history (last 6 exchanges) for context
        history_query = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.timestamp.desc()).limit(6).all()
        history_query.reverse()
        
        chat_history = []
        for h in history_query[:-1]:  # exclude the one we just added
            if h.message:
                chat_history.append({"role": "user", "content": h.message})
            if h.response:
                chat_history.append({"role": "assistant", "content": h.response})
        
        # Get user-specific API key (falls back to env var inside ai.py)
        user_api_key = current_user.groq_api_key if current_user.groq_api_key else None
        
        # Call Layer 2 – AI Explanation
        ai_response = generate_ai_response(
            user_message, 
            chat_history=chat_history, 
            bill_context=bill_context,
            api_key=user_api_key
        )
        
        # Update DB with AI response
        chat_entry.response = ai_response
        db.session.commit()
        
        # AJAX response
        if request.headers.get('Accept') == 'application/json':
            return jsonify({"status": "success", "response": ai_response, "message": user_message})
            
        return redirect(url_for('main.chat'))
    
    # GET: Render chat page with full history
    chats = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.timestamp.asc()).all()
    
    # Check if user has a bill context
    has_bill = Bill.query.filter_by(user_id=current_user.id).first() is not None
    
    return render_template('chat.html', title='AI Legal Chat', form=form, chats=chats, has_bill=has_bill)


@bp.route('/chat/<int:chat_id>', methods=['DELETE'])
@login_required
def delete_chat(chat_id):
    """Delete a single chat message."""
    chat_entry = Chat.query.get_or_404(chat_id)
    if chat_entry.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    db.session.delete(chat_entry)
    db.session.commit()
    return jsonify({"status": "success"})


@bp.route('/chat/clear', methods=['DELETE'])
@login_required
def clear_chats():
    """Delete all chats for the current user."""
    Chat.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"status": "success", "message": "Chat history cleared."})

# ─── Settings Route ───

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    form = SettingsForm()
    if form.validate_on_submit():
        current_user.groq_api_key = form.groq_api_key.data if form.groq_api_key.data else None
        db.session.commit()
        flash('Settings saved successfully!', 'success')
        return redirect(url_for('main.settings'))
    
    # Pre-fill existing key (masked)
    if current_user.groq_api_key:
        form.groq_api_key.data = current_user.groq_api_key
    
    return render_template('settings.html', title='Settings', form=form)

# ─── Dashboard ───

@bp.route('/dashboard')
@login_required
def dashboard():
    bills = Bill.query.filter_by(user_id=current_user.id).order_by(Bill.created_at.desc()).all()
    return render_template('dashboard.html', title='Dashboard', bills=bills)
