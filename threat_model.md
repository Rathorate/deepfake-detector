# Threat Model: Deepfake / Synthetic Media Impersonation in Video Calls

**Prepared for:** internal security review
**Scope:** risk of AI-generated audio/video impersonation used to defraud or
manipulate employees over video calls, voice calls, or voicemail.
**Status:** draft — for review by Security and Legal before circulation.

---

## 1. Background

Real-time face-swap and voice-cloning tools have lowered the cost of
convincingly impersonating a specific, known individual (an executive, a
colleague, a vendor contact) in a live video or voice call. Publicly
reported incidents include fraudulent wire-transfer authorizations obtained
via deepfake video calls impersonating company executives, and voice-cloned
calls used for social engineering. This document assesses the exposure of
this organization to that class of attack and recommends controls.

## 2. Assets at risk

- **Financial controls**: wire transfers, vendor payment changes, payroll
  changes.
- **Credential and access systems**: IT helpdesk resets, MFA resets, VPN
  access grants.
- **Sensitive information**: M&A discussions, legal matters, HR/personnel
  data disclosed on the assumption the requester is who they claim to be.
- **Trust in internal communications generally**: once employees know this
  attack is possible, unwarranted suspicion of legitimate calls can also
  cause operational friction — this is a secondary risk to manage via
  training, not just technical controls.

## 3. Attack vectors

| # | Vector | Description | Likely target |
|---|--------|-------------|----------------|
| 1 | Live deepfake video call | Real-time face-swap or reenactment software puppeting a known executive's face on a live call (Zoom/Teams/Meet) to authorize a transaction or request. | Finance, executive assistants |
| 2 | Voice cloning (call or voicemail) | Cloned voice of an executive or trusted contact, often paired with urgency/secrecy pressure, requesting a transfer or credential action. | Finance, IT helpdesk |
| 3 | Pre-recorded synthetic clip injected into a call | A pre-generated deepfake clip played into a call (e.g. via virtual camera/mic) rather than real-time puppeting, sometimes to sidestep latency artifacts. | Any video-call-based approval step |
| 4 | Hybrid social engineering | Deepfake/voice-clone used as one part of a broader pretext (e.g. combined with a spoofed email thread or fake urgency) to increase credibility. | Any employee with approval authority |

## 4. Why this works (attacker leverage)

- **Authority + urgency**: impersonating a superior and creating time
  pressure discourages the target from pausing to verify.
- **Channel trust**: employees are trained to trust video/voice as
  "harder to fake" than email, which is no longer reliably true.
- **Bypassing normal verification**: attackers exploit the fact that many
  orgs have strong controls for *email*-initiated requests (e.g. "call to
  confirm") but weaker controls for requests that arrive *by* call.
- **Imperfect but sufficient realism**: for a short, high-pressure call,
  synthetic media doesn't need to be flawless — just good enough that the
  target doesn't stop to scrutinize it.

## 5. Detection signals (technical)

These are useful as supporting signals, not sole evidence:

- Unnatural blink rate or absence of blinking.
- Visible blending seams around the face/hairline, especially under head
  turns or hand-near-face moments.
- Audio-video sync drift, or audio that doesn't match mouth movement
  closely.
- Flat or inconsistent lighting on the face relative to the rest of the
  scene/background.
- Unnatural head-pose stability (real webcams show natural micro-jitter;
  some synthesis pipelines are either too smooth or too jittery).
- Backgrounds that behave oddly when the subject moves (warping near the
  face boundary).
- Refusal or evasiveness when asked to perform an unscripted action (turn
  to profile, cover part of the face with a hand, hold up a written word) —
  real-time puppeting pipelines often struggle with unscripted movement.

A companion prototype tool (`detector.py` in this repo) implements a subset
of these as an automated heuristic scorer for recorded or live video, for
internal testing and awareness purposes. See its README for capabilities
and — importantly — its limitations. It is not a certified detection
control.

## 6. Recommended controls

### 6.1 Process controls (highest priority — cheapest and most reliable)

- **Out-of-band verification for high-risk actions.** Any request for a
  wire transfer, payment detail change, or credential/access reset that
  arrives via video or voice call must be independently confirmed through
  a second, pre-established channel (e.g. calling back a known number on
  file, not one provided during the call).
- **Dual approval for financial transactions above a threshold**,
  regardless of how convincingly the request was delivered.
- **Codeword or challenge protocol** for high-risk approvals between
  executives and finance/IT — a pre-agreed verification phrase not
  guessable from public information.
- **"Time to verify" as a protected norm.** Explicitly tell employees that
  pausing to verify an urgent request is always acceptable and will never
  be penalized, even if the request turns out to be legitimate. Urgency
  pressure is the attacker's main lever; removing the social cost of
  pausing blunts it.

### 6.2 Technical controls

- Evaluate commercial deepfake-detection tools for calls handling
  high-risk approvals (e.g. finance, executive comms), rather than relying
  solely on an internal heuristic prototype.
- Where feasible, use video-conferencing platforms' built-in verification
  features (e.g. verified/authenticated participant indicators) for
  sensitive meetings.
- Log and monitor for anomalous patterns around high-risk requests (e.g.
  a request immediately followed by pressure to bypass standard approval
  steps).

### 6.3 Awareness / training controls

- Employee training specifically on deepfake video/voice call fraud,
  using real (or realistic) example clips, aimed at Finance, HR, IT
  helpdesk, and executive assistants first, then broader staff.
- Tabletop exercise: simulate a deepfake-call fraud attempt against the
  wire-transfer approval process to test whether process controls (6.1)
  actually catch it in practice.
- Clear, simple reporting path for "I think I was just on a call with a
  fake version of someone" — speed of reporting matters for containment.

## 7. Incident response — if a suspected deepfake call occurs

1. **Do not act on the request** until verified through an independent
   channel.
2. **Preserve evidence**: if the call was recorded (with appropriate
   consent/policy), retain the recording; note the platform, time, and any
   unusual details (audio glitches, visual artifacts, evasive behavior).
3. **Report immediately** to Security/IT per the organization's incident
   reporting process.
4. **Check for related activity**: verify whether any linked action (email
   thread, payment change, access request) was also part of the attempt.
5. **Notify affected teams** (e.g. Finance) if the pretext targeted a
   financial or access-control process, so pending requests can be
   double-checked.
6. **Post-incident review**: whether or not the attempt succeeded, feed
   findings back into training and control updates.

## 8. Open questions for Security/Legal sign-off

- What is the organization's policy on recording video calls (consent
  requirements vary by jurisdiction), which affects both detection
  tooling and evidence preservation?
- What threshold should trigger mandatory dual-channel verification for
  financial requests?
- Who owns the codeword/challenge protocol between execs and
  finance/IT, and how often is it rotated?
- Should this threat be added to the formal enterprise risk register, and
  if so, under which existing category (fraud, social engineering, or a
  new "synthetic media" category)?

---

*This document is a starting draft for internal review. It should be
validated, scoped, and formally approved by Security and Legal before
being treated as organizational policy.*
