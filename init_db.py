from app import create_app, db
from app.models import User
import os
import bcrypt
from datetime import datetime

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@brtanya.local")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "rahasia123")
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", 12))

app = create_app()

def ensure_admin():
    existing = User.query.filter(
        (User.email == ADMIN_EMAIL) | (User.username == ADMIN_USERNAME)
    ).first()
    if existing:
        print("Admin sudah ada, skip insert.")
        return

    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    pw_hash = bcrypt.hashpw(ADMIN_PASSWORD.encode('utf-8'), salt).decode('utf-8')

    admin = User(
        username=ADMIN_USERNAME,
        email=ADMIN_EMAIL,
        password_hash=pw_hash,
        full_name="Administrator",
        is_admin=True,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.session.add(admin)
    db.session.commit()
    print(f"Akun admin dibuat: {ADMIN_USERNAME} / {ADMIN_EMAIL}")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Database initialized successfully!")
        ensure_admin()