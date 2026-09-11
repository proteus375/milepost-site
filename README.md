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

All four apps now exist. Each arrived with its first model, which is the rule
this section used to state as a promise about `instances` and can now state as
a fact.

`instances` is the machine channel, and §A says its seam is the one worth
building early: human browser traffic and machine instance traffic differ in
authentication, threat model, rate limiting and — the row that decides it —
compatibility. You control when the website ships. You do not control when a
customer's installation upgrades. So the version is in the path from the first
URL (`/machine/v1/`), the prefix is `machine/` rather than `api/` because this
channel means one specific thing, and no view there touches a session.

`billing` arrived with households and entitlement and **no Stripe**, which is
worth saying because the table above lists Stripe first. What gates a download
is a date on a household that an operator sets by hand; Stripe's job, when it
lands, is to set that same date from a webhook. Splitting it that way meant the
half everything else was waiting on could be built and tested with no external
account, no keys and no webhook tunnel.

§B.3's signed entitlement token is also absent, and that is not the same
omission. The token exists so an installation in the field can verify
entitlement *offline*; there is no `instances` app, so nothing would read it. It
arrives with the app that consumes it, and it will read the same rows the
marketplace already reads in process.

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
