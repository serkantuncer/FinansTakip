#!/usr/bin/env python3
from werkzeug.security import generate_password_hash
from models import db, User
from app import app

def create_admin_user():
    with app.app_context():
        # Check if admin user already exists
        existing_admin = User.query.filter_by(username='admin').first()
        if existing_admin:
            print("Admin user already exists")
            return
        
        # Create admin user with hashed password
        password_hash = generate_password_hash('admin123')
        admin_user = User(
            username='admin',
            email='admin@example.com',
            password_hash=password_hash
        )
        
        db.session.add(admin_user)
        db.session.commit()
        print("Admin user created successfully: admin/admin123")

if __name__ == '__main__':
    create_admin_user()