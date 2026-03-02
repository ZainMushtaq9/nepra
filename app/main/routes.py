from flask import render_template, flash, redirect, url_for, request, send_from_directory
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from urllib.parse import urlsplit
import os
import json
from werkzeug.utils import secure_filename

from app import db
from app.main import bp
from app.models import User, Bill
from app.main.forms import LoginForm, RegistrationForm, UploadForm
from app.logic.ocr import extract_text_from_image, parse_bill_data
from app.logic.reasoning import analyze_bill

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
        # return redirect(url_for('main.results', bill_id=bill.id)) 
        return redirect(url_for('main.index'))
    return render_template('upload.html', title='Upload Bill', form=form)

@bp.route('/robots.txt')
@bp.route('/sitemap.xml')
def static_from_root():
    from flask import current_app
    return send_from_directory(current_app.static_folder, request.path[1:])
