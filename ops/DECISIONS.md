# ops/DECISIONS.md

Short-form log of hosting/infra decisions and the reasoning behind them —
not a full ADR process, just enough that "why did we do it this way"
doesn't get lost.

## 2026-07-17 — Beta relay tier: reuse existing idle box, don't resize later

**Decision:** Run the first (beta) termhop relay on an existing 1 vCPU /
1.25GB RAM / 25GB / ~2.4TB box that previously ran an early/alpha
RallyText instance (predating the current production stack). When usage
outgrows this box, add a second, larger relay for general use rather than
resizing this one.

**Why:**
- The relay holds almost no durable state (pairing tokens are short-lived
  and single-use; session-resume data is meant to be treated as
  ephemeral) — so "outgrow the box" doesn't require a data migration,
  just standing up a new instance.
- Each agent is configured with one specific relay URL; relays don't need
  to coordinate with each other. This makes "add a relay" a clean scaling
  model instead of "grow one relay to handle everyone."
- The provider (RackNerd) doesn't offer in-place resize, so the choice
  was between lift-and-shift later vs. planning for horizontal (multiple
  relays) growth from the start. Horizontal fit the architecture better.
- Using existing idle capacity instead of provisioning a new box avoided
  an unnecessary cost for what's explicitly a test/beta tier.

**Conditions attached to reusing this specific box:**
- Confirmed the old RallyText instance on it is fully inactive, not just
  superseded — see `ops/decommission-checklist.md`, completed before any
  termhop service was installed.
- Real host details (IP, hostname) deliberately kept out of the public
  repo — see `ops/beta-server.local.md.example` and the `.gitignore`
  entry for `ops/beta-server.local.md`. This repo will eventually be
  public under AGPL-3.0; a nonprofit's real infrastructure shouldn't be
  permanently in its git history.

**Revisit when:**
- Beta tier shows real usage patterns (connection counts, bandwidth) —
  use this to size the "general" relay rather than guessing.
- Per-tenant rate limiting/quotas (tracked as an open item in
  `PROTOCOL.md`) should land before this tier is opened beyond a small
  invite list, per the reasoning in the VPS-sizing conversation that
  preceded this decision.
