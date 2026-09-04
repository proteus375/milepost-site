# Milepost legal documents — drafts for review

**None of this has been reviewed by a lawyer. Nothing here should be published, linked from the site,
or relied on until it has been.** These are drafts written to give counsel something concrete to
correct, on the theory that reviewing a draft is a shorter and cheaper conversation than being asked
what the documents should say.

## The set

| File | What it is | Who accepts it |
| --- | --- | --- |
| `terms-of-service.md` | The master agreement | Every account holder |
| `content-licence.md` | **Milepost Content Licence 1.0** (`milepost-1.0`) — the terms every pack carries | Accepted by downloading |
| `publisher-terms.md` | The grant, the warranty, the indemnity | Every publisher, and every organisation, version-stamped |
| `acceptable-use.md` | What may and may not be published | Every account holder |
| `copyright-and-takedown.md` | Notice-and-takedown procedure | — |
| `privacy-policy.md` | What we hold and why | — |

## What each document is implementing

Every substantive term traces to a decision recorded in `docs/marketplace-design.md` in the
`homeschool-lms` repository. The mapping, so a reviewer can see what is a considered position and what
is boilerplate:

| Decision | Where it was made | Where it appears |
| --- | --- | --- |
| One licence, versioned, no menu | §4.4.1 | `content-licence.md` §7 |
| Adaptations may be re-published | §4.4.2 | `content-licence.md` §1.3, §3; `publisher-terms.md` §1 |
| Lineage one hop deep, never a chain | §4.4.2 | `content-licence.md` §3; `copyright-and-takedown.md` "Adaptations" |
| Download licence is perpetual | §4.4.3 | `content-licence.md` §4 |
| …except after a takedown | §4.4.3 | `content-licence.md` §4.1; `copyright-and-takedown.md` "Copies already downloaded" |
| …and publishing still needs a subscription | §4.4.3 | `content-licence.md` §3 |
| …and it does not cover co-op content read in place | §4.4.3 | `content-licence.md` §4.2; `terms-of-service.md` §3 |
| Both contributor and organisation warrant | §4.4.4 | `publisher-terms.md` preamble, §2, §3 |
| Acceptance is version-stamped and recorded | §C.4.7 | `publisher-terms.md` preamble, §7 |
| Nothing is ever sold; no publisher payouts | §4.6 | `publisher-terms.md` §5 |
| Subscription sells others' content, not the LMS | §B.4.2 | `terms-of-service.md` §3 |
| Own records never gated | §B.4 | `terms-of-service.md` §3; `content-licence.md` §5 |
| A started run outlives its teacher's billing | §B.4.1 | `terms-of-service.md` §3 |
| Disclose the subscription, never gate enrolment | §4.13 | `terms-of-service.md` §4 |
| Full per-child export, always available | §4.14 | `terms-of-service.md` §6; `privacy-policy.md` |
| Staff notes and conversations excluded from export | §4.14.1 | `terms-of-service.md` §6; `privacy-policy.md` |
| Certified vs parent-attested on the transcript | §E.6 | `terms-of-service.md` §9 |
| Children have no logins | §3 | `terms-of-service.md` §1; `privacy-policy.md` |
| Operating entity is Pointer Technologies LLC | §4.4.6 | everywhere |

## The four questions to put to counsel first

Ordered by how much rides on them.

**1. Does COPPA attach — and what does student access do to the answer?** This was the strongest
question in the set when these drafts were written, on the position that a guardian entering records
about their own child is not collection *from* a child. **Design-doc revision 17 changed the facts
underneath it.** Student access (§F) lets a child sign in and tick off their own work, so the service
now collects from the child, and the question is no longer whether we are outside the Rule but what
compliance inside it requires — including whether the guardian's own verified payment card can serve
as verifiable parental consent, and what the under-13 case needs given that
`StudentProfile.date_of_birth` is nullable and cannot be relied on. **`privacy-policy.md` has been
rewritten against what shipped (version 1.1) and now states that Milepost is inside the Rule rather
than outside it.** Its four sub-questions, in the *What this means for COPPA* section, are the
concrete asks.

**2. Is the takedown procedure sufficient for the safe harbour?** `copyright-and-takedown.md` has
statutory requirements behind it and is the document least safe to publish unreviewed. The repeat
infringer standard in particular is deliberately left blank — vagueness there is a known way to lose
the protection, but the numbers are not ours to pick.

**3. Is an indemnity from individual consumer subscribers worth having?** `publisher-terms.md` §3
takes it from both individuals and organisations. Its practical recovery value is close to zero — you
will not sue a homeschool parent — and its real function is to evidence good faith. Counsel may prefer
to narrow it for individuals and keep it for organisations.

**4. Can an unincorporated co-op warrant anything?** Most co-ops are not legal entities. The design
deliberately does not require them to be, which means organisation warranties may be weak or
unenforceable. Both parties warrant precisely because neither alone survives — but counsel should say
whether the organisation half is worth anything at all.

## Before any of this can go live

- [ ] **Register the designated agent** with the U.S. Copyright Office — $6, renews every three years,
      lists Milepost Family, Milepost and all four domains as alternative names of Pointer Technologies
      LLC. It must be
      on file **before the first user-published pack is publicly reachable**, which is earlier than
      this review needs to finish. The completed field-by-field submission is prepared in
      `docs/name-and-agent-filings.md`; it is blocked only on the trade-name search above.
- [x] **Search the West Virginia trade name register.** Done 4 September 2026, and the bare name is
      out: MILEPOST, LLC (Charleston, Not Active) makes "Milepost" not distinguishable as a trade
      name. **The trade name is `Milepost Family`** — clear on the register, and it matches the
      domain already registered. "Milepost" survives as the product name and as an alternative name
      on the DMCA designation. See `docs/name-and-agent-filings.md`.
- [x] **File the trade name.** Done 4 September 2026 — `Milepost Family` is registered with the WV
      Secretary of State. No separate Business Registration Certificate was needed: the LLC's One
      Stop filing was multi-agency and includes the Tax Department, and form NR-3 asks for no
      registration number in any case.
- [ ] Fill every `[[TO CONFIRM: …]]` marker. `grep -rn "TO CONFIRM" legal/` lists them.
- [ ] Decide the retention periods in `privacy-policy.md` — these are now required to be published,
      and they are business decisions, not legal ones.
- [ ] Get a real contact address. `hello@milepostfamily.com` appears throughout and has no mailbox.
- [ ] Have counsel draft the warranty disclaimer, limitation of liability, and dispute resolution
      clauses. Those are left deliberately unwritten rather than guessed at.

## A note on voice

These are written to be read by homeschooling parents, not by lawyers. Where a plain sentence and a
precise one conflicted, the drafts generally chose plain and flagged it — `copyright-and-takedown.md`
is the exception, because its wording has statutory consequences. If counsel rewrites everything into
standard form, something real is lost: the parts most worth keeping in plain language are the promise
that records are never held hostage over a payment, and the explanation of why scanned workbook pages
cannot be published.
