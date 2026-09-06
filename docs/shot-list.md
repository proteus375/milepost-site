# Milepost — photo shot list

Eleven slots on the home page. Each one is a `.photo` div in
`templates/pages/home.html`, labelled with `data-shot`. Replacing one with an `<img>` **inside the
same div** does not move the layout:

```
<div class="photo"><img src="{% static 'img/kitchen-table.jpg' %}"
     alt="Two children and their mother at the kitchen table"></div>
```

Files go in `static/img/`. Aspect ratios below are enforced by CSS — a source image at a different
ratio will be cropped to fit by `object-fit: cover`, so what matters is that the subject sits
comfortably inside the given shape, not that the file matches it exactly.

## The rule that decides where to buy

**Any slot where a child's face is identifiable needs a model release**, and a release for a minor
means a parent or guardian signed it. Free libraries do not supply releases — Unsplash says outright
that it does not guarantee commercial use of images with identifiable people and that the
responsibility is yours; Pexels does not address releases at all. A marketing site is commercial use
of a likeness.

So the list splits in two, and the split saves money as well as risk:

- **Paid, model-released** — Adobe Stock, iStock, Shutterstock, Stocksy. Four slots.
- **Free is fine** — Unsplash, Pexels, Pixabay. Seven slots, because they are framed on hands,
  materials, backs of heads or an empty room. **These are not the compromise slots.** Hands on a
  nature journal is a better photograph than a child smiling at a camera, and it is the register the
  rest of the page is written in.

If you want to cut the paid list further, slots 3, 7 and 10 all work shot from behind or over the
shoulder, which removes the face and moves them to the free column. Only slot 1 really wants faces,
because it is the hero.

---

## The rule that decides who is in the frame

The first version of this document specified framing, aspect ratio and model releases in detail and
said nothing at all about casting. Eleven photographs were then bought against it. Nine of them show
people, and every person in all nine — every parent, every child — is white.

That is not a failure of taste on anyone's part. It is what the search terms above return. *Mother
teaching children at home*, *family homeschooling morning natural light*, *siblings reading book
together* — every one of those queries has a default on every stock library, and the default is what
arrived. A brief that does not name casting has still made a casting decision; it has just made it
by accident, and handed it to a search ranking.

So it gets named.

**Across the set, no one kind of family is the default.** This is a rule about the set, not about
any single photograph — a slot is not required to represent anybody, and no photograph should look
like it was chosen to fill a quota. The test is what somebody sees after scrolling the whole page:
if a visitor can tell at a glance that this product pictures one kind of household, the set has
failed, however good each image is on its own.

Held against the eleven slots, that means:

- **The people slots — 1, 3, 5, 7, 8, 10 — must not all be the same family twice over.** Six slots
  is enough range to show more than one skin tone, more than one hair texture, and more than one
  shape of household without any of it looking deliberate. Fewer than half being white is not the
  target and neither is a quota; one being the whole cast is the thing to avoid.
- **The hero carries the most weight.** It is the first image, it is the largest, and it sets what a
  visitor assumes the rest is about. Budget accordingly — if only one slot gets extra sourcing time,
  it is this one.
- **Household shape counts too.** Homeschooling includes single parents, grandparents teaching,
  co-op groups and two-father and two-mother households. The current set has two photographs of
  fathers teaching, which cuts against the default that a homeschooling parent is a mother — that
  was a good instinct and it should survive any reshoot.
- **Disability is part of this and is usually forgotten.** A child in a wheelchair at the kitchen
  table, or a hearing aid visible in profile, is an ordinary morning for a lot of families and is
  almost never what a stock search returns unless it is asked for.
- **Do not solve it with one photograph.** A single image of a Black family among eight white ones
  reads worse than the original set, because it reads as an apology. Range across the set, not a
  designated slot.

### Searching for it

Stock libraries respond to explicit terms and mostly ignore implicit ones. Adobe Stock, iStock and
Getty all support filtering on ethnicity, age and number of people directly in the sidebar; use the
filter rather than hoping the query carries it.

Add to the search terms in each slot below, and run each slot's search more than once with
different terms rather than taking the first grid:

> *Black family homeschooling*, *Latino mother teaching child at home*, *Asian father and daughter
> studying*, *mixed race family kitchen table lesson*, *grandmother teaching grandchild at home*,
> *child wheelchair desk learning*, *hijab mother child homework*

The release rule above does not change. A model release is still required wherever a child's face is
identifiable, and it is required for exactly the same reasons whoever is in the picture.

### The set as it stands

Audited by opening all eleven, not by reading the file names. Everyone visible in every photograph
that has a person in it is white. Cross a row off as it is replaced.

| Slot | File | Who is in it | Action |
| --- | --- | --- | --- |
| 1 Hero | ~~`hero-map.jpg`~~ → `hero-family-table.jpg` | Father and mother, two young sons | **Done.** `hero-map.jpg` is now unused |
| 2 Journal | `activities-drawing.jpg` | One child's hand and forearm, light skin | Recast when convenient — a hand still has a skin tone |
| 3 Reading | `courses-father-daughter.jpg` | White father, white daughter | **Recast** |
| 4 Planner | `week-planner.jpg` | Two hands at a laptop, light skin | Recast when convenient |
| 5 Laptop | `attendance-laptop.jpg` | Mother and son at the kitchen table | **Done.** Replaced in place |
| 6 Portfolio | `portfolio-papers.jpg` | No people | Keep |
| 7 Teen | `transcript-teen.jpg` | White teenage girl | **Recast** |
| 8 Outdoors | `outdoors-magnifier.jpg` | Boy with a magnifying glass and a leaf | **Done.** Replaced in place |
| 9 Art | `art-painting.jpg` | Four white children | **Recast** — four children in one frame is the cheapest range on the page. One candidate was rejected: see below |
| 10 Siblings | `reading-siblings.jpg` | Two white children | **Recast** |
| 11 Closing | `closing-desk.jpg` | No people | Keep |

Seven of these need a model release, which is unchanged from the original brief — slots 1, 3, 5, 7,
8, 9 and 10 all show identifiable faces. Slots 2 and 4 are hands and can come from a free library.

**Three replaced so far.** The hero now has a father teaching, which changes what slot 5 has to
carry: the point about not losing a father-teaching photograph is satisfied by slot 1, so slot 5 was
free to change. Five to go — 2, 3, 4, 7, 9 — plus 10.

**Store each file at its slot's own shape.** The originals were all 16:9 while the slots render at
4:3.2, 3:2 and 3:2.4, so `object-fit: cover` was throwing away the sides of every one of them. The
three replacements are cut to the ratio they display at, which is why nothing is lost off the edge
and the files are smaller.

### One candidate was rejected, and why it is worth recording

A generated image was considered for slot 9 and turned down on two grounds.

It read as AI-generated: a paintbrush whose handle tapered into a blob with no ferrule and which was
not touching the gourd it was supposedly painting, fingers that merged where they wrapped an object,
paint jars with no lids or labels, and splatter distributed evenly with no directionality. Any one
of those is arguable; together they are not.

Separately, and regardless of how it was made, it was a Halloween scene — painted jack-o'-lantern
faces date an evergreen page to October, on a slot whose brief asks only for paint, brushes and
mess.

The first reason is the one that generalises. This page argues that these are real families keeping
real records, which makes invented children a poor fit for it whatever the licence says, and a bad
thing to be found out about later. Check provenance on anything bought from here on, and keep it
with the receipts.

Slot 9 is worth doing first after the hero: four children in one frame carries more range for one
purchase than any other slot on the page, and it is already the busiest image.

Replacing a file in place needs no template change — the `<img>` tags in
`templates/pages/home.html` reference these names and the CSS crops to fit. **The `alt` text does
need changing**, because it describes the people in the photograph and will otherwise describe the
wrong ones.

### The cast, slot by slot

Allocated as a set rather than searched for slot by slot, because nine independent searches each
told to "be diverse" produce nine independent results and no composition. This is a starting
allocation — shuffle it freely, but shuffle it as a whole, so that whatever moves out of one slot
moves into another.

| Slot | Cast | Why this slot |
| --- | --- | --- |
| 1 Hero | Black mother or father with two children | The largest and first image, and the one the old default hit hardest. If one slot gets extra sourcing time it is this |
| 2 Journal | Hands, deep brown skin | Free library, no release, and a hand still carries a skin tone |
| 3 Reading | South Asian child on a sofa | Free if shot from behind or in profile, which also fits the slot's framing |
| 4 Planner | Hands, any tone not already used twice | Deliberately unremarkable — the row should not read as a parade |
| 5 Laptop | **Keep the current photograph** | A father teaching, which cuts against the assumption that a homeschooling parent is a mother. Do not spend a purchase undoing that |
| 7 Teen | Latina or Latino teenager at a desk | Also carries the "this works past age nine" job, so it wants to read clearly as older |
| 8 Outdoors | East Asian child, or a pair | Heads down over the magnifier, so it often lands in the free column |
| 9 Art | Four children, genuinely mixed group | The best value on the page: one purchase, four children, and it is already the busiest frame |
| 10 Siblings | Two Black or mixed-heritage siblings — **or** the disability slot | Seated, close to camera and calm, so a hearing aid or a wheelchair reads naturally here rather than as the point of the picture |

Eight slots to source. Four need releases — 1, 3, 7 and 10 — which is back to the original plan's
budget, because 8 and 9 both work with heads down or from overhead.

**Where the disability line lands.** Slot 10 is the suggestion, but slot 1 is the braver choice and
the better one: a wheelchair at the kitchen table in the hero says the thing without a caption. It
is harder to source well, so decide before spending on the hero rather than after.

---

## 1 — Hero

| | |
| --- | --- |
| **Ratio** | 4 : 3.2, landscape |
| **Brief** | Two children and a parent at the kitchen table, mid-lesson |
| **Source** | **Paid, released** |

The one image that carries the page. It should look like an ordinary morning, not a posed family
portrait — papers spread out, someone mid-sentence, nobody looking at the camera. Warm daylight from a
window. A real kitchen with things on the counter beats a styled set.

**Cast:** Black mother or father with two children, primary-school age.

**Search:** *Black family homeschool kitchen table* · *African American mother teaching children at
home* · *Black father helping children with schoolwork* · *Black family learning together morning
light*

**Filters:** Number of people 3 · Ethnicity: Black/African American · Age: children and adults ·
Photos only · Horizontal.

**Reject:** anyone looking at the lens; a whiteboard or any classroom prop; a laptop as the focal
point; a styled all-white kitchen with nothing on the counter.

---

## 2–7 — The "what it keeps" row

Six slots, all **3 : 2 landscape**, sitting in a grid together — so they need to look like a set.
Keep them consistent in warmth and light; if two are cool-toned and four are warm the row falls apart.

### 2 — Hands and a nature journal, close in
**Free.** Close crop on hands, a pencil, a pressed leaf or a sketch. No face in frame.

**Cast:** Hands and forearm, deep brown skin. A hand carries a skin tone, which is why this slot
counts.

**Search:** *Black child hands nature journal* · *dark skin hands drawing sketchbook* · *child hands
pressed leaves notebook*

**Filters:** Number of people 1 · Ethnicity: Black/African American · Photos only.

**Reject:** adult hands — rings, a watch or manicured nails read as adult immediately; a flat-lay so
tidy there is no evidence of a person.

### 3 — Child reading on a sofa, warm light
**Paid if the face reads; free if shot from behind or in profile with hair falling forward.**

**Cast:** South Asian child. Shot from behind or in profile keeps this in the free column, which
suits the slot's framing anyway.

**Search:** *Indian child reading book at home* · *South Asian girl reading sofa window light* ·
*child reading from behind warm light*

**Filters:** Age: children · Ethnicity: South Asian/Indian · Photos only.

**Reject:** a posed portrait; a stack of books arranged as a prop; a reading nook that looks
styled.

### 4 — Wall calendar or family planner, hand writing
**Free.** A hand and a pen on a paper calendar or planner. This one carries the recordkeeping idea
and is the most on-message image on the page — worth spending time on.

**Cast:** Hands, whichever tone is not already doubled up by the time you reach this slot. This one
is deliberately unremarkable — the row should not read as a parade.

**Search:** *hand writing family planner calendar* · *hands weekly schedule notebook pen* · *writing
on wall calendar close up*

**Filters:** Number of people 1 · Photos only · Horizontal.

**Reject:** a corporate desk; a printed year planner that reads as an office wall; a phone in
frame.

### 5 — Parent and child at a laptop together
**Paid, released.** Both faces likely visible. Shoulder to shoulder, screen not readable.
Search: *parent child laptop learning together home*, *mother son computer homework*

### 6 — Printed portfolio pages and photographs on a table
**Free.** Paper, worksheets, a few photographs laid out. No people needed at all. This is the
transcript-and-portfolio idea made physical.
Search: *school work papers spread on table*, *homework worksheets photographs desk flat lay*

### 7 — Older teenager studying at a desk
**Paid if the face reads; free from behind.** Deliberately older than the others — the page needs to
say this works past age nine.

**Cast:** Latina or Latino teenager, clearly older than every other child on the page.

**Search:** *Hispanic teenager studying at home desk* · *Latina teen homework concentration* ·
*Latino student writing notes at window desk*

**Filters:** Age: teenagers · Ethnicity: Hispanic/Latino · Photos only.

**Reject:** anything that reads as a school or a dorm room; a graduation cap; a phone in frame; a
model who reads as a university student rather than a teenager.

---

## 8–10 — The moments strip

Three slots in a row, first wider than the other two.

### 8 — Children outdoors with magnifying glass or field notes
**Ratio:** 3 : 2.4, landscape

**Paid if faces read; often works free because heads are down over the object.**

**Cast:** East Asian child, or a pair of children.

**Search:** *Asian child magnifying glass outdoors* · *children examining leaves garden nature
study* · *kids field notebook outdoors close up*

**Filters:** Age: children · Ethnicity: East Asian · Photos only · Horizontal.

**Reject:** a school trip in matching uniforms; over-saturated park green; a staged science kit.

### 9 — Art supplies mid-project
**Ratio:** 1 : 1.05, essentially square

**Free.** Paint, brushes, paper mid-work. Mess is good here.

**Cast:** Four children, genuinely mixed. This is the best value on the page — one purchase, four
children, and it is already the busiest frame.

**Search:** *multiethnic children painting together table* · *diverse group of kids art class craft
table* · *children painting overhead view mixed group*

**Filters:** Number of people 4+ · Age: children · Photos only. **Leave ethnicity unset here** and
judge by eye: the filter returns one group per search, and this slot needs several in one frame.

**Reject:** matching smocks; a visible teacher, which makes it a classroom; every child facing the
camera.

### 10 — Siblings reading together
**Ratio:** 1 : 1.05, essentially square

**Paid if faces read; free from behind or overhead.**

**Cast:** Two Black or mixed-heritage siblings — **or** this is the disability slot. Seated, close to
camera and calm, so a hearing aid or a wheelchair reads as part of the scene rather than as the
point of the picture.

**Search:** *Black siblings reading book together* · *brother and sister sharing a book at home* ·
*child hearing aid reading with sibling* · *child wheelchair reading at home*

**Filters:** Number of people 2 · Age: children · Photos only.

**Reject:** an age gap wide enough to read as parent-and-child; pyjamas or a bedtime scene — this is
a daytime learning page.

---

## 11 — Closing

| | |
| --- | --- |
| **Ratio** | 4 : 3, landscape |
| **Brief** | Warm, quiet domestic scene — books, a table, morning light |
| **Source** | **Free** |

No people. The page ends on calm rather than on activity. Books, a mug, a table, light across it.

Search: *books table morning light home*, *quiet reading corner natural light*, *still life books window*

---

## Buying

Eleven images. The original plan was four of them needing releases; the set actually bought has
seven identifiable faces, because several slots that could have been shot from behind were not. A
recast is the moment to decide which of those go back to the free column — slots 3, 7 and 10 all
still work over the shoulder, and that is three releases saved.

Budget for the paid ones as one month of a small Adobe Stock plan (about $30 for ten assets) or a
one-off credit pack, and free downloads for the rest. Stocksy costs more per
image and looks markedly less like stock, which is worth considering for slot 1 alone since it sets
the tone for everything else.

Whatever you buy, **keep the licence receipts and the asset IDs**. If a question about a photograph
ever comes up you want the paperwork, and it is far easier to file now than reconstruct later.

### The generated option, and what is unresolved about it

Adobe Stock now has AI Studio, which generates images with Firefly inside the same subscription.
Adobe states that Firefly-generated content is commercially safe because the model was trained on
content Adobe has rights to, and that it may be used in commercial projects.

For this page the appeal is obvious: casting stops being a search problem. You describe the family
you want and get it, rather than hoping a ranking surfaces one.

**Two things are not settled and should be before spending on it.** Adobe's commercial-use page does
not say whether a generated depiction of a person needs a release, and it does not address
generating children at all — which is the one thing this page is full of. Neither silence is
permission. Ask Adobe support directly and keep the answer with the licence receipts.

There is also a judgement separate from the legal one. A page whose argument is *these are real
families keeping real records* is a page where invented children are a slightly odd choice, and it
is the kind of thing that reads badly if it comes out later. Worth deciding on purpose rather than
by default.

## Alt text

Every `<img>` needs an `alt` describing what is in the picture, for screen readers and for the days
the image does not load. Write what someone would say if they were describing it aloud — *"Two
children and their mother at the kitchen table, papers spread out"* — not *"homeschool photo"*.
