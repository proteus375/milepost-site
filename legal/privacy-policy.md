# Milepost Privacy Policy

**Version:** 1.1
**Status:** DRAFT — not reviewed by counsel. Do not publish or link from the site until it has been.

*Revision history: 1.0 argued that Milepost never collects anything from a child. Student access
shipped, and that argument is no longer true. 1.1 is written against what the software actually does.*

---

Milepost is operated by **Pointer Technologies LLC**, trading as **Milepost Family**. This policy
explains what we hold, why, and what you can do about it.

## The short version

- **A child has no user account on Milepost, and never gets one.** A parent or guardian holds the
  account, enters the records, and decides what a child can reach.
- **A guardian may optionally give a child a way to sign in** and tick off their own work. It is off
  until a guardian turns it on, one child at a time, and can be switched off again at any moment.
- Your records live in **your own instance**, with its own database, not in a pool shared with other
  families.
- **We do not sell anything about you or your children**, do not share it with advertisers, and do not
  use it to train AI models.
- You can **export everything about any child, in full, at any time**, without asking us.
- You can ask us to delete it.

## About children, specifically

This is the part that matters most, so it comes first.

### A child is a record, not a user

A child in Milepost is a *student profile*: a name, a date of birth if you enter one, their
coursework, and their progress — created and maintained by their parent or guardian. There is no user
account behind it. A child does not appear in the user directory, cannot be sent notifications,
cannot be added to a staff list, and cannot be reached by any part of the system that deals in users.
That is a structural property of how the software is built, not a setting we could flip.

### A child may nevertheless be allowed to sign in

Milepost has an optional feature — **off by default, per child** — that lets a guardian give a child
a way to see their own assignment list and tick items off.

**What the child is given.** A short sign-in code and a passphrase. **Both are issued by the
guardian**, not chosen by the child. The passphrase is stored only as a cryptographic hash; we cannot
recover it, and the only thing a guardian can do with a forgotten passphrase is set a new one.

**What we collect from the child.** The sign-in itself, and a tick. Concretely: the fact that they
signed in and when they were last seen, and which lesson pages they have marked done or undone. That
is the complete list. A signed-in child has no field to type into, no email address, no name to
enter, no profile to edit, no message to send, and no file to upload. There is nowhere in the
child's view of Milepost for a child to put a piece of information about themselves.

**What the child can see.** The courses they are enrolled in, the list of pages in each, and which of
those they have ticked off. Nothing else — not grades or scores, not any other child in the household
or a co-op, not messages, not their transcript or portfolio, not the record export, and nothing that
belongs to a co-op or the marketplace. Those surfaces are reachable only by an adult account holder,
and a signed-in child is not one.

**What a guardian keeps.** Who granted the access and when, whether it is currently on, and when the
child last used it — so a guardian can see whether it is being used and switch off what is not.
Switching it off ends any session the child already has open, immediately.

**The credential is never exported.** The per-child record export described below deliberately leaves
out the sign-in code and the passphrase hash. An export is a file a family emails to a school or a
state; a working credential must not be inside it.

### What this means for COPPA

We are stating our position rather than hiding it: **once a guardian enables sign-in for a child,
Milepost is collecting information from that child**, and we treat the service as being inside the
Children's Online Privacy Protection Act rather than outside it. An earlier draft of this policy
argued the opposite, on the basis that a guardian entered everything. That argument was true of the
software as first designed and stopped being true when this feature shipped.

The design choices above are meant to keep the amount collected as close to nothing as it can be
while the feature still works — guardian-granted, guardian-revocable, guardian-set credential, no
data entry of any kind by the child, nothing visible to the child that the guardian could not already
see. **They are not a substitute for consent where consent is required.**

[[TO CONFIRM — this is now the first question for counsel, ahead of the licensing set, and it is a
design question rather than a wording one:
1. Does enabling access require verifiable parental consent under the amended Rule, given that the
   guardian is the one enabling it, setting the credential, and holding the paid account?
2. Can the guardian's own verified payment card serve as one of the Rule's accepted consent methods?
3. What does the under-13 case require, given that `date_of_birth` on a student profile is optional
   and therefore cannot be relied on to tell whether a child is under 13? Options are to require it
   before access can be enabled, to treat every child as under 13, or something counsel proposes.
4. What must the consent record itself capture, and for how long?]]

### What we hold about a child

Only what is put there:

| | |
| --- | --- |
| **Identity** | Their name, and a date of birth if you enter one |
| **Schoolwork** | Enrolments, attendance, work submitted and files uploaded by a guardian, grades, quiz attempts, notes you write |
| **Progress** | Which lesson pages are done, and when — including ones the child ticked off themselves |
| **Hours** | Days and hours of instruction you log, by subject |
| **Planning** | Multi-year plans and the requirements you set on them |
| **Documents** | Certificates, completion records, portfolios, transcripts, course descriptions and grade reports |
| **Sign-in** | If enabled: the sign-in code, the passphrase hash, who enabled it and when, and when the child was last seen |

### What we do with it

Store it, show it to the guardian, show the child their own checklist if you enable that, and produce
the documents you ask for. Nothing else. It is not used for advertising, not shared with third
parties for their own purposes, and not used to train models.

### What must never be published

Nothing identifying a child may appear in a course pack shared to the marketplace — including your own
child. The Acceptable Use Policy states this and we enforce it.

## What we hold about you

| | |
| --- | --- |
| **Account** | Name, email address, and the identifier from the sign-in provider you use |
| **Billing** | Handled by Stripe. **We do not hold your card number.** We hold your subscription's status, plan and history |
| **Your co-op** | Which organisation you belong to, and what you may do in it |
| **Marketplace** | What you have published, downloaded, and reported |
| **Technical** | Log data — IP address, browser, timestamps — kept for security and troubleshooting |

## Who we share it with

Only the providers we need to run the service:

| | |
| --- | --- |
| **Stripe** | Payments |
| [[TO CONFIRM: hosting provider]] | Hosting and storage |
| [[TO CONFIRM: email provider]] | Sending account and notification email |
| [[TO CONFIRM: any error/monitoring service]] | |

[[TO CONFIRM: the amended COPPA Rule makes operators responsible for how vendors handle children's
data, and that obligation is heavier now that we are collecting from children rather than only about
them. Each provider above needs a data processing agreement, and the list here must stay accurate.]]

We also share information when the law requires it, and we will tell you when we are permitted to.

**We do not sell personal information, and we do not share it for advertising.**

## Inside a co-op

Co-op staff can see what they need to teach: a child's enrolment, attendance, submitted work and
grades for the courses they teach. They cannot see a child's records from other courses, other
co-ops, or your own home instruction, and they cannot export a child's record. **Co-op staff cannot
grant, revoke or change a child's sign-in** — that is the guardian's alone.

Notes co-op staff write about a student, and conversations between staff, are **excluded from the
export you download** — they are the co-op's working record, not the child's. [[TO CONFIRM: whether a
parent has a right of access to those notes under any applicable state or federal law. This is a real
question and the current answer was an engineering decision, not a legal one.]]

## How long we keep things

While your account is open, we keep your records so they are there when you need them — transcripts in
particular are often needed years later.

If you close your account: [[TO CONFIRM: a specific retention period is now required and must be
published. Proposal — records deleted 90 days after closure, with an export offered first and a
warning before deletion. Backups purge on their own cycle, which also needs stating.]]

If you ask us to delete a child's record, we delete it, and the sign-in credential goes with it.
Export first: we cannot get it back.

Disabling a child's sign-in leaves their schoolwork untouched — it removes the child's access, not
their record.

## Your choices

- **Export** everything about any child, at any time, from inside your instance
- **Correct** anything, by editing it
- **Turn a child's sign-in on or off**, per child, at any time
- **Delete** a child's record, or your whole account
- **Ask us** what we hold about you

[[TO CONFIRM: whether state privacy laws — and which — give your users additional rights that must be
described here. Your users are in many states.]]

## Security

Each household or co-op has its own instance and its own database, so a fault in one does not expose
another. Your own sign-in is through an external provider, so we never hold your password. A child's
passphrase is held only as a hash, using the same mechanism that protects any other password, and is
checked at every request rather than trusted once at sign-in — so revoking access takes effect at
once. [[TO CONFIRM: encryption at rest and in transit, backup handling, breach notification
commitment]]

## Changes

We will tell you before this policy changes in a way that matters, and post the date it last changed.

## Contact

[[TO CONFIRM: a real address for privacy requests]]
