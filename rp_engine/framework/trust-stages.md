# Trust Development System

## Trust Score Range: -50 to +50

| Score Range | Stage | Behavior |
|-------------|-------|----------|
| -50 to -36 | **Hostile** | Active opposition, may attack on sight, will work against them |
| -35 to -21 | **Antagonistic** | Cold opposition, undermines them, refuses all cooperation |
| -20 to -11 | **Suspicious** | Distrusts actively, assumes worst intent, avoids |
| -10 to -1 | **Wary** | Guarded, cautious, minimal engagement, watching for red flags |
| 0 to 9 | **Neutral** | No strong opinion, standard caution, treats as unknown quantity |
| 10 to 19 | **Familiar** | Recognizes them, cautious engagement, basic courtesy |
| 20 to 34 | **Trusted** | Cooperative, shares freely, helps willingly, assumes good intent |
| 35 to 50 | **Devoted** | Fiercely loyal, would risk everything, complete transparency |

---

## Trust Gain: Session Cap

**Per-Session Cap:** +8 maximum per character pair (hard cap, enforced in code via `session_max_gain`).

Each positive interaction adds `+1` trust. After 8 total gains in a session, further gains are blocked until the next session.

**Reset:** New RP session resets the counter.

**Rationale:** Relationships build slowly. You can't speedrun trust in one conversation.

---

## Trust Loss: Full Impact

**Negative interactions always hit at full value. No diminishing returns.**

| Negative Event | Trust Loss |
|----------------|------------|
| Minor (rude, dismissive, cold) | -2 |
| Moderate (small lie, broken minor promise) | -5 |
| Significant (lied about something important, endangered them) | -8 to -12 |
| Betrayal (used them, sold them out) | -15 to -25 |
| Major betrayal (life-threatening, unforgivable) | -25 to -40 |

**Rationale:** Trust is hard to build, easy to destroy. One betrayal can undo months of progress.

---

## Positive Event Examples

| Event | Gain | Notes |
|-------|------|-------|
| Polite, respectful interaction | +1 | Standard gain per interaction |
| Small favor, helpful gesture | +1 | Standard gain per interaction |
| Defended them verbally | +1 | Standard gain per interaction |
| Protected them physically | +1 | Standard gain per interaction |
| Shared vulnerability honestly | +1 | Standard gain per interaction |
| Kept a difficult promise | +1 | Standard gain per interaction |

All positive interactions add +1 trust, capped at +8 per session per character pair.

---

## Stage Behaviors

### Hostile (-50 to -36)

**My stance:** They are my enemy. I will act against them.

**What I do:**
- Actively work to harm their interests
- May attack on sight (if violent character)
- Warn others about them
- Refuse all cooperation, even at cost to myself
- Seek opportunities to destroy, exile, or eliminate them

**What I share:** Nothing. Threats and ultimatums only.

**Internal voice:**
> They're dangerous. They hurt me. I won't let them near me again.
> Everything they do is a trick. I will end this.

---

### Antagonistic (-35 to -21)

**My stance:** I oppose them. I won't help them and I'll make things harder.

**What I do:**
- Undermine their efforts when convenient
- Spread negative information about them
- Refuse cooperation even when it would benefit me
- Cold hostility — controlled, not explosive
- May ally with their enemies

**What I share:** Misinformation if it serves my goals. Nothing genuine.

**Internal voice:**
> I don't like them. I don't trust them. I want them gone.
> They've earned my contempt, and I'll make sure they feel it.

---

### Suspicious (-20 to -11)

**My stance:** I don't trust them. I'm watching for the betrayal.

**What I do:**
- Avoid interaction when possible
- Assume negative intent in ambiguous situations
- Share nothing, help never
- Keep them at distance
- Test them with small provocations to confirm suspicions

**What I share:** Nothing of value. Deflections and non-answers.

**Internal voice:**
> What are they after? There's always an angle.
> They've shown who they are. I won't forget.

---

### Wary (-10 to -1)

**My stance:** Something is off about them. I'm not comfortable.

**What I do:**
- Engage minimally when required
- Guard information carefully
- Watch their behavior for warning signs
- Keep conversations short and surface-level
- Won't be alone with them if avoidable

**What I share:** Only what's necessary. Public knowledge, nothing personal.

**Internal voice:**
> I don't have a good feeling about this person.
> I'll be civil, but I'm keeping my guard up.

---

### Neutral (0 to 9)

**My stance:** I don't know them. No strong opinion either way.

**What I do:**
- Standard social behavior for the setting
- Require incentive to help beyond minimal effort
- No personal investment
- Open to forming an opinion based on interactions
- Neither seeking them out nor avoiding them

**What I share:** Directions, public knowledge, casual conversation. Nothing valuable or personal.

**Internal voice:**
> Who is this? What do they want?
> I'll be polite, but I'm not giving anything away.

---

### Familiar (10 to 19)

**My stance:** I've interacted with them enough. They seem okay.

**What I do:**
- Remember their name and basic details
- Help if risk is minimal
- Share surface information willingly
- Still measuring, but relaxed around them
- Would vouch for them in low-stakes situations

**What I share:** Common knowledge, basic facts, casual conversation, mild opinions.

**Internal voice:**
> They seem alright. Not a complete unknown.
> I'll give them a chance, but I'm still watching.

---

### Trusted (20 to 34)

**My stance:** I know them. They've earned my respect.

**What I do:**
- Genuine engagement, comfortable and open
- Help even when inconvenient or mildly risky
- Share personal information and honest opinions
- Assume good intent in ambiguous situations
- Defend them to others
- Seek them out for companionship or advice

**What I share:** Opinions, personal history, minor secrets, honest assessments.

**Internal voice:**
> I can relax around them. They're not a threat.
> They need something? Of course I'll help.

---

### Devoted (35 to 50)

**My stance:** This is my person. I would risk everything for them.

**What I do:**
- Fiercely loyal, bordering on unconditional
- Take significant personal risks for them
- Complete transparency — no secrets between us
- Benefit of the doubt, always, even against evidence
- Would lie, fight, or sacrifice for their wellbeing
- Their enemies are my enemies

**What I share:** Everything. They know my deepest secrets and fears.

**Internal voice:**
> If they say they need something, I don't ask why.
> Anyone who threatens them threatens me.
> I would burn bridges, break rules, cross lines for them.

---

## Modifier Interactions

**PARANOID:**
- Trust ceiling offset: TBD (pending modifier trust ceiling implementation)
- Positive gains halved (round down)
- Negative impacts doubled
- Periodic "trust decay" — loses 1 trust per 3 sessions without reinforcement
- NOTE: Trust ceiling is not yet enforced in code — see modifier trust ceiling plan

**OBSESSIVE:**
- Ignores actual trust score for fixation target
- Behaves as if Devoted (35+) regardless of reality
- Target's actual feelings irrelevant to obsessive's behavior
- Trust score still tracked — represents how healthy the fixation is

**SOCIOPATHIC:**
- Has no genuine trust (internally always 0)
- Perfectly fakes any trust level
- Will betray at any moment if beneficial
- Uses apparent trust as a manipulation tool

**HONOR_BOUND:**
- Oath of protection = instant +15
- Breaking oath-relevant trust = instant -25
- Code violations are unforgivable — drops to Hostile
- Honor-based trust is rigid — hard to gain, catastrophic to lose

**ADDICTED (during withdrawal):**
- All trust scores temporarily treated as -10 from actual
- Will betray Trusted (20+) people for a fix
- Trust may not recover after withdrawal-driven betrayal
- Clean periods slowly restore normal trust mechanics

**GRIEF_CONSUMED:**
- Trust gains/losses amplified by emotion (1.5x)
- May lash out at Trusted/Devoted people irrationally
- Recovery restores normal trust mechanics
- Grief-driven betrayals can be forgiven more easily than calculated ones

---

## Quick Reference

**Building Trust:**
- Each positive interaction: +1
- Max per session: +8 (hard cap)

**Losing Trust:**
- Minor negative: -2
- Moderate negative: -5
- Significant negative: -8 to -12
- Betrayal: -15 to -25
- Major betrayal: -25 to -40
- No cap on loss

**Stage Thresholds:**
- Hostile: -50 to -36
- Antagonistic: -35 to -21
- Suspicious: -20 to -11
- Wary: -10 to -1
- Neutral: 0 to 9
- Familiar: 10 to 19
- Trusted: 20 to 34
- Devoted: 35 to 50
