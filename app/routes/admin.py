# app/routes/admin.py

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Session, Poll, Vote, Participant
import qrcode
import io
import base64
from datetime import datetime
import random
import string
from app.models import User
from werkzeug.utils import secure_filename
import os
import uuid

admin_bp = Blueprint('admin', __name__)

# Configuration for file uploads
UPLOAD_FOLDER = 'app/static/uploads/polls'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_code(length=6):
    """Generate random session code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ========== PAGES ==========

@admin_bp.route('/')
@admin_bp.route('/poll')
@login_required  
def poll():
    """Admin index page - list all sessions"""
    return render_template('admin/poll.html')

@admin_bp.route('/session/create')
@login_required  
def create_session_page():
    """Render create multi-slide poll page"""
    return render_template('admin/create_session.html')

@admin_bp.route('/dashboard/<session_code>')
@login_required
def dashboard(session_code):
    """Render live dashboard"""
    poll_session = Session.query.filter_by(code=session_code).first_or_404()
    
    # Check ownership (user can only access their own sessions, unless admin)
    if poll_session.user_id != current_user.id and not current_user.is_admin:
        return "Unauthorized - Anda tidak memiliki akses ke session ini", 403
    
    return render_template('admin/live_dashboard.html', session=poll_session)

# ========== USER MANAGEMENT (Server-Side) ==========
@admin_bp.route('/users', methods=['GET', 'POST'])
@login_required
def users_management():
    """User management page (admin only)"""
    if not current_user.is_admin:
        flash('Unauthorized access', 'error')
        return redirect(url_for('admin.poll'))
    
    # Handle POST for add/edit
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            full_name = request.form.get('full_name')
            is_admin = request.form.get('is_admin') == 'on'
            is_active = request.form.get('is_active') == 'on'
            
            # Validation
            if User.query.filter_by(username=username).first():
                flash('Username sudah digunakan', 'error')
            elif User.query.filter_by(email=email).first():
                flash('Email sudah terdaftar', 'error')
            else:
                new_user = User(
                    username=username,
                    email=email,
                    full_name=full_name,
                    is_admin=is_admin,
                    is_active=is_active
                )
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                flash(f'✅ User {username} berhasil dibuat!', 'success')
        
        elif action == 'edit':
            user_id = request.form.get('user_id')
            user = User.query.get_or_404(user_id)
            
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            full_name = request.form.get('full_name')
            is_admin = request.form.get('is_admin') == 'on'
            is_active = request.form.get('is_active') == 'on'
            
            # Check uniqueness
            error = False
            if username != user.username and User.query.filter_by(username=username).first():
                flash('Username sudah digunakan', 'error')
                error = True
            elif email != user.email and User.query.filter_by(email=email).first():
                flash('Email sudah terdaftar', 'error')
                error = True
            
            if not error:
                user.username = username
                user.email = email
                user.full_name = full_name
                user.is_admin = is_admin
                user.is_active = is_active
                
                if password:
                    user.set_password(password)
                
                db.session.commit()
                flash(f'✅ User {username} berhasil diupdate!', 'success')
        
        elif action == 'delete':
            user_id = request.form.get('user_id')
            if int(user_id) == current_user.id:
                flash('❌ Tidak bisa menghapus akun sendiri!', 'error')
            else:
                user = User.query.get_or_404(user_id)
                username = user.username
                db.session.delete(user)
                db.session.commit()
                flash(f'✅ User {username} berhasil dihapus!', 'success')
        
        return redirect(url_for('admin.users_management'))
    
    # GET - show page with all users
    users = User.query.order_by(User.created_at.desc()).all()
    
    total_users = len(users)
    active_users = sum(1 for u in users if u.is_active)
    total_admins = sum(1 for u in users if u.is_admin)
    
    return render_template('admin/users.html', 
                         users=users,
                         total_users=total_users,
                         active_users=active_users,
                         total_admins=total_admins)

# ========== API: SESSIONS MANAGEMENT ==========

@admin_bp.route('/api/sessions', methods=['POST'])
@login_required  
def create_session_api():
    """Create new polling session with multiple slides and image uploads"""
    try:
        # Check if request is JSON or FormData
        if request.is_json:
            # Original JSON handling (no images)
            data = request.json
            slides_data = data.get('slides', [])
        else:
            # FormData handling (with images)
            data = {
                'title': request.form.get('title'),
                'description': request.form.get('description'),
            }
            slides_json = request.form.get('slides')
            if not slides_json:
                return jsonify({'success': False, 'error': 'No slides data provided'}), 400
            
            import json
            slides_data = json.loads(slides_json)
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({'success': False, 'error': 'Title is required'}), 400
        
        # Generate unique code
        code = generate_code()
        while Session.query.filter_by(code=code).first():
            code = generate_code()
        
        # Create session
        new_session = Session(
            user_id=current_user.id,
            title=data.get('title'),
            description=data.get('description'),
            code=code,
            is_active=False,
            current_slide_index=0
        )
        db.session.add(new_session)
        db.session.flush()  # Get session ID before creating polls
        
        # Create polls for each slide
        for idx, slide_data in enumerate(slides_data):
            image_url = None
            
            # Handle image upload for this slide
            if not request.is_json:  # Only process files if FormData
                file_key = f'slide_{idx}_image'
                if file_key in request.files:
                    file = request.files[file_key]
                    
                    # Validate file
                    if file and file.filename and allowed_file(file.filename):
                        # Check file size
                        file.seek(0, os.SEEK_END)
                        file_size = file.tell()
                        file.seek(0)  # Reset pointer
                        
                        if file_size > MAX_FILE_SIZE:
                            return jsonify({
                                'success': False, 
                                'error': f'Image for slide {idx + 1} exceeds 5MB limit'
                            }), 400
                        
                        # Generate unique filename
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        unique_filename = f"{code}_slide_{idx}_{uuid.uuid4().hex[:8]}.{ext}"
                        
                        # Save file
                        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                        file.save(filepath)
                        
                        # Store relative URL for database
                        image_url = f'/static/uploads/polls/{unique_filename}'
            
            # Create poll
            poll = Poll(
                session_id=new_session.id,
                slide_number=slide_data.get('slideNumber'),
                question=slide_data.get('question'),
                poll_type=slide_data.get('type'),
                options=slide_data.get('options', []),
                allow_multiple=slide_data.get('settings', {}).get('allowMultiple', False),
                anonymous=slide_data.get('settings', {}).get('anonymous', True),
                show_results=slide_data.get('settings', {}).get('showResults', True),
                image_url=image_url  # Add image URL to poll
            )
            db.session.add(poll)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'session': new_session.to_dict(),
            'session_code': code,
            'message': 'Session created successfully'
        }), 201
    
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@admin_bp.route('/api/sessions/all')
@login_required  
def get_all_sessions():
    """Get all sessions with statistics - filtered by user"""
    # Admin bisa lihat semua, user biasa hanya miliknya
    if current_user.is_admin:
        sessions = Session.query.order_by(Session.created_at.desc()).all()
    else:
        sessions = Session.query.filter_by(user_id=current_user.id).order_by(Session.created_at.desc()).all()
    
    sessions_data = []
    total_participants = 0
    total_votes = 0
    active_count = 0
    
    for sess in sessions:
        participant_count = Participant.query.filter_by(
            session_id=sess.id, 
            is_online=True
        ).count()
        vote_count = Vote.query.join(Poll).filter(
            Poll.session_id == sess.id
        ).count()
        
        total_participants += participant_count
        total_votes += vote_count
        if sess.is_active:
            active_count += 1
        
        session_dict = sess.to_dict()
        session_dict['participant_count'] = participant_count
        session_dict['vote_count'] = vote_count
        session_dict['poll_count'] = len(sess.polls)
        sessions_data.append(session_dict)
    
    return jsonify({
        'sessions': sessions_data,
        'stats': {
            'total': len(sessions),
            'active': active_count,
            'participants': total_participants,
            'votes': total_votes
        }
    })

@admin_bp.route('/api/sessions/<session_code>')
@login_required  
def get_session(session_code):
    """Get session details with all polls and status"""
    poll_session = Session.query.filter_by(code=session_code).first_or_404()
    
    # Check ownership
    if poll_session.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    polls_data = []
    for poll in sorted(poll_session.polls, key=lambda x: x.slide_number):
        poll_dict = poll.to_dict()
        results = poll.get_results()
        poll_dict['results'] = results if results else {}
        polls_data.append(poll_dict)
    
    session_data = poll_session.to_dict()
    session_data['polls'] = polls_data
    session_data['participant_count'] = Participant.query.filter_by(
        session_id=poll_session.id, 
        is_online=True
    ).count()
    session_data['is_active'] = poll_session.is_active
    session_data['current_slide'] = poll_session.current_slide_index
    
    return jsonify(session_data)

@admin_bp.route('/api/sessions/<int:session_id>', methods=['DELETE'])
@login_required  
def delete_session(session_id):
    """Delete a session and all related data"""
    sess = Session.query.get_or_404(session_id)
    
    # Check ownership
    if sess.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Delete associated images
        for poll in sess.polls:
            if poll.image_url:
                try:
                    # Extract filename from URL
                    filename = poll.image_url.split('/')[-1]
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as e:
                    print(f"Error deleting image: {e}")
        
        db.session.delete(sess)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Session deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== API: SESSION CONTROLS ==========

@admin_bp.route('/api/sessions/<session_code>/toggle', methods=['PUT'])
@login_required  
def toggle_session(session_code):
    """Toggle session active status (Start/Pause)"""
    try:
        poll_session = Session.query.filter_by(code=session_code).first_or_404()
        
        # Check ownership
        if poll_session.user_id != current_user.id and not current_user.is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Toggle status
        poll_session.is_active = not poll_session.is_active
        
        # Update timestamp
        if poll_session.is_active:
            poll_session.started_at = datetime.utcnow()
        
        db.session.commit()
        
        # Emit socket event
        from app import socketio
        socketio.emit('session_status_changed', {
            'is_active': poll_session.is_active,
            'message': 'Session started' if poll_session.is_active else 'Session paused'
        }, room=session_code)
        
        return jsonify({
            'success': True,
            'is_active': poll_session.is_active,
            'message': 'Session started' if poll_session.is_active else 'Session paused'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@admin_bp.route('/api/sessions/<session_code>/end', methods=['PUT'])
@login_required  
def end_session(session_code):
    """End session - set is_active to False"""
    try:
        poll_session = Session.query.filter_by(code=session_code).first_or_404()
        
        # Check ownership
        if poll_session.user_id != current_user.id and not current_user.is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Set session as inactive
        poll_session.is_active = False
        poll_session.ended_at = datetime.utcnow()
        
        db.session.commit()
        
        # Emit socket event to all participants
        from app import socketio
        socketio.emit('session_ended', {
            'message': 'Session has ended. Thank you for participating!'
        }, room=session_code)
        
        return jsonify({
            'success': True,
            'message': 'Session ended successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@admin_bp.route('/api/sessions/<session_code>/slide', methods=['PUT'])
@login_required  
def change_slide(session_code):
    """Change current slide and notify participants"""
    try:
        poll_session = Session.query.filter_by(code=session_code).first_or_404()
        
        # Check ownership
        if poll_session.user_id != current_user.id and not current_user.is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.json
        new_slide_index = data.get('slide_index', 0)
        poll_session.current_slide_index = new_slide_index
        db.session.commit()
        
        # Get current poll
        current_poll = None
        if poll_session.polls:
            sorted_polls = sorted(poll_session.polls, key=lambda x: x.slide_number)
            if new_slide_index < len(sorted_polls):
                current_poll = sorted_polls[new_slide_index]
        
        # Emit socket event to participants
        from app import socketio
        socketio.emit('slide_changed', {
            'slide_index': new_slide_index,
            'poll': current_poll.to_dict() if current_poll else None
        }, room=session_code)
        
        return jsonify({
            'success': True,
            'slide_index': new_slide_index,
            'poll': current_poll.to_dict() if current_poll else None
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

# ========== API: QR CODE ==========

@admin_bp.route('/api/qrcode/<session_code>')
@login_required  
def generate_qr(session_code):
    """Generate QR code for session join URL"""
    try:
        # Verify session exists & check ownership
        sess = Session.query.filter_by(code=session_code).first_or_404()
        
        if sess.user_id != current_user.id and not current_user.is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        join_url = request.host_url + f'join?code={session_code}'
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4
        )
        qr.add_data(join_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="#7c3aed", back_color="white")
        
        # Convert to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return jsonify({
            'success': True,
            'qr_code': f'data:image/png;base64,{img_str}',
            'join_url': join_url
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ========== API: STATISTICS ==========

@admin_bp.route('/api/dashboard/stats')
@login_required  
def dashboard_stats():
    """Get dashboard statistics for overview - filtered by user"""
    # Filter by user
    if current_user.is_admin:
        sessions_query = Session.query
    else:
        sessions_query = Session.query.filter_by(user_id=current_user.id)
    
    total_sessions = sessions_query.count()
    active_sessions = sessions_query.filter_by(is_active=True).count()
    
    # Get participant & vote counts from user's sessions only
    user_session_ids = [s.id for s in sessions_query.all()]
    total_participants = Participant.query.filter(
        Participant.session_id.in_(user_session_ids),
        Participant.is_online == True
    ).count() if user_session_ids else 0
    
    total_votes = db.session.query(Vote).join(Poll).filter(
        Poll.session_id.in_(user_session_ids)
    ).count() if user_session_ids else 0
    
    # Recent sessions
    recent_sessions = sessions_query.order_by(
        Session.created_at.desc()
    ).limit(5).all()
    
    recent_data = []
    for sess in recent_sessions:
        session_dict = sess.to_dict()
        session_dict['total_polls'] = len(sess.polls)
        session_dict['participant_count'] = Participant.query.filter_by(
            session_id=sess.id
        ).count()
        recent_data.append(session_dict)
    
    return jsonify({
        'stats': {
            'total': total_sessions,
            'active': active_sessions,
            'participants': total_participants,
            'votes': total_votes
        },
        'recent_sessions': recent_data
    })
