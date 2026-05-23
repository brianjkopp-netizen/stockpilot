# Linear Setup Checklist
## StockPilot Project -- Step-by-Step Configuration

Complete these steps in order. Estimated time: 30-45 minutes.

---

## Step 1 -- Create Your Linear Workspace

1. Go to https://linear.app and click **Sign up free**
2. Sign in with your GitHub account (this simplifies the integration later)
3. Create a new **Workspace** named: `Kopp Projects` (keeps it reusable beyond this project)
4. When prompted to create a team, name it: `StockPilot`
5. Skip inviting teammates for now -- you'll add your son after setup

---

## Step 2 -- Configure the StockPilot Team

Inside the StockPilot team settings (`Settings > Teams > StockPilot`):

**Workflow States** -- customize these columns (delete defaults you don't need):

| State | Type | Color |
|---|---|---|
| Backlog | Backlog | Gray |
| Ready | Unstarted | Blue |
| In Progress | Started | Yellow |
| In Review | Started | Orange |
| Done | Completed | Green |
| Cancelled | Cancelled | Red |

**Issue Labels** -- create these labels:

| Label | Color | Use |
|---|---|---|
| feature | Green | New capability |
| bug | Red | Something broken |
| chore | Gray | Setup, cleanup, maintenance |
| research | Purple | Spike or investigation |
| good-first-issue | Teal | Right-sized for learning |
| blocked | Orange | Waiting on something external |

**Cycles** -- enable Cycles (Linear's version of sprints) in team settings. Set cycle length to **2 weeks**. Note: Cycle 1 starts May 27 and runs through Jun 5 (week 1 is only 3 days, May 27-29).

---

## Step 3 -- Create the Roadmap

1. In the left sidebar, click **Roadmap**
2. Create a new Roadmap named: `StockPilot v1`
3. Create four **Projects** (Linear's version of epics/milestones):

| Project Name | Target Date | Description |
|---|---|---|
| Milestone 1 -- Data Foundation | Jun 12, 2026 | yfinance pipeline, indicators, CLI |
| Milestone 2 -- AI Signal Engine | Jul 3, 2026 | Anthropic API, signal generation, logging |
| Milestone 3 -- Paper Trading | Jul 24, 2026 | Alpaca integration, buy/sell execution |
| Milestone 4 -- Portfolio Dashboard | Aug 14, 2026 | Streamlit UI, daily P&L, recommendations |

4. Set each project's **status** to `Planned` -- update to `In Progress` when work begins

---

## Step 4 -- Create the Issues

For each issue in the `GITHUB_ISSUES.md` file:

1. Click **New Issue** in the StockPilot team
2. Set the **Title** exactly as written
3. Paste the full issue body into the Description field
4. Set **Label(s)** as noted
5. Assign to the correct **Project** (Milestone 1 or 2)
6. Set **Status** to `Backlog` initially
7. Assign **Priority**: use `Medium` for most, `High` for the review/gate issues (M1-05, M2-05)

**Issue ordering within each milestone:**
Linear auto-generates IDs like `STO-1`, `STO-2`, etc. Create them in the order listed so the numbers track to the sequence.

---

## Step 5 -- Connect GitHub

This is the integration that makes the work queue self-managing.

1. Go to `Settings > Integrations > GitHub`
2. Click **Connect GitHub** and authorize Linear to access your repo
3. Select the `stockpilot` repository
4. Enable **Auto-close issues** -- when a PR merges with `Closes STO-X` in the description, the Linear issue moves to Done automatically

**How your son uses this:**
When he opens a PR, the PR description should include:
```
Closes STO-3

## What changed
[Brief description of what was built]

## How to test
[Steps to verify the acceptance criteria]
```

This single line connects his code to the work queue without any manual updates.

---

## Step 6 -- Invite Your Son

1. Go to `Settings > Members > Invite`
2. Enter his email
3. Set his role to **Member** (he can create and edit issues, but not change workspace settings)
4. Have him accept the invite and install the Linear desktop app or mobile app

**Recommended:** Have him also install the Linear GitHub app on his machine so he can see issue context without switching windows.

---

## Step 7 -- Set Up Your First Cycle

1. Go to **Cycles** in the left sidebar
2. Create **Cycle 1** starting today
3. Drag these issues from Backlog into Cycle 1 (his first two-week sprint):
   - M1-01: Repo setup
   - M1-02: Stock data fetcher
4. Set both to **Ready** status -- this signals they're groomed and he can start

**The rule:** Only move an issue to Ready if the acceptance criteria are complete and he has everything he needs to start. Backlog = not yet ready. Ready = his work queue.

---

## Step 8 -- Your Ongoing PM Workflow

**Weekly (15 minutes):**
- Review what's In Progress and In Review
- Move newly groomed issues from Backlog to Ready
- Check if anything is Blocked and needs your input

**At the start of each Cycle:**
- Review what was completed vs. planned
- Pull the next set of issues from the appropriate Milestone into the new Cycle
- Write any new issues that have emerged from the last cycle's work

**At each Milestone gate (M1-05, M2-05, etc.):**
- Do not advance to the next Milestone until the gate issue is closed
- These are your product review checkpoints -- treat them seriously

---

## How the Full Workflow Looks Day-to-Day

```
You write an issue in Linear (Backlog)
        |
You groom it and move it to Ready
        |
Your son picks it up, moves it to In Progress
        |
He opens a PR on GitHub with "Closes STO-X"
        |
He moves the issue to In Review, tags you
        |
You review the PR in GitHub, leave comments
        |
He addresses comments, you approve and merge
        |
Linear auto-closes the issue --> Done
        |
You pull the next issue into the Cycle
```

This is the loop. The goal isn't just to ship features -- it's to build the professional habit of working in a structured product-engineering system.
