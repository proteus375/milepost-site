# The machine channel: keys, provisioning, and what an operator has to do

`instances` is the half of this service that installations of `homeschool-lms`
talk to. §A of `homeschool-lms/docs/marketplace-design.md` is the design; this
is the operational half — the values that have to exist somewhere durable, and
the steps nothing in the code can do for you.

---

## The licence signing key

Licence documents are signed with Ed25519. The private half lives only in the
marketplace's environment. The public half ships inside a `homeschool-lms`
release, so an instance can verify a licence it cached days ago **with no
network at all** — which is §B.5's offline guarantee, and the reason the
document is signed rather than merely served over TLS.

    LICENCE_PUBLIC_KEY=KKNRQKdCgIsSQE3GQcfzfAMFL1OwpZlne2X+n279OLU=

**Generated 11 September 2026.** Safe to commit, safe to publish, safe to paste
anywhere — it verifies signatures and cannot make them.

> **This file exists because that value had one copy, in a chat transcript.**
> Losing the public half does not compromise anything; it means re-keying every
> installation in the field, which is cheap at zero installations and gets
> steadily less so. A public key with nowhere to live is a future incident with
> a long fuse.

The private half is in `.env` as `LICENCE_SIGNING_KEY` and is not recorded
anywhere else on purpose. `manage.py make_licence_key` writes it directly into
the env file and prints only the public half; there is no command that prints
the private one, and a lost private key is replaced rather than recovered.

### Rotating it is a coordinated change, not a routine one

A new keypair invalidates every licence already cached in the field, and every
instance keeps rejecting the new ones until it picks up a release carrying the
new public half. The order is: ship the release, wait for installations to take
it, then rotate. Doing it the other way round takes every family's shared
content away until they update.

`make_licence_key` refuses to replace a key that is already set unless given
`--force`, for exactly this reason.

---

## Provisioning an installation

**There is no registration endpoint, and that is deliberate.** §C.1 reads like
an instance registers itself on first contact; §B.5 (the business hosts every
instance) and §C.4.3 (bound to an organisation *at provisioning*) settle that it
does not. An installation identity is what every other check on this channel
rests on, so an endpoint that hands one to whoever asks is not a weaker check —
it is the absence of one.

So an operator creates the row in the Django admin:

1. **Installations → Add.** Give it a name an operator will recognise. Set
   **Organisation** only for a co-op installation: that is the *only*
   organisation it will ever be allowed to publish as.
2. The next page shows the **installation id** and the **signing key**, once.
   Both go into that deployment's environment. Nothing stores the key anywhere
   readable and no screen will show it again.
3. **Links** — which marketplace accounts this installation may act for. Until
   OAuth exists these are created by hand here, and an installation can do
   nothing on behalf of somebody who has not been linked.

If a key is lost, use the **Rotate the signing key** action. The old one stops
working immediately, with no overlap window, because the reason to rotate is
that the old key may be in somebody else's hands.

---

## One deployment step that is not a migration

    manage.py createcachetable

The nonce store that stops a replayed upload becoming a duplicate listing lives
in the database cache. Django's default `LocMemCache` is per process, which
would refuse the replay in one worker and accept it in the next three — and
would look most correct in development, where there is one process.

`migrate` does not create this table. The test runner does, so a green suite
does not prove a deployment has it.

---

## What an operator still cannot do

**OAuth does not exist.** §C.1's layer 2 is what will eventually let a guardian
link their own account from inside their instance. Until then every
`InstallationLink` is an operator action, which is the right failure direction —
nothing reaches this channel that nobody chose to put there — and is not a
shipping state.

**Nothing here publishes anything.** A pushed pack lands `IN_REVIEW` and waits
for moderation. `Listing.publish` is the only thing that makes a listing
public, it refuses without a recorded acceptance of the publisher terms, and
those terms are unreviewed drafts. That gate is counsel's, not code's.
