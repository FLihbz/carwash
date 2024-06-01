from app import db, User, app

with app.app_context():
    db.create_all()  # Create tables for all models
    admin_user = User(username='admin', password='adminpassword', role='admin')
    db.session.add(admin_user)
    db.session.commit()
    print("Admin user created successfully")
