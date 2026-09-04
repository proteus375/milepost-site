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

## 1 — Hero

| | |
| --- | --- |
| **Ratio** | 4 : 3.2, landscape |
| **Brief** | Two children and a parent at the kitchen table, mid-lesson |
| **Source** | **Paid, released** |

The one image that carries the page. It should look like an ordinary morning, not a posed family
portrait — papers spread out, someone mid-sentence, nobody looking at the camera. Warm daylight from a
window. A real kitchen with things on the counter beats a styled set.

Search: *homeschool kitchen table lesson*, *mother teaching children at home table*, *family
homeschooling morning natural light*

Avoid: everyone smiling at the lens; a tidy white room; a laptop as the focal point.

---

## 2–7 — The "what it keeps" row

Six slots, all **3 : 2 landscape**, sitting in a grid together — so they need to look like a set.
Keep them consistent in warmth and light; if two are cool-toned and four are warm the row falls apart.

### 2 — Hands and a nature journal, close in
**Free.** Close crop on hands, a pencil, a pressed leaf or a sketch. No face in frame.
Search: *nature journal hands drawing*, *child hands sketchbook leaves*, *field notebook pencil close up*

### 3 — Child reading on a sofa, warm light
**Paid if the face reads; free if shot from behind or in profile with hair falling forward.**
Search: *child reading book sofa window light*, *kid reading at home from behind*

### 4 — Wall calendar or family planner, hand writing
**Free.** A hand and a pen on a paper calendar or planner. This one carries the recordkeeping idea
and is the most on-message image on the page — worth spending time on.
Search: *hand writing on wall calendar*, *family planner pen close up*, *weekly schedule notebook writing*

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
Search: *teenager studying desk books*, *teen homework concentration home*

---

## 8–10 — The moments strip

Three slots in a row, first wider than the other two.

### 8 — Children outdoors with magnifying glass or field notes
| **Ratio** | 3 : 2.4, landscape |
**Paid if faces read; often works free because heads are down over the object.**
Search: *children magnifying glass outdoors nature study*, *kids field notes park*

### 9 — Art supplies mid-project
| **Ratio** | 1 : 1.05, essentially square |
**Free.** Paint, brushes, paper mid-work. Mess is good here.
Search: *children art supplies paint mid project*, *kids craft table overhead*

### 10 — Siblings reading together
| **Ratio** | 1 : 1.05, essentially square |
**Paid if faces read; free from behind or overhead.**
Search: *siblings reading book together*, *two children sharing a book*

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

Eleven images, four of them needing releases. That is one month of a small Adobe Stock plan (about
$30 for ten assets) or a one-off credit pack, and free downloads for the rest. Stocksy costs more per
image and looks markedly less like stock, which is worth considering for slot 1 alone since it sets
the tone for everything else.

Whatever you buy, **keep the licence receipts and the asset IDs**. If a question about a photograph
ever comes up you want the paperwork, and it is far easier to file now than reconstruct later.

## Alt text

Every `<img>` needs an `alt` describing what is in the picture, for screen readers and for the days
the image does not load. Write what someone would say if they were describing it aloud — *"Two
children and their mother at the kitchen table, papers spread out"* — not *"homeschool photo"*.
