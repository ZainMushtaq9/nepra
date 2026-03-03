from flask import render_template, flash, redirect, url_for, request, send_from_directory, Response
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from urllib.parse import urlsplit
import os
import json
from werkzeug.utils import secure_filename
from flask import send_file

from app import db
from app.main import bp
from app.models import User, Bill, Chat
from app.main.forms import LoginForm, RegistrationForm, UploadForm, ChatForm, DirectFetchForm
from app.logic.ocr import extract_text_from_image, parse_bill_data
from app.logic.reasoning import analyze_bill
from app.logic.ai import generate_ai_response
from app.logic.generator import generate_complaint_docx
from app.logic.scraper import scrape_pitc_bill

@bp.route('/')
@bp.route('/index')
def index():
    return render_template('index.html', title='Home')

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

@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        f = form.bill_image.data
        filename = secure_filename(f.filename)
        from flask import current_app
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        f.save(filepath)
        
        # OCR Processing
        raw_text = extract_text_from_image(filepath)
        bill_data = parse_bill_data(raw_text)
        
        # Reason Detection
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
    return render_template('upload.html', title='Upload Bill', form=form)

@bp.route('/results/<int:bill_id>')
@login_required
def results(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    if bill.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Parse JSON string back to dict for the template
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

@bp.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    form = ChatForm()
    # Handle AJAX posts from JS
    if request.method == 'POST' and form.validate_on_submit():
        user_message = form.message.data
        
        # Save user message to DB
        chat_entry = Chat(user_id=current_user.id, message=user_message, response="")
        db.session.add(chat_entry)
        db.session.commit()
        
        # Get history (last 5 messages) for context
        history_query = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.timestamp.desc()).limit(5).all()
        history_query.reverse()
        
        chat_history = []
        for h in history_query[:-1]: # exclude the current one we just added
            if h.message:
                chat_history.append({"role": "user", "content": h.message})
            if h.response:
                chat_history.append({"role": "assistant", "content": h.response})
                
        # Call Groq API
        ai_response = generate_ai_response(user_message, chat_history)
        
        # Update DB with AI response
        chat_entry.response = ai_response
        db.session.commit()
        
        # If it's an AJAX request (fetch), return JSON
        if request.headers.get('Accept') == 'application/json':
            return {"status": "success", "response": ai_response, "message": user_message}
            
        return redirect(url_for('main.chat'))
        
    # Get all chat history for rendering the page
    chats = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.timestamp.asc()).all()
    return render_template('chat.html', title='AI Legal Chat', form=form, chats=chats)

@bp.route('/dashboard')
@login_required
def dashboard():
    bills = Bill.query.filter_by(user_id=current_user.id).order_by(Bill.created_at.desc()).all()
    return render_template('dashboard.html', title='Dashboard', bills=bills)

@bp.route('/robots.txt')
@bp.route('/sitemap.xml')
def static_from_root():
    from flask import current_app
    return send_from_directory(current_app.static_folder, request.path[1:])
