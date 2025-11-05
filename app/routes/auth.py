# app/routes/auth.py

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from datetime import datetime

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('admin.poll'))
    
    if request.method == 'POST':
        # Support both JSON and Form data
        data = request.json if request.is_json else request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember = bool(data.get('remember', False))
        
        # Validate input
        if not username or not password:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Username dan password harus diisi'}), 400
            flash('Username dan password harus diisi', 'error')
            return render_template('auth/login.html')
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        # Debug logging (remove in production)
        print(f"🔍 Login attempt: username={username}")
        if user:
            print(f"✅ User found: {user.username} | Active: {user.is_active} | Admin: {user.is_admin}")
        else:
            print(f"❌ User not found: {username}")
        
        # Check user exists and password is correct
        if user and user.check_password(password):
            print(f"✅ Password verified for: {username}")
            
            # Check if user is active
            if not user.is_active:
                print(f"⚠️ User inactive: {username}")
                if request.is_json:
                    return jsonify({'success': False, 'error': 'Akun Anda tidak aktif'}), 403
                flash('Akun Anda tidak aktif. Hubungi administrator.', 'error')
                return render_template('auth/login.html')
            
            # Login user
            try:
                login_user(user, remember=remember)
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                print(f"✅ Login successful: {username}")
                
                # Redirect
                next_page = request.args.get('next')
                redirect_url = next_page or url_for('admin.poll')
                
                if request.is_json:
                    return jsonify({
                        'success': True,
                        'message': 'Login berhasil',
                        'redirect': redirect_url
                    })
                
                flash(f'Selamat datang, {user.full_name or user.username}!', 'success')
                return redirect(redirect_url)
                
            except Exception as e:
                print(f"❌ Login error: {str(e)}")
                db.session.rollback()
                if request.is_json:
                    return jsonify({'success': False, 'error': 'Terjadi kesalahan sistem'}), 500
                flash('Terjadi kesalahan saat login. Silakan coba lagi.', 'error')
                return render_template('auth/login.html')
        
        # Invalid credentials
        print(f"❌ Invalid credentials for: {username}")
        if request.is_json:
            return jsonify({'success': False, 'error': 'Username atau password salah'}), 401
        flash('Username atau password salah', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout user"""
    username = current_user.username
    print(f"👋 Logout: {username}")
    
    logout_user()
    flash('Anda telah logout', 'info')
    return redirect(url_for('auth.login'))