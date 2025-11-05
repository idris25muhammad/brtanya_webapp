from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models import Session, Poll, Vote, Participant

participant_bp = Blueprint('participant', __name__)

@participant_bp.route('/')
@participant_bp.route('/join')
def join():
    """Render participant join page"""
    session_code = request.args.get('code', '')
    return render_template('participant/join.html', session_code=session_code)

@participant_bp.route('/api/join', methods=['POST'])
def join_session():
    """Join a polling session"""
    data = request.json
    session_code = data.get('session_code')
    
    poll_session = Session.query.filter_by(code=session_code, is_active=True).first()
    
    if not poll_session:
        return jsonify({'error': 'Invalid or inactive session'}), 404
    
    return jsonify({
        'success': True,
        'session': poll_session.to_dict()
    })

@participant_bp.route('/api/vote', methods=['POST'])
def submit_vote():
    """Submit a vote"""
    data = request.json
    
    poll_id = data.get('poll_id')
    participant_id = data.get('participant_id')
    answer = data.get('answer')
    
    # Check if already voted
    existing_vote = Vote.query.filter_by(
        poll_id=poll_id,
        participant_id=participant_id
    ).first()
    
    if existing_vote:
        return jsonify({'error': 'Already voted'}), 400
    
    # Create vote
    vote = Vote(
        poll_id=poll_id,
        participant_id=participant_id,
        answer=answer
    )
    db.session.add(vote)
    db.session.commit()
    
    # Emit socket event for real-time update
    from app import socketio
    poll = Poll.query.get(poll_id)
    
    socketio.emit('new_vote', {
        'poll_id': poll_id,
        'answer': answer,
        'results': poll.get_results()
    }, room=poll.session.code)
    
    return jsonify({'success': True})
