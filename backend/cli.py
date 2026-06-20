import argparse
import sys
from backend.core.database import SessionLocal
from backend.core.models import User
from backend.core.auth import get_password_hash

def create_admin(email, password, db=None):
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.is_admin = True
            user.password_hash = get_password_hash(password)
            db.commit()
            print(f"Korisnik {email} je promovisan u administratora i lozinka mu je ažurirana.")
        else:
            hashed_pwd = get_password_hash(password)
            new_admin = User(email=email, password_hash=hashed_pwd, is_admin=True)
            db.add(new_admin)
            db.commit()
            print(f"Novi nalog {email} je kreiran i promovisan u administratora.")
    except Exception as e:
        db.rollback()
        print(f"Greška pri kreiranju administratora: {e}", file=sys.stderr)
        if should_close:
            sys.exit(1)
        raise e
    finally:
        if should_close:
            db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI za administraciju sinhronizuj.me")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin_parser = subparsers.add_parser("create_admin", help="Kreiraj ili promovisi administratora")
    create_admin_parser.add_argument("--email", required=True, help="Email adresa administratora")
    create_admin_parser.add_argument("--password", required=True, help="Lozinka administratora")

    args = parser.parse_args()

    if args.command == "create_admin":
        create_admin(args.email, args.password)
