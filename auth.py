from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse
from models import User, db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = bool(request.form.get('remember'))
        
        print(f"Login attempt for user: {username}")
        user = User.query.filter_by(username=username).first()
        print(f"User found: {user is not None}")
        
        if user and check_password_hash(user.password_hash, password):
            print(f"Password check passed for user: {username}")
            login_user(user, remember=remember)
            print(f"User logged in, is_authenticated: {user.is_authenticated}")
            
            next_page = request.args.get('next')
            if next_page and urlparse(next_page).netloc == '':
                print(f"Redirecting to next page: {next_page}")
                flash(f'Hoş geldiniz, {user.username}!', 'success')
                return redirect(next_page)
            else:
                print("Redirecting to index page")
                flash(f'Hoş geldiniz, {user.username}!', 'success')
                return redirect(url_for('index'))
        else:
            print(f"Authentication failed for user: {username}")
            flash('Geçersiz kullanıcı adı veya şifre!', 'danger')
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_confirm = request.form['password_confirm']
        
        # Validation
        if password != password_confirm:
            flash('Şifreler eşleşmiyor!', 'danger')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Şifre en az 6 karakter olmalıdır!', 'danger')
            return render_template('register.html')
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten kullanılıyor!', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Bu e-posta adresi zaten kullanılıyor!', 'danger')
            return render_template('register.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'change_password':
            current_password = request.form['current_password']
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            
            if not check_password_hash(current_user.password_hash, current_password):
                flash('Mevcut şifreniz yanlış!', 'danger')
            elif new_password != confirm_password:
                flash('Yeni şifreler eşleşmiyor!', 'danger')
            elif len(new_password) < 6:
                flash('Yeni şifre en az 6 karakter olmalıdır!', 'danger')
            else:
                current_user.password_hash = generate_password_hash(new_password)
                db.session.commit()
                flash('Şifreniz başarıyla güncellendi!', 'success')
                return redirect(url_for('auth.profile'))
        
        elif action == 'update_info':
            username = request.form['username']
            email = request.form['email']
            
            # Check if username or email already exists (for other users)
            existing_user = User.query.filter(
                (User.username == username) | (User.email == email),
                User.id != current_user.id
            ).first()
            
            if existing_user:
                flash('Bu kullanıcı adı veya e-posta adresi zaten kullanılıyor!', 'danger')
            else:
                current_user.username = username
                current_user.email = email
                db.session.commit()
                flash('Bilgileriniz başarıyla güncellendi!', 'success')
                return redirect(url_for('auth.profile'))
    
    return render_template('profile.html')
