# Magnum Now — presenter's prompt book

**Twenty minutes, seven cues, one honest number.**

A running order for the client demonstration. Each cue names the screen, the
exact clicks, and the line that carries it. Every figure quoted below is live in
the build — if one has moved, the build is telling the truth and this page is
stale, not the other way round.

| | |
|---|---|
| **Runtime** | ~20 min + questions |
| **Market** | NY / CT metro |
| **Window** | 39 weeks, 2025-12-02 → 2026-09-01 |
| **Data** | synthetic, seed `20260901` |
| **Companions** | [BUILD.md](../BUILD.md) (full spec + change log) · [MODEL_CARD.md](MODEL_CARD.md) (evaluation + limitations) |

---

## Before the room walks in

```bash
scripts/start.sh
```

One process, one address. The API serves the built front end, so there is no
Node running and nothing to explain if somebody glances at your terminal. (While
developing, `npm run dev --prefix web` gives hot reload on `:5173` and proxies
`/api` back to `:8000` — that is a build-time convenience, not a second app.)

Open **`http://localhost:8000`** and leave it parked on the default scenario:

> **Astoria NY · Friday 5–7 PM · summer · hot · game day on · John Smith**

Say the disclaimer once, in your own words, and then never again: this is an
Uber Eats-*inspired* reference build, it is not an Uber product and is not
affiliated with or endorsed by Uber, and every row of data in it is synthetic.
Getting that out of the way early is what buys you the right to quote numbers
confidently for the next twenty minutes.

---

## Cue 0 — What it adds up to

**Screen:** Impact **Time:** 3 min

The first tab, and the first thing the room sees. Open it before you show them a
single recommendation, then come back to it at the end.

> **Say:** *"Everything after this screen answers whether one decision is right.
> This screen answers what they add up to — and it is the easiest screen in this
> product to lie on, so it is built to be argued with."*

Four charts, left to right and then down. They are in that order on purpose: it
is an argument, and the money is the conclusion, not the opening.

1. **Shown, and what came back.** All ten stores combined, and it is **one bar,
   not two** — the whole bar is what the system put on screen, and the solid part
   at the bottom is what came back out of it. Both numbers are written above each
   bar, so nobody has to guess which is which: *56.2k shown*, then *12.4k bought
   · 22%*. The solid part is itself split by whether the basket needed a coupon
   to close — **5.9k at full price, 6.6k with a coupon**. Then
   read the line under it out loud, because it is the number nobody volunteers: a
   further **4.4k baskets buy Magnum with nothing on screen at all**, and this
   page does not count them.

   > **Say:** *"Half the conversions here did not need a discount. That is the
   > whole product in one bar — the cheapest thing you can do to a customer is
   > show them the right thing, and we only pay when we have to."*

2. **Extra Magnum orders** — +410 a month against no targeting, plus the orders
   substitution saves when the first choice is gone. Then the point worth making
   out loud: against the blanket campaign, attach is **1.48 points lower**, about
   **171 fewer discounted orders a month**, and it still makes more money —
   because the campaign was paying for orders that were coming anyway.
3. **Stockouts caught early.** The forecast calls a shortfall before the peak and
   stock moves between stores — **101 store-to-store moves** over six months,
   **1.4k shelf-hours** that never go empty, **3.9k bars** saved, worth
   **$11.6k**. Do not overclaim the split, and do not let anyone else either:
   **3.75k of those 3.9k bars are spoilage**, not customers who were refused. The
   caption says so on the screen.
4. **Margin gained — everything above, in money.** Full width, last, and it is
   the first three charts converted: green is the offer lever from charts 1 and
   2, blue is the stock lever from chart 3. Six months is **$31.4k**, with
   whiskers running **$19.8k to $43.1k**. The extra orders are never added on top
   — they are the same lever counted in units.

> **Say:** *"Against a blanket 20% campaign — one campaign, one depth, everybody
> in the file, which is what most retailers actually run — this is worth about
> **28 cents a decision**, and that result is statistically solid. Against doing
> nothing at all, the extra orders are established and the extra money is not
> yet, on this much data. We would rather you trusted the first number, and the
> confidence intervals behind both are on the Analysis tab if you want them."*

If somebody asks to see that, go to **Analysis → policy evaluation**. Do not go
looking for it on this screen — the interval chart used to live here and was
taken off, because a client asking "what am I looking at" about the second chart
on the business-case screen is a chart that has failed.

Now move the two sliders in the header while they watch:

- **Forecast recovery** — the only assumption on the page, and it is a control
  rather than a constant. Every chart moves. Everything else is read off 273 days
  of log.
- **Network scale** — ×1 is the simulated network, 10 stores and 5,000
  households. The rates hold; the volumes move.

> **Say:** *"There is exactly one assumption on this page and we made it a slider
> so you can disagree with it in front of us. Stock loss is costed at the average
> demand on a shelf-hour — and stockouts cluster in busy hours, so that
> understates the loss rather than flattering it."*

---

## Cue 1 — The problem, in one screen

**Screen:** Shop **Time:** 2 min

> **Say:** *"This is a quick-commerce storefront. What makes it different is that
> nothing on it is a static merchandising rule."*

Point at the scenario bar: 93 °F, hot, game day live, demand ×1.44 against a
normal Friday. Then the **Ranking this list** strip — text 35%, personal 25%,
peer 15%, context 15%, availability 10%. The weights are on the screen, not in a
slide.

Click **Why** on Magnum Almond Bar. The score decomposes term by term, with
reason codes underneath.

> **Say:** *"Every recommendation in this system can be interrogated. If it
> cannot be explained, it does not ship."*

---

## Cue 2 — The recommendation never goes away — and it reads the plate

**Screen:** Shop **Time:** 6 min

This is the cue that answers *what does Magnum actually get out of it*. Do not
rush it.

1. **Live Magnum picks** is at the top right, in view the moment the page loads
   and never dismissed by anything the shopper does. The latency chip is measured
   server time, not a spinner.
2. It is **two rows**, and each one is the whole answer: which Magnum, why it is
   there, and **what it costs this shopper right now**. Read the top row out in
   full before you touch anything.

> **Say:** *"Two, not twenty. A rail of twenty is a shelf; two is a
> recommendation. And each one carries its own price — decided by the same
> function the cart uses, on the same inputs, so these two surfaces physically
> cannot quote you different numbers."*

**Scenario for everything below:** Astoria, summer, hot, Friday dinner, game day
on. Set it once on the scenario bar and leave it — the numbers here were measured
on exactly that.

For John Smith the top row reads:

- **Magnum Double Caramel Bars, 3 Count** · goes with your food · $10.99
- **11% off any Magnum — saves $1.20, applied at checkout**
- *"The hour trims it from the usual 20% — orders are running 64% above normal
  for this hour, so we are not paying for orders that were coming anyway."*
- *"Friday 7-10 PM is one of the busier slots of the week in its own right, which
  trims it further."*
- *"They are ahead of their own rhythm — already coming back, so the note stays
  light."*
- and the strip underneath: **`20% base · hour −34.1% · slot −7.5% · = 10.9%`**

> **Say:** *"Three sentences, three different reasons, and the arithmetic under
> them. The first is what today's conditions did. The second is what Friday
> evening does every week regardless of the weather — those are two different
> facts and we price them separately. The third is about him. And none of the
> three claims to be the answer; the number on the right is the answer."*

Now **switch households without touching anything else**, then flip to
**rain, Wednesday, late** and go down the list again:

| Household | Hot match-day Friday, dinner | Rainy Wednesday, late |
|---|---|---|
| John Smith | 10.9% | 21.6% |
| Sarah Miller | 10.7% | 21.4% |
| David Brown | **no coupon** | 19.4% |
| Emily Davis | **no coupon** | **no coupon** |
| Michael Johnson | 14.2% | 23.7% |
| Jessica Wilson | **no coupon** | **no coupon** |

> **Say:** *"Read a row and the hour is moving the price — demand goes from 64%
> above normal to well below it, and every coupon on the page roughly doubles.
> Read a column and the person is. Michael is seventy per cent past his own
> reorder rhythm and he buys on offer, so he is the deepest in both. David gets a
> coupon on the quiet hour and none on the busy one — same household, and the
> hour alone decided it. Jessica has not bought on a single offer in eight months
> of orders, so the system declines to pay her — on every hour we have tried."*

If someone asks why the empty ones are empty, that is the answer worth having:

> **Say:** *"That is not a gap in the demo. A system whose only visible behaviour
> is handing out money is not one you want setting prices. The hours it declines
> are the ones that pay for the hours it does not."*

The chips under the search box are shortcuts, nothing more — but watch their
order change when you move the weather or the household. That row is the system
guessing, and it has to guess differently for different people.

3. Type **pizza** and search. Watch the rail. **Mini Classic Bars, 6 Count**
   goes to the top.
4. Now search **burger**. The rail inverts to **Double Caramel Bars, 3 Count**.

Point at **Pairing is live · 28% of the score**:

> **Say:** *"It is not just surviving the search. It is reading it."*

Read the panel out. Baskets with a burger take **caramel 1.60×** more often than
the store average, and the size pull drops to **0.70×** because a burger is one
person's dinner. Baskets with pizza take **classic 1.36×**, and the size pull
rises to **1.52×** because a pizza is a table. Both measured across real baskets —
1,611 for the burger, 5,384 for the pizza, and the count is on the screen.

Then search **wings**, which is the one that shows the model has a shape rather
than a preference:

> **Say:** *"Wings are the spiciest thing on this menu. Almond goes up to 1.23,
> and caramel — the heaviest, sweetest thing we sell — falls to 0.65. A hot plate
> does not want a rich finish. And the size goes to 1.46, because nobody orders
> wings for one. The dish is moving the flavour and the count in two different
> directions at the same time, and neither of those was written by hand."*

The control, if anyone asks whether this is just basket size in disguise:

> **Say:** *"French fries carry no flavour affinity in our model, deliberately.
> Across 1,989 baskets they sit between 0.94 and 1.07 on all four flavours —
> nothing. If the effect were an artefact of big baskets, fries would move with
> the burger. They do not."*

If they push, be straight about the limit: onion rings sit on 944 baskets and
white lands at 0.83, which is noise on a sample that size rather than a signal.
The count is on the screen next to every one of these numbers for exactly that
reason.

Finally, open the **chevron** on the top rail row. Every factor, in plain
English, with its score, its weight, its points, adding to the match score.

> **Say:** *"Every ranking in this system decomposes, and none of it is written
> in jargon. Note the weights on the strip above: when there is something to pair
> with, 'goes with your food' takes 28% and the other five compress to make room.
> The formula is on the glass, not in a slide."*

---

## Cue 3 — Change the world, watch it react

**Screen:** Shop **Time:** 4 min

Scroll to **If the world changed right now**.

> **Say:** *"One resolved context tells you what the system does. It does not
> prove the system is reacting. So here is the whole curve."*

1. **Weather.** Five bars, hot 2.63× down to snow 1.16×. Click **Snow**.
   - The banner names it: weather hot → snow, demand 2.63× → 1.16× (−56%),
     93 °F → 67 °F.
   - The signal list flips sign: weather −0.42, seasonal norm −0.46.
   - The rail re-ranks; the arrows show what moved. **The order changes, not just
     the scores** — on heat the light bars lead, on cold the rich ones do.

> **Say:** *"Temperature does not just sell more ice cream. It sells different
> ice cream. In our order log white chocolate goes from 12.7% of units in winter
> to 30.3% in summer, and caramel goes the other way, 36.3% down to 18.2%. The
> ranker uses the same numbers the history was built on — one definition, shared
> by both — so what you see here is not a rule somebody typed in."*
2. **Time of day.** Morning 1.15× against dinner 4.06×.
3. **Day.** Tuesday 1.84× against Saturday 2.89×.
4. Put it back on **Hot** before you move on.

> **Say:** *"None of this is a demo animation. Each bar is the real
> resolve-and-rank path the live screen uses, so what you preview is exactly what
> you get when you click it."*

---

## Cue 3b — The calendar is a pricing input, and match night is a different night

**Screen:** Shop, then Cart **Time:** 4 min

The cue that answers *"does it actually react, or does it just look busy?"* Set
**Astoria · summer · warm · dinner**, household **John Smith**, and leave
everything else alone for the whole cue. You will change exactly one control at
a time.

**1. Walk the days.** Click Monday, then Friday, on the Day strip.

| | Monday | Friday |
|---|---|---|
| Top rail row | Classic Milk Chocolate Bar | **Double Caramel Bars, 3 Count** |
| Coupon | 15.9% | 15.2% |
| Breakdown strip | slot **−4.0%** | slot **−7.5%** |

> **Say:** *"Same weather, same hour, same person. The flavour changed and the
> price changed, and the reason is on the strip: the hour term is identical on
> both — the weather did not move — and the slot term went from minus four to
> minus seven and a half. Friday evening is one of the busiest slots of the week
> in its own right, so more of the coupon comes off. That is not a rule somebody
> typed: Friday baskets take a box rather than a single ten per cent more often
> than an average day, measured across 4,954 of them."*

**2. Now toggle match day.** One click, nothing else.

| | Monday | **Monday + match** |
|---|---|---|
| Top rail row | Classic Milk Chocolate Bar | **Double Caramel Bars, 3 Count** |
| Coupon | 15.9% | **13.2%** |

**3. Go to the Cart** with two large cheese pizzas in it, and toggle match day
again while they watch.

| | Monday | **Monday + match** |
|---|---|---|
| Suggested | 1 × Mini Classic, **6 bars** | 3 × Almond 3-pack, **9 bars** |
| Format | one box | three boxes |

> **Say:** *"Three things moved on one click: the flavour, the count and the
> price. And the count did not move because somebody wrote 'match day, sell
> more'. Match-window baskets in our log take a box thirty-six per cent more
> often than average and carry fourteen per cent more bars — two separate
> findings, and the system uses them separately. The bar count comes from the
> second one. The decision to send three small boxes rather than one big one
> comes from the first."*

**4. Switch to David Brown** and toggle match day once more. The coupon
**disappears**, and the card says which night it is declining on:

> *"No coupon · Monday 7-10 PM — orders are running 36% above normal for this
> hour. At that level the shallow price this hour can afford would not move this
> household enough to pay for itself. The pick and the size are still moving —
> monday and match window baskets are what put this one first."*

> **Say:** *"Same click, opposite answer, because he is a different household.
> And notice it still moved — the flavour went to almond and the cart went from
> three bars to six. Price is one of three levers and it is the one we are most
> careful with."*

**If someone asks whether every day is different**, be straight:

> **Say:** *"Monday and Tuesday genuinely look alike in this log — pack lift 0.82
> against 0.84. Rounded to a whole percent they can print the same coupon. We did
> not manufacture a difference that is not there; the strip under the coupon is
> where the tenth of a point stays visible."*

---

## Cue 4 — Who is this shopper?

**Screen:** Customer **Time:** 4 min

Click **View analytics** in the header. Work down the page in this order.

- **Identity and consent first**, deliberately. Marketing consent,
  personalisation, contacts 0/1 in 24 h and 0/3 in 7 d, and whether they are
  contactable at this moment. *The first thing the system shows about a customer
  is what it is allowed to do.*
- **Lifetime.** 33 orders, \$918, 18.2% attach against a 24.1% cluster.
- **Against the cluster.** Green is the household, grey is the peer group. A
  household number without its benchmark is not a fact anyone can act on.
- **When are they due.** John bought yesterday, so the gauge reads 0.01× —
  *early* — and the reorder nudge stands down.
- **Month by month.** The attach line climbing out of winter into August.

> **Say:** *"That climbing attach line is the entire thesis, one customer at a
> time."*

Close on the padlock at the bottom: `latent_traits` is never read here.

---

## Cue 5 — The message it would actually send

**Screen:** Customer → **The nudge** **Time:** 5 min

This is the cue the room came for. Everything above it is evidence; this is the
thing the evidence pays for.

Scroll to **The nudge** — a rendered phone notification with a real product
shot, a headline, a size and an offer.

1. **Read the message out loud, as written.** For John, on a 93 °F game-day
   Friday: *"John, 4 classic bars before kickoff. We lined up 4 bars — the size
   you usually take. Enough for the whole watch party."* Three things are
   assembled there, not picked from a list: the **occasion** that leads, the
   **size** this household takes, and a closing line written for what they are
   buying for.
2. Then the strip beneath it, left to right — every number in the message traces
   to one of these: reorder odds, size, offer attached, expected net.
3. **Why this hour.** *"Their own order history clusters at 9 PM."* Not a
   campaign send-time. Their hour.
4. **Why this household, why now.** The drivers, in priority order, with the
   lead driver setting the headline.

Now switch households in the selector and let the room watch it re-compose. The
six are deliberately different and the contrast is the argument:

| Household | Decision | Headline it composes | Size | Offer attached |
|---|---|---|---|---|
| **John Smith** | **held** — ordered 4 h ago | *John, 4 classic bars before kickoff* | 4 bars | — |
| Sarah Miller | send, Tue 7 PM | *Sarah, 5 classic bars before kickoff* | 5 bars | — |
| David Brown | send, Sun 1 PM | *David, 2 almond bars before kickoff* | 2 bars | — |
| Emily Davis | send, today 6 PM | *Emily, the freezer is looking empty* | 3-pack | flavour discovery |
| **Michael Johnson** | send, today 7 PM | *Michael, it has been 30 days* | 4 bars | **5% off a multipack** |
| **Jessica Wilson** | send, today 2 PM | *Jessica, it has been 107 days* | 2 bars | **flavour discovery, no discount** |

> **Say:** *"Same engine, same moment, six different headlines, six different
> sizes. The three at the top lead on the match, because nothing about their own
> cadence is arguing for a send — so the message is about kickoff and the size
> they take. The three below lead on the person, because being 30 days past your
> own rhythm outranks whatever is on television."*

> **Say:** *"Michael is a deal explorer and the economics justify paying him.
> Jessica buys premium at full price — discounting her would burn margin she was
> never going to need, so she gets a flavour suggestion instead and it costs three
> cents. And John gets nothing at all, because he ordered four hours ago."*

**Now change the weather and read the same six again.** This is the part worth
slowing down for, because the copy is not a template with a slot in it:

| Condition | John Smith | David Brown |
|---|---|---|
| Match day, 93 °F | *John, 4 classic bars before kickoff* | *David, 2 almond bars before kickoff* |
| Rainy Wednesday evening | *Raining out — 2 almond bars to the door* | *Raining out — one almond bar to the door* |
| Cold Tuesday lunch | *John, 2 almond bars worth staying in for* | *David, one almond bar worth staying in for* |

> **Say:** *"The headline, the flavour, the count and the closing line all moved,
> and none of them moved because somebody wrote three versions of this message.
> The rain changes what leads. The temperature changes the count — heat makes
> baskets bigger, not just more frequent, and that is measured in the log rather
> than asserted here. And the closing line is chosen against the condition, so a
> family planner is never told to stock up for a watch party on a wet Wednesday
> with no game on."*

**The offer depth is live too.** Michael's card reads **5% off a multipack** on
this busy game-day Friday. Switch to a cold Tuesday lunch and re-read the same
card: **25% off any Magnum**. The label is rendered from the depth the policy
just decided, not typed into the copy — because a message that says 20% next to a
12% discount is a customer-service ticket.

Land on John and point at the greyed card:

> **Say:** *"Note that the message still gets composed. We show you exactly what
> would have been sent and then we don't send it. Restraint you cannot see is
> indistinguishable from a system that never had an idea."*

---

## Cue 6 — The commercial decision, where the shopper meets it

**Screen:** Shop → Cart **Time:** 3 min

Search **pizza**, add the large cheese pizza, open **Cart**.

- **How many, and why.** Read the subtitle out — 40% what this household
  normally buys, 35% what similar households buy, 25% the size of tonight's
  occasion, then rounded to a pack that actually exists on the shelf. No symbols.
- **What's in the basket changes the answer.** Flavour pull and size pull, side
  by side. One pizza pulls **classic to 1.35×** and caramel down to 0.69×, and
  pushes the size to **1.52×** — five bars, off an occasion read of three people.
- Now **add the wings**. The occasion read goes 3 → 5 people and the count before
  rounding goes 4.51 → 5.17; the almond pull climbs toward classic (1.15× →
  1.19×) because the wings are voting for a lighter finish and the pizza is
  voting for classic.
- **Add a second pizza.** Occasion reaches 6, and the answer flips format
  entirely — from five single bars to one **Mini Classic Bars, 6 Count**.
- **What your last edits changed** logs each movement as it happens, and stays
  silent when an edit moves nothing — so the log records causes, not flicker.

> **Say:** *"The basket is the strongest signal in the product and it used to be
> spent on a headcount. What somebody is eating tells you which flavour goes with
> it and how much of it they need — and every one of those numbers moves the
> moment a line changes."*

Switch households with the same basket and watch the answer change — the pairing
tilts the ranking, it does not overturn a history. Somebody who only buys white
chocolate is not handed classic because they ordered a pizza.

- **The hour's own pull on the size** is now its own set of rows in the table,
  between the basket subtotal and the final count. Heat, match day and how many
  people are ordering right now each carry their own multiplier with the sentence
  that justifies it. This is not decoration: the generator writes heat into
  quantity, and until these rows existed the serving policy was blind to it.
- **The offer banner** sits on the suggestion itself, and it renders in both
  directions. When there is a coupon it says what moved the depth; when there is
  not, it says why — because the interesting half of this system is the half that
  declines to discount, and an absence with no copy on it reads as a bug.

**Now leave the basket exactly as it is and change only the world.** Two pizzas
and the wings, John Smith, nothing else touched:

| Condition | Size multiplier | Answer | Coupon |
|---|---|---|---|
| Match day, 93 °F | ×1.47 | Mini Classic Bars, 6 Count — **6 bars** | 12% off any Magnum |
| Rainy Wednesday evening | ×0.83 | Classic Milk Chocolate Bar — **5 bars** | 13% off a multipack |
| Cold Tuesday lunch | ×0.81 | Classic Milk Chocolate Bar — **5 bars** | 10% off a multipack |

> **Say:** *"Same basket, same shopper. The count went from six bars to five, the
> format went from a box to singles, and the coupon moved with the hour — and
> every one of those is a row in the table with a sentence next to it. Nothing
> here moved silently."*

Now the line that usually gets the question about pricing. Change the context to
a **cold, quiet afternoon**, then to a **hot Saturday evening with the game on**,
and read the banner's second line each time:

> *"Deeper than the usual 8% — orders are running below normal this hour, so the
> discount is doing the work."* — **10% off a multipack, saving \$1.09**
>
> *"Trimmed from the usual 8% — the store is already busy, so we are not paying
> for orders that were coming anyway."* — **5% off a multipack, saving \$0.54**

Note the number in the sentence: it reads *the usual 8%*, not a hard-coded 20%,
because the base rate belongs to whichever offer won this basket. On the
straight voucher the same mechanism swings wider — **12% on a busy Friday
dinner, 25% on a quiet Tuesday lunch**, the guardrail ceiling.

> **Say:** *"The discount is not a coupon somebody printed. It moves against how
> the hour is actually trading — twice the depth into a dead hour, half of it
> when the store is already busy — and it never moves without saying why. And the
> function that decides the depth is the same one the historical data was
> generated with — imported, not duplicated. They are not two implementations
> that agree today and drift next quarter."*

> **Say:** *"The ranking behind that banner considers every offer in the library
> and the guardrails get a veto over all of them. The shopper sees one line. The
> full reasoning is on the customer screen, where the audience for it is."*

Switch the household to **Jessica Wilson**, keep the busy hot Friday dinner, and
re-open the cart: the banner turns grey and reads **"No coupon this hour"** with
the reason attached. Same basket, same hour, different person — she buys premium
at full price and the expected value of paying her did not clear the bar. Switch
back to **Michael Johnson** and the discount returns.

> **Say:** *"Most of the time the right answer is not to discount, and on a peak
> hot Friday this policy declines for five of these six households. It never tells
> a shopper they failed to qualify — it just says the store is busy and the price
> is the price."*

**One distinction worth making if somebody asks about the guardrails.** The
frequency cap, the post-purchase window and marketing consent govern *contacting*
somebody — they gate the push notification on cue 5, and John is held there
because he ordered four hours ago. They do not gate the price a shopper sees
while they are already standing in the store with a basket in their hand. The
economic guardrails — minimum uplift, margin, the 25% cap — apply on both.

---

## Cue 7 — Show your homework

**Screen:** Demand desk, then Data **Time:** 3 min

The evaluation screen is deliberately not in this build's UI — it was an
analyst's console inside a shopper's product. The numbers did not go away; they
live in [MODEL_CARD.md](MODEL_CARD.md) and are served by `/api/analysis/*`. Have
the model card open in a second window and quote from it when asked.

| | | | | | |
|---|---|---|---|---|---|
| **+5.89 pp** | **−\$0.2570** | **+\$0.7628** | **+\$0.4584** | **95.9%** | **0.55 pp** |
| voucher lift | voucher / decision | shipped policy | uplift-greedy | p90 coverage | max recovery error |

> **Say:** *"Uplift-greedy maximises exactly what a conversion model optimises.
> It correctly finds the voucher's real lift — and it finishes below doing
> nothing, because it pays for that lift out of margin. That is the single most
> useful result in this build, and it is why Jessica does not get a discount."*

- **Demand desk.** The 48-hour p10–p90 band with the temperature overlay and the
  shaded game window, then **What to move, and by when** — two bars per SKU: the
  pale bar is what is on the shelf right now, the dark bar is what the busiest
  hour ahead of it will actually take. Where the dark bar is longer the shelf
  runs out before the peak, and it turns red. Underneath, only the red rows get a
  line, and each says the shortfall and how long the van has: *Almond Bar, 5 units
  short by friday 8p — move 6 units, van out within 0.8h.* Click **Show the
  arithmetic** if anyone wants the subtraction: *on hand + inbound − forecast p90
  to peak − safety stock*.
- **Across the network.** The same two bars, one row per store, sorted so whoever
  is short is at the top and whoever has units to lend is at the bottom. A red
  demand bar means that store is borrowing, not lending — so the transfer decision
  reads straight off the chart: pick a red row at the top, pick a green row at the
  bottom. Click any bar to load that store's 48 hours above.
- **Data.** Every table the application reads, browsable. Then point at the two
  greyed chips — `latent_traits` and `ground_truth` return `403`.

> **Say:** *"The generator knows the true answer. The application is not allowed
> to see it. That is the only reason the validation panel means anything."*

---

## Curtain

> *"Five claims, and each one has a screen behind it. Context changes demand and
> the system reacts to it live — not just the scores, the order. What somebody is
> eating changes which flavour and how many, and we can show you the control that
> proves it is not just basket size. The system knows the household — and can
> show you what it knows and what it is allowed to do with it. It writes the
> actual message, with the right size and the right offer, at the household's own
> hour, and it prices the offer against the hour rather than off a coupon sheet.
> And it can tell you which of its own ideas make money, including the one that
> does not."*

---

## Questions you should expect

Answer these the same way every time. The credibility of the whole demo rests on
the answers being unflattering where the truth is unflattering.

| Question | Answer |
|---|---|
| **Is the pairing real, or did you just wire it up to look clever?** | It is measured out of 88,000 synthetic orders, and there is a control: French fries and onion rings were given no flavour affinity at all, and they sit at 0.95–1.05× on every flavour. If the effect were an artefact of basket size, they would move too. We also found and fixed the version where it *was* an artefact — the first build's pizza→classic lift came from pack selection, not taste, and we rewrote the generator rather than patch the ranker. |
| **Why does a spicy dish not always get the flavour you say it should?** | Because the household outranks the dish. Wings tilt toward white; what most households actually get is almond, because that is what they already buy. The plate moves the odds, the person still decides. A system that always did what the dish said would be a worse one. |
| **Who decided the discount is 13% this hour?** | The demand index did. Depth moves against how the hour is trading — deeper when orders are running below normal, trimmed when the store is already busy — capped at the 25% guardrail. The function that sets it is imported by the data generator, not duplicated, so the history and the live policy cannot drift apart. |
| **Why is "similar shoppers" only 4% of the score?** | Because it is the weakest evidence we have and the easiest to be wrong about. It breaks ties. What this household actually bought, and what is on their plate right now, do the work. |
| **Where is the evaluation screen?** | Deliberately not in the product. It was an analyst's console sitting inside a shopper's app, so the numbers moved to the model card and the `/api/analysis/*` endpoints. Nothing was weakened — ask for any figure and it is one page away. |
| **Is this real data?** | No. Every row is synthetic, deterministically generated from seed `20260901`. It says so on every screen. |
| **How good is the forecast really?** | On this data, very. But it shares the generator's own demand model, so it measures parameter recovery, not prediction. Expect materially worse on live data — the model card says so in writing. |
| **Can you plug this into Uber Eats?** | Not in this build. There is an adapter stub behind a flag that is off. Nothing here calls an external service, and no Uber credentials or trade dress exist in the repository. |
| **Why doesn't the shipped policy beat always-reminder?** | On this sample it does not, and we say so. Its case is restraint — 45% of decisions left alone — plus guardrails a fixed always-send policy cannot express at all. |
| **What about the customer's privacy?** | Consent is the first thing on the customer screen and a hard block in the offer policy. The evaluation tables are unreachable from the application and return 403 in the explorer. |

---

*Magnum Now — Uber Eats-inspired reference build. Not an Uber product, not
affiliated with or endorsed by Uber. All data is synthetic.*
*Policy `policy-v1.0.0` · forecast `forecast-baseline-v1.0.0` · generator
`gen-v1.0.0` · seed `20260901` · window 2025-12-02 → 2026-09-01 (39 weeks).
Held out of the application: `ground_truth`, `latent_traits`.*
