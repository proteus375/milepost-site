# Two filings before launch: the trade name and the designated agent

Neither needs a lawyer. One of them blocks the other, and one of them blocks the marketplace going
public. This is the working document for both — what was found, what is left, and the exact values to
type into each form.

---

## 1. The West Virginia trade name

### Why this comes first

Milepost operates under **Pointer Technologies LLC**. Trading publicly under a different name than
the LLC's registered name is a trade name (DBA) question, and it is a state matter. It comes first
because **whatever name is actually granted is the name that goes on the DMCA designation**, on the
site footer, in the terms, and in the licence identifier's attribution string. Filing the federal
designation against a name the state then refuses is a $6 mistake plus a rewrite of every document.

The precedent is discouraging and worth restating: West Virginia rejected plain **"Guidepost"** as not
distinguishable from an existing registration, which is why that product trades under a longer
qualified name. "Milepost" is a common word. Expect the same outcome and have a qualified fallback
ready — `Milepost Family`, `Milepost Learning`, `Milepost Homeschool` — rather than discovering the
need for one at the counter.

### What the search could not do from here, and why

The WV Secretary of State's business entity search at
`https://apps.wv.gov/sos/businessentitysearch/` is **behind a reCAPTCHA**. The search form submits,
the page comes back with an *Error Processing Request* panel and no results, and completing the
challenge is not something automation is permitted to do. This is a two-minute manual task, not a
blocked one.

Two further caveats found while looking:

- The service's own help page describes what it returns — *"entity names that match your search
  criteria along with entity type, city and status"* — and **never states whether registered trade
  names are included alongside entities.** Third-party guides claim the register does include trade
  names. That claim is not confirmed by the state's own documentation, so a clean search result is
  weaker evidence than it looks.
- There is a **separate** WV search surface, the Enterprise Registration & Licensing System trade-mark
  search at `https://erls.wvsos.gov/OnlineTMSearch/Index`, which is not the same database. A name can
  be free of entities and still collide with a registered mark.

### The procedure

1. Open `https://apps.wv.gov/sos/businessentitysearch/`, complete the reCAPTCHA, and search
   **Milepost**. Partial matching is on by default — the form asks for "a portion of the name" — so
   the bare word surfaces `Milepost Inc`, `Milepost Holdings LLC` and anything else containing it.
2. Repeat for each fallback: **Milepost Family**, **Milepost Learning**, **Milepost Homeschool**.
3. Search `https://erls.wvsos.gov/OnlineTMSearch/Index` for the same terms.
4. If the entity search shows anything at all in the neighbourhood, **call before filing**: Business
   and Licensing Division, **(304) 558-8000**, `business@wvsos.com`. Ask them two questions directly:
   whether registered trade names appear in the public entity search, and whether the specific name
   you want is distinguishable from what is on file. They answer this all day; it is cheaper than a
   rejected filing.

### If the name is available

| | |
| --- | --- |
| **Form** | Application for Trade Name (DBA) — the **LLC version**, which is a different form from the sole-proprietor one |
| **Filed with** | WV Secretary of State (Charleston, Clarksburg or Martinsburg), online via the One Stop Business Portal, by email, by mail, or in person |
| **Fee** | **$25** |
| **Renewal** | None. A WV trade name does not expire |
| **Prerequisite** | A **WV Business Registration Certificate** from the State Tax Department ($30) must be in hand first. [[TO CONFIRM: whether Pointer Technologies LLC already holds one]] |

### What the answer changes downstream

- The alternative-names list on the DMCA designation (below).
- `Pointer Technologies LLC` / `Milepost` wording in `legal/terms-of-service.md`,
  `legal/privacy-policy.md` and `legal/publisher-terms.md`.
- The site footer and the attribution string the content licence requires.

---

## 2. The DMCA designated agent

### Why it is not optional and not negotiable on timing

Safe-harbour protection under 17 U.S.C. §512 is conditional on a designated agent being on file with
the U.S. Copyright Office, and **it does not apply retroactively** to infringement that happened while
the designation was absent. There is no way to file late and be covered for the gap.

**It must be on file before the first user-published pack is publicly reachable.** That is a
deployment gate, not a launch-week task, and it lands earlier than the counsel review finishes.

### Confirmed mechanics

| | |
| --- | --- |
| **Where** | The Copyright Office's online DMCA Designated Agent Directory. **Paper designations are no longer accepted** |
| **Fee** | **$6** per designation, amendment, or resubmission |
| **Term** | **Three years.** It lapses if not renewed |
| **Renewal** | Amend or resubmit. Either resets the three-year clock. There is no separate renewal fee — the $6 amendment fee *is* the renewal |
| **Account** | One account can manage many designations. The account holder is not the designated agent |

### The finding that makes this cheap

**One designation covers every brand, site and application of a single legal entity**, provided each
is listed on it as an alternative name. The Office's test is *every name the public would plausibly
search for the agent under* — business names, URLs and application names all qualify.

Separate *legal entities* do not: a parent and a subsidiary each need their own $6 filing. Milepost is
not a separate legal entity. It is an alternative name on Pointer Technologies LLC's single
designation. **There is one filing here, not two.**

Omitting an alternative name does not invalidate the designation — it just makes the agent unfindable
by anyone searching that name, which is the entire point of the directory.

### The submission, field by field

Fill this in, then type it in once.

| Field | Value |
| --- | --- |
| **Service provider's full legal name** | `Pointer Technologies LLC` |
| **Physical street address** | [[TO CONFIRM: a real street address, and note that **it is published**. `legal/copyright-and-takedown.md` warns that a PO box alone may not suffice; confirm with the Office rather than assuming either way]] |
| **Alternative names** | See the list below |
| **Designated agent — name** | [[TO CONFIRM: a person or a role, e.g. "Copyright Agent"]] |
| **Designated agent — organization** | `Pointer Technologies LLC` |
| **Designated agent — address** | May be the same as above |
| **Designated agent — telephone** | [[TO CONFIRM]] |
| **Designated agent — email** | [[TO CONFIRM. `legal/copyright-and-takedown.md` leaves this blank too, and the same value must go in both. Whatever is chosen must be a mailbox that exists and is monitored before this is filed]] |
| **Primary administrative contact** | [[TO CONFIRM — this one is not published; it is how the Office reaches you about the designation]] |

#### Alternative names to list

Each domain needs only its top-level form; subdomains are covered.

- `Milepost` — **or the qualified trade name the state actually grants.** This line is what §1 blocks.
- `milepostfamily.com`
- [[TO CONFIRM: the second registered domain]]
- [[TO CONFIRM: the third registered domain]]
- [[TO CONFIRM: the fourth registered domain]]

> The design document records four registered domains but does not name them. List all four here
> before filing — an amendment later costs another $6 and resets the clock, which is harmless, but
> a domain that answers with no agent findable behind it is the failure this filing exists to
> prevent.

### The other half, which is easy to forget

The statute requires the agent's contact information in **two** places: on file with the Copyright
Office, *and* **available to the public on the service's own website.**
`legal/copyright-and-takedown.md` has the block ready with placeholders, but the document is not published and the placeholders are not filled. The agent block
must be reachable from the live site — footer link is the conventional placement — on the same day the
designation goes on file.

---

## Order of operations

1. Confirm the WV Business Registration Certificate is in hand.
2. Search the WV register (manually — reCAPTCHA). Call (304) 558-8000 if anything is close.
3. File the trade name, $25. Wait for it to be granted.
4. Stand up the `copyright@` mailbox and confirm someone monitors it.
5. File the DMCA designation, $6, with the granted name on it.
6. Publish `legal/copyright-and-takedown.md` with the agent block, linked from the site footer.
7. Only then may a user-published pack be publicly reachable.
8. Diary the designation's three-year renewal.
