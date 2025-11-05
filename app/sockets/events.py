from flask_socketio import emit, join_room, leave_room
from app import socketio, db
from app.models import Session, Participant, Poll
import secrets

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connected', {'message': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_session')
def handle_join_session(data):
    """Participant joins a session room"""
    session_code = data.get('session_code')
    
    poll_session = Session.query.filter_by(code=session_code).first()
    if not poll_session:
        emit('error', {'message': 'Invalid session'})
        return
    
    # Create participant
    participant_id = secrets.token_hex(8)
    participant = Participant(
        session_id=poll_session.id,
        identifier=participant_id
    )
    db.session.add(participant)
    db.session.commit()
    
    # Join room
    join_room(session_code)
    
    # Send current poll
    current_poll = Poll.query.filter_by(
        session_id=poll_session.id,
        slide_number=poll_session.current_slide_index + 1
    ).first()
    
    emit('session_joined', {
        'participant_id': participant.id,
        'participant_identifier': participant_id,
        'current_slide': poll_session.current_slide_index,
        'total_slides': len(poll_session.polls),
        'current_poll': current_poll.to_dict() if current_poll else None
    })
    
    # Notify admin of new participant
    emit('participant_joined', {
        'count': Participant.query.filter_by(session_id=poll_session.id, is_online=True).count()
    }, room=session_code)

@socketio.on('admin_join')
def handle_admin_join(data):
    """Admin joins session room for monitoring"""
    session_code = data.get('session_code')
    join_room(session_code)
    emit('admin_connected', {'message': 'Monitoring session'})

@socketio.on('leave_session')
def handle_leave_session(data):
    """Participant leaves session"""
    session_code = data.get('session_code')
    participant_id = data.get('participant_id')
    
    participant = Participant.query.get(participant_id)
    if participant:
        participant.is_online = False
        db.session.commit()
    
    leave_room(session_code)
    
    poll_session = Session.query.filter_by(code=session_code).first()
    if poll_session:
        emit('participant_left', {
            'count': Participant.query.filter_by(session_id=poll_session.id, is_online=True).count()
        }, room=session_code)
