# Milepost — the public site

The marketing site for **Milepost**, recordkeeping and curriculum for
homeschooling families and co-ops, and eventually the marketplace service
behind it.

The product itself lives in the `homeschool-lms` repository. This one is the
public half: what Milepost is, who it is for, and — later — subscriptions and
the shared lesson-plan marketplace.

## What is here now

Marketing pages, and nothing else. That is deliberate rather than
unfinished: the marketing half depends on nothing unbuilt, while everything
commercial depends on decisions and code that do not exist yet.

## What it grows into

`docs/marketplace-design.md` in the `homeschool-lms` repository is the design
of record. §A settles the shape: one Django project, one Postgres database,
and four apps —

| App | Responsibility |
| --- | --- |
| `accounts` | Marketplace identity, OAuth endpoints, profiles, organisations |
| `billing` | Stripe, plans, households, subscriptions, entitlement records |
| `catalog` | Listings, packs, search, browse, moderation |
| `instances` | Installation registration, the versioned machine API, licences |

None of them is scaffolded here. An empty app with no models claims work has
started when it has not; each arrives with its first model.

The seam that section says is worth building early is not
marketplace-versus-billing — it is **human browser traffic versus machine
instance traffic**. `instances` gets its own URL prefix, its own
authentication and no shared session middleware, because an installation in
the field cannot be redeployed on your schedule.

## Running it

    python -m venv venv
    venv\Scripts\activate           # Windows
    pip install -r requirements.txt
    copy .env.example .env
    python manage.py runserver

SQLite until `DB_HOST` is set, which is the entire switch to Postgres — the
same convention `homeschool-lms` uses, so an operator does not have to hold
two ideas about how these projects are configured.

## One thing to know about configuration

`settings.env()` treats a **present-but-empty** environment variable as
absent. `os.environ.get(name, default)` does not — it returns `''` — and
`homeschool-lms` shipped `SERVER_EMAIL=` and `LOG_DIR=` blank in its example
file for long enough that every deployment following it sent error mail from
nobody and wrote logs to wherever the process started. Nothing announced it.

Leaving a key blank in `.env` is therefore safe here, and means "use the
default".
