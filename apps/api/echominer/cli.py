"""Operational CLI: `python -m echominer.cli create-admin --email … --password …`"""
import argparse
import sys

from sqlalchemy import func, select

from .config import get_settings
from .models import Admin
from .db import SessionLocal, create_all
from .security import new_totp_secret
from .services.admin import AdminService


def create_admin(args) -> None:
    with SessionLocal() as db:
        service = AdminService(db, get_settings())
        secret = None if args.no_totp else new_totp_secret()
        admin = service.create_admin(email=args.email, password=args.password, totp_secret=secret)
        db.commit()
        print(f"admin created: {admin.email}")
        if secret:
            print(f"TOTP secret (enrol now, it is not shown again): {secret}")
            print(f"otpauth://totp/EchoMiner:{admin.email}?secret={secret}&issuer=EchoMiner")


def bootstrap_admin(_args=None) -> None:
    """Hosts without a shell (Render free tier) cannot run create-admin by hand.
    On start-up, if ADMIN_BOOTSTRAP_EMAIL/PASSWORD are set and no administrator
    exists yet, create one and print its authenticator enrolment once."""
    settings = get_settings()
    if not (settings.admin_bootstrap_email and settings.admin_bootstrap_password):
        return
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Admin)):
            print("bootstrap-admin: an administrator already exists; nothing to do. "
                  "Remove ADMIN_BOOTSTRAP_* from the environment.", flush=True)
            return
        service = AdminService(db, settings)
        secret = new_totp_secret()
        admin = service.create_admin(email=settings.admin_bootstrap_email,
                                     password=settings.admin_bootstrap_password, totp_secret=secret)
        db.commit()
    print("=" * 72, flush=True)
    print(f"bootstrap-admin: created administrator {admin.email}", flush=True)
    print("Add this to an authenticator app NOW (shown once):", flush=True)
    print(f"  setup key: {secret}", flush=True)
    print(f"  otpauth://totp/EchoMiner:{admin.email}?secret={secret}&issuer=EchoMiner", flush=True)
    print("Then delete ADMIN_BOOTSTRAP_EMAIL and ADMIN_BOOTSTRAP_PASSWORD from the environment.",
          flush=True)
    print("=" * 72, flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="echominer")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-admin")
    create.add_argument("--email", required=True)
    create.add_argument("--password", required=True)
    create.add_argument("--no-totp", action="store_true",
                        help="skip TOTP enrolment (not recommended outside development)")
    create.set_defaults(func=create_admin)

    boot = sub.add_parser("bootstrap-admin",
                          help="create the first admin from ADMIN_BOOTSTRAP_* if none exists")
    boot.set_defaults(func=bootstrap_admin)

    init = sub.add_parser("init-db", help="create tables (development only; production uses Alembic)")
    init.set_defaults(func=lambda _: (create_all(), print("schema created")))

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
