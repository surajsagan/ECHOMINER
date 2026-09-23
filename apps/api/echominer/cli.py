"""Operational CLI: `python -m echominer.cli create-admin --email … --password …`"""
import argparse
import sys

from .config import get_settings
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="echominer")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-admin")
    create.add_argument("--email", required=True)
    create.add_argument("--password", required=True)
    create.add_argument("--no-totp", action="store_true",
                        help="skip TOTP enrolment (not recommended outside development)")
    create.set_defaults(func=create_admin)

    init = sub.add_parser("init-db", help="create tables (development only; production uses Alembic)")
    init.set_defaults(func=lambda _: (create_all(), print("schema created")))

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
