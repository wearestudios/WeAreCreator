#!/usr/bin/env python3
"""Why won't the admin log in? — a read-only look at the production database.

Admin sign-in is the one account that uses email + password (creators and
brands are WhatsApp OTP only), and it is seeded from the environment on
startup. That seed is **create-only**: if a user document already exists for
ADMIN_EMAIL, a later change to ADMIN_PASSWORD does nothing at all. That single
fact explains most "the password in Railway is definitely right" reports.

This script answers, in order:

  1. Is there a user document for the address at all?
  2. If so: what role and status does it carry, and does it have a password
     hash? (The hash itself is never printed — only its shape.)
  3. Does a password you supply actually verify against that stored hash?
  4. Which accounts in this database have role "admin"? — in case one was
     seeded under a different address and the one you are typing was never
     created.

It **only reads.** There is no code path here that writes, updates or deletes
anything; you can run it against production without taking a backup first.

Usage:

    cd backend
    pip install -r requirements.txt          # needs pymongo + bcrypt
    MONGO_URL='mongodb://...' DB_NAME='...' python diagnose_admin_login.py

The address defaults to ADMIN_EMAIL if that is set, or pass one:

    python diagnose_admin_login.py creator@wearemonk.in

The password is asked for on a prompt rather than taken from an argument, so
it does not land in your shell history or in the output of `ps`. Press Enter
to skip the check.
"""
import os
import re
import sys
from getpass import getpass

try:
    import bcrypt
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError as exc:  # pragma: no cover - a setup problem, not a bug
    sys.exit(
        f"Missing a dependency ({exc.name}). Run this from backend/ after:\n"
        "    pip install -r requirements.txt"
    )

# The server does this to both the seeded address and the submitted one, so a
# diagnostic that skipped it would report a mismatch the app does not have.
def normalise(email: str) -> str:
    return email.lower().strip()


def describe_hash(raw) -> str:
    """Say enough about a stored hash to diagnose it, without printing it.

    The prefix and cost are the diagnostic part — `$2b$12$` means bcrypt at
    cost 12. The salt and digest that follow are the secret part and never
    appear. A value that is not bcrypt at all is the interesting finding here,
    so it is named as such rather than dismissed as "present".
    """
    if raw is None:
        return "ABSENT — the document has no password_hash field"
    if not isinstance(raw, str):
        return f"PRESENT but not a string (stored as {type(raw).__name__}) — this cannot verify"
    if not raw:
        return "PRESENT but empty — this cannot verify"
    match = re.match(r"^(\$2[abxy]\$)(\d{2})\$", raw)
    if not match:
        return (
            f"PRESENT ({len(raw)} chars) but NOT a bcrypt hash — it does not start "
            "with $2a$/$2b$/$2x$/$2y$. Something other than hash_password() wrote it."
        )
    return f"PRESENT — bcrypt, prefix {match.group(1)}, cost {int(match.group(2))}, {len(raw)} chars"


def verify(password: str, stored: str):
    """(result, explanation). Never raises — a malformed hash is a finding."""
    if not isinstance(stored, str) or not stored:
        return None, "no usable hash stored, so there is nothing to verify against"
    if len(password.encode("utf-8")) > 72:
        return None, (
            f"the password you supplied is {len(password.encode('utf-8'))} bytes; bcrypt "
            "refuses anything over 72. If ADMIN_PASSWORD is this long, the seed "
            "raised a ValueError on startup and no admin was ever created."
        )
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8")), ""
    except ValueError as exc:
        return None, f"the stored hash is not valid bcrypt ({exc})"


def rule(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


def main() -> int:
    mongo_url = os.environ.get("MONGO_URL", "").strip()
    db_name = os.environ.get("DB_NAME", "").strip()
    if not mongo_url or not db_name:
        return print_usage_error()

    wanted_raw = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ADMIN_EMAIL", "")
    if not wanted_raw.strip():
        return print_usage_error("No address given and ADMIN_EMAIL is not set.")
    wanted = normalise(wanted_raw)

    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
        client.admin.command("ping")
    except PyMongoError as exc:
        print(f"Could not connect: {exc}", file=sys.stderr)
        print(
            "\nIf the URL starts with mongodb+srv:// you also need dnspython:\n"
            "    pip install 'pymongo[srv]'",
            file=sys.stderr,
        )
        return 2

    db = client[db_name]

    # Connecting to the wrong database is a real possibility and looks exactly
    # like a missing account, so establish which one we are in before anything
    # is concluded from an absence.
    rule("0. Which database is this?")
    total = db.users.count_documents({})
    print(f"  DB_NAME               {db_name}")
    print(f"  users collection      {total} document(s)")
    if total == 0:
        print(
            "\n  This database has no users at all. Either DB_NAME does not match what\n"
            "  the deployed app uses, or you are pointed at the wrong cluster. Nothing\n"
            "  below will mean anything until that is settled."
        )
        collections = [c for c in db.list_collection_names()]
        print(f"  collections here      {', '.join(sorted(collections)) or '(none)'}")
        others = [n for n in client.list_database_names() if n not in ("admin", "local", "config")]
        print(f"  other databases       {', '.join(others) or '(none)'}")
        return 1

    # --- 1. Does the document exist? -----------------------------------------
    rule(f"1. Is there a user document for {wanted}?")
    user = db.users.find_one({"email": wanted})
    print(f"  exact match on '{wanted}': {'YES' if user else 'NO'}")

    # The app looks it up with an exact match on the normalised address, so a
    # row stored with different casing or a stray space is invisible to login
    # while looking perfectly correct in Compass. Worth catching explicitly.
    near = [
        d
        for d in db.users.find(
            {"email": {"$regex": f"^\\s*{re.escape(wanted)}\\s*$", "$options": "i"}}
        )
        if d.get("email") != wanted
    ]
    if near:
        print("\n  Found near-miss document(s) that login can never match:")
        for d in near:
            print(f"    stored as {d.get('email')!r}  role={d.get('role')!r}")
        print(
            "  The server looks up email.lower().strip() with an exact match, so a\n"
            "  stored address that differs by case or whitespace will always 401."
        )

    if user is None:
        print(
            "\n  → No account exists for this address. See section 4 for which admin\n"
            "    accounts do exist. If the list is empty, the seed never ran: it is\n"
            "    skipped when ADMIN_EMAIL or ADMIN_PASSWORD is unset at boot."
        )

    # --- 2. What does it look like? ------------------------------------------
    if user is not None:
        rule("2. What state is that account in?")
        role = user.get("role")
        status = user.get("status")
        print(f"  _id                   {user.get('_id')}")
        print(f"  email                 {user.get('email')!r}")
        print(f"  name                  {user.get('name')!r}")
        print(f"  role                  {role!r}")
        print(f"  status                {status!r}")
        print(f"  password_hash         {describe_hash(user.get('password_hash'))}")
        print(f"  created_at            {user.get('created_at')}")

        if role not in ("admin", "campaign_manager"):
            print(
                f"\n  → role is {role!r}. POST /api/auth/login accepts only 'admin' and\n"
                "    'campaign_manager'; anything else is refused with 403 'Please sign in\n"
                "    with your WhatsApp number' — note that is a 403, not a 401, so if you\n"
                "    are seeing 'Invalid email or password' this is NOT your cause."
            )
        if status not in (None, "active"):
            print(
                f"\n  → status is {status!r}. For the record, /auth/login does not check\n"
                "    status, so this does not block sign-in by itself."
            )

    # --- 3. Does a password verify? ------------------------------------------
    rule("3. Does a password verify against the stored hash?")
    if user is None:
        print("  Skipped — there is no document to check against.")
    else:
        supplied = os.environ.get("CHECK_PASSWORD")
        if supplied is None:
            supplied = getpass("  Password to test (input hidden, Enter to skip): ")
        if not supplied:
            print("  Skipped.")
        else:
            result, why = verify(supplied, user.get("password_hash"))
            if result is None:
                print(f"  INCONCLUSIVE — {why}")
            else:
                print(f"  verify_password(...) → {result}")
                if result and user.get("role") not in ("admin", "campaign_manager"):
                    # Don't send them off chasing CORS: the password is fine but
                    # the role guard rejects it a few lines later in the handler.
                    print(
                        "\n  → The password IS correct, but section 2 found the role is\n"
                        f"    {user.get('role')!r}. Login gets past the password check and is then\n"
                        "    refused by the role guard with 403. Fixing the password will not\n"
                        "    help; this account needs role 'admin'."
                    )
                elif result:
                    print(
                        "\n  → This password IS correct for this account, and the role is one\n"
                        "    login accepts. The credentials are not your problem; look at how\n"
                        "    the request reaches the API — CORS_ORIGINS, the cookie domain, or\n"
                        "    REACT_APP_BACKEND_URL pointing somewhere unexpected."
                    )
                else:
                    print(
                        "\n  → This password does NOT match the stored hash. The seed is\n"
                        "    create-only: once the account exists, changing ADMIN_PASSWORD in\n"
                        "    Railway has no effect. Set ADMIN_PASSWORD_RESET=true for exactly\n"
                        "    one boot to overwrite the hash, then remove it."
                    )

    # --- 4. Who are the admins? ----------------------------------------------
    rule("4. Every account with role 'admin'")
    admins = list(db.users.find({"role": "admin"}))
    if not admins:
        print("  None. No admin account exists in this database.")
        print(
            "\n  → The startup seed logs 'ADMIN_EMAIL/ADMIN_PASSWORD not set — skipping\n"
            "    admin seed' and returns when either variable is blank. Check both are\n"
            "    set in Railway, then redeploy so startup runs again."
        )
    else:
        for d in admins:
            marker = "  <- the address you asked about" if d.get("email") == wanted else ""
            print(
                f"  {str(d.get('email')):<40} status={str(d.get('status')):<10} "
                f"hash={'yes' if d.get('password_hash') else 'NO'}{marker}"
            )
        if user is None:
            print(
                "\n  → Your address is not in this list. The account was seeded under a\n"
                "    different address — sign in with one of the above, or set ADMIN_EMAIL\n"
                "    to the address you want and redeploy to seed it."
            )

    managers = db.users.count_documents({"role": "campaign_manager"})
    if managers:
        print(f"\n  (also {managers} campaign_manager account(s), which may also use this login)")

    print()
    client.close()
    return 0


def print_usage_error(extra: str = "") -> int:
    if extra:
        print(extra, file=sys.stderr)
    print(
        "MONGO_URL and DB_NAME must both be set.\n\n"
        "    MONGO_URL='mongodb://...' DB_NAME='wearecreators' \\\n"
        "        python diagnose_admin_login.py creator@wearemonk.in\n",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
