from datetime import datetime
from app import db
import secrets
import string
from flask_login import UserMixin
import bcrypt


def generate_session_code():
    """Generate unique 6-character session code"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationship with sessions
    sessions = db.relationship('Session', backref='creator', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        salt = bcrypt.gensalt(rounds=12) 
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'total_sessions': len(self.sessions)
        }


# UPDATE Session Model - tambahkan foreign key
class Session(db.Model):
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  
    code = db.Column(db.String(6), unique=True, nullable=False, default=generate_session_code)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    current_slide_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    polls = db.relationship('Poll', backref='session', lazy=True, cascade='all, delete-orphan')
    participants = db.relationship('Participant', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'creator_name': self.creator.username if self.creator else None,  
            'code': self.code,
            'title': self.title,
            'description': self.description,
            'is_active': self.is_active,
            'current_slide_index': self.current_slide_index,
            'total_polls': len(self.polls),
            'created_at': self.created_at.isoformat()
        }
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False, default=generate_session_code)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    current_slide_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    polls = db.relationship('Poll', backref='session', lazy=True, cascade='all, delete-orphan')
    participants = db.relationship('Participant', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'title': self.title,
            'description': self.description,
            'is_active': self.is_active,
            'current_slide_index': self.current_slide_index,
            'total_polls': len(self.polls),
            'created_at': self.created_at.isoformat()
        }

class Poll(db.Model):
    __tablename__ = 'polls'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    slide_number = db.Column(db.Integer, nullable=False)
    question = db.Column(db.Text, nullable=False)
    poll_type = db.Column(db.String(50), nullable=False)  # multiple_choice, rating_scale, open_ended
    options = db.Column(db.JSON)  # Store options as JSON array
    
    # Settings
    allow_multiple = db.Column(db.Boolean, default=False)
    anonymous = db.Column(db.Boolean, default=True)
    show_results = db.Column(db.Boolean, default=True)
    image_url = db.Column(db.String(500), nullable=True)

    # Relationships
    votes = db.relationship('Vote', backref='poll', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'slide_number': self.slide_number,
            'question': self.question,
            'poll_type': self.poll_type,
            'options': self.options,
            'image_url': self.image_url,
            'settings': {
                'allow_multiple': self.allow_multiple,
                'anonymous': self.anonymous,
                'show_results': self.show_results
            },
            'total_votes': len(self.votes)
        }
    
    def get_results(self):
        """Calculate vote distribution"""
        from collections import Counter
        
        if self.poll_type in ['multiple_choice', 'rating_scale']:
            # Initialize with all options at 0
            results = {option: 0 for option in self.options}
            for vote in self.votes:
                if vote.answer in results:
                    results[vote.answer] += 1
            return results
        
        elif self.poll_type == 'word_cloud':
            # Count word frequency for word cloud
            all_words = [vote.answer.strip().lower() for vote in self.votes if vote.answer.strip()]
            word_counts = Counter(all_words)
            return dict(word_counts)  # Return {word: count}
        
        else:  # open_ended
            # Return list of all answers for open-ended questions
            return [vote.answer for vote in self.votes]

class Participant(db.Model):
    __tablename__ = 'participants'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    identifier = db.Column(db.String(50), unique=True, nullable=False)  # Socket ID or generated ID
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_online = db.Column(db.Boolean, default=True)
    
    # Relationships
    votes = db.relationship('Vote', backref='participant', lazy=True, cascade='all, delete-orphan')

class Vote(db.Model):
    __tablename__ = 'votes'
    
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('participants.id'), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint: one vote per participant per poll
    __table_args__ = (db.UniqueConstraint('poll_id', 'participant_id', name='_poll_participant_uc'),)
