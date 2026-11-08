# T0 documents, one by one

Every T0 document in run-20261107T203600Z, with the measurements behind the
verdict and the specific things to look at. This is a worklist, not a conclusion:
each section names a document, what differs numerically, and where.

63 documents. Symptoms overlap; a document can appear in several groups.

| symptom | documents |
|---|---|
| text missing or reduced | 23 |
| page count differs | 24 |
| images missing | 10 |
| shapes missing | 16 |
| placement findings | 37 |

> **Reading the image counts.** They are not comparable between engines.
> LibreOffice renders `.wmf` and `.emf` metafiles as vector drawings rather than
> embedded images, so a document can show "images 175 vs 59" with no content
> missing at all — `bz75208-157040` has 2891 drawings in Collabora against 427
> in Word for exactly that reason. Only `.pict` is genuinely dropped: one
> document, 46 images, verified by rendering a bare one (`images=0, drawings=1`).
> Treat "images" in the table below as "raster images", not "pictures".

## The most extreme cases, in order of how obvious they should be on a page

| document | what the measurements say |
|---|---|
| `bz34722-43806` | 139 words in Word, **0 in Collabora** |
| `bz34722-63648` | 172 words vs 0, shapes 76 vs 3 |
| `bz52576-64768` | 4 pages vs **16**, shapes 6 vs 1 |
| `bz58180-136153` | 4521 words vs **559**, 6 pages vs 5 |
| `bz45284-57967/57968` | 3 words vs 0 |
| `bz55459-67866` | 15 pages vs 21, **images 65 vs 17** |
| `bz33590-53915` | 82 words vs 21 |
| `bz66525-95109` | 157 words vs 8 |

63 documents.

| document | what differs |
|---|---|
| `bz33590-42590` | text 140 vs 125 tokens |
| `bz33590-53915` | text 82 vs 21 tokens |
| `bz34722-43806` | text 139 vs 0 tokens |
| `bz34722-63648` | text 172 vs 0 tokens · shapes 76 vs 3 |
| `bz36791-108642` | images 1 vs 0 |
| `bz36791-46282` | text only |
| `bz43699-57030` | text 83 vs 65 tokens · shapes 2 vs 0 · placement visible {'displaced': 1} |
| `bz45284-57967` | text 3 vs 0 tokens |
| `bz45284-57968` | text 3 vs 0 tokens |
| `bz45386-171194` | pages 8 vs 7 · placement breaking {'outside': 2, 'displaced': 137} |
| `bz47240-58329` | text only |
| `bz47596-165620` | text 70 vs 61 tokens · placement breaking {'outside': 1, 'displaced': 4} |
| `bz49641-61233` | placement breaking {'displaced': 17, 'outside': 1} |
| `bz50869-154099` | pages 2 vs 3 · shapes 30 vs 15 · placement breaking {'outside': 1} |
| `bz51127-63083` | pages 4 vs 3 · placement breaking {'displaced': 104, 'outside': 1} |
| `bz51129-163093` | pages 1 vs 2 |
| `bz52576-180433` | shapes 6 vs 1 |
| `bz52576-64768` | pages 4 vs 16 · text 925 vs 834 tokens · shapes 6 vs 1 |
| `bz55459-67866` | pages 15 vs 21 · images 65 vs 17 · placement visible {'displaced': 548} |
| `bz57725-70819` | pages 3 vs 2 |
| `bz58180-136153` | pages 6 vs 5 · text 4521 vs 559 tokens · images 3 vs 2 · shapes 4 vs 2 · placement visible {'displaced': 20} |
| `bz58452-135646` | images 1 vs 0 |
| `bz59674-163608` | pages 2 vs 1 |
| `bz61213-75238` | pages 7 vs 6 · placement visible {'displaced': 57} |
| `bz61473-75540` | pages 2 vs 1 · shapes 95 vs 36 · placement visible {'displaced': 1} |
| `bz61995-77935` | shapes 18 vs 8 · placement visible {'displaced': 203} |
| `bz62613-157544` | pages 13 vs 12 · images 13 vs 12 · shapes 488 vs 189 · placement breaking {'displaced': 56, 'outside': 2} |
| `bz62613-77075` | pages 9 vs 12 · shapes 487 vs 116 · placement visible {'displaced': 70} |
| `bz65260-80150` | images 1 vs 0 |
| `bz65266-80154` | text 5 vs 1 tokens |
| `bz66525-158577` | text 157 vs 69 tokens · placement visible {'displaced': 1} |
| `bz66525-95109` | text 157 vs 8 tokens |
| `bz67339-83023` | pages 3 vs 4 · images 9 vs 5 · placement visible {'displaced': 14} |
| `bz68326-163233` | pages 1 vs 2 · text 465 vs 18 tokens |
| `bz68326-163238` | text only |
| `bz68326-84324` | pages 1 vs 23 · placement visible {'displaced': 1} |
| `bz69175-160866` | placement breaking {'outside': 1} |
| `bz69175-85548` | shapes 41 vs 29 · placement visible {'displaced': 8} |
| `bz69686-160843` | text only |
| `bz72388-151985` | placement visible {'displaced': 79} |
| `bz72388-90342` | placement visible {'displaced': 66} |
| `bz73977-125317` | pages 7 vs 8 · shapes 280 vs 98 · placement visible {'displaced': 122} |
| `bz75154-136053` | pages 1 vs 2 · placement visible {'displaced': 1} |
| `bz75154-163517` | pages 1 vs 2 · placement visible {'displaced': 1} |
| `bz75154-163518` | pages 3 vs 2 · shapes 4 vs 3 |
| `bz75208-157040` | pages 174 vs 172 · images 175 vs 59 · placement breaking {'displaced': 1107, 'outside': 6} |
| `bz75208-167513` | text 164 vs 119 tokens · placement visible {'displaced': 9} |
| `bz75208-167516` | text 110 vs 82 tokens · placement visible {'displaced': 15} |
| `bz75208-94362` | pages 173 vs 170 · images 221 vs 46 · shapes 348 vs 16 · placement breaking {'displaced': 817, 'outside': 6} |
| `bz75281-136950` | text 23 vs 14 tokens |
| `bz79920-100881` | images 2 vs 0 · shapes 49 vs 27 |
| `bz81736-103647` | text 157 vs 139 tokens · placement visible {'displaced': 9} |
| `dk-tracked-changes-heavy-1` | placement visible {'displaced': 4} |
| `dk-tracked-changes-heavy-2` | placement visible {'displaced': 4} |
| `dk-tracked-changes-heavy-3` | placement visible {'displaced': 4} |
| `hu-gov-9.11._Bet-tlap_tart-zkod-si_enged-ly_ir-nti_k-relemhez_-_Kutat-s_illetve_kutat-i_hossz-_t-v-_mobilit-s_HU` | pages 3 vs 4 |
| `hu-gov-9.13._Bet-tlap_tart-zkod-si_enged-ly_ir-nti_k-relemhez_-_Tanulm-nyok_folytat-sa_illetve_hallgat-i_mobilit-s_HU` | placement breaking {'outside': 1} |
| `hu-gov-9.16._Bet-tlap_tart-zkod-si_enged-ly_ir-nti_k-relemhez_-_Gyakornoki_tev-kenys-g_folytat-sa_HU` | placement breaking {'outside': 1} |
| `hu-gov-9.21._Appendix_to_an_application_for_a_residence_permit_-_Voluntary_service` | placement breaking {'outside': 1} |
| `hu-gov-9.21._Bet-tlap_tart-zkod-si_enged-ly_ir-nti_k-relemhez_-_-nk-ntes_tev-kenys-g_folytat-sa_HU` | placement breaking {'outside': 1} |
| `hu-gov-9.3._Bet-tlap_tart-zkod-si_enged-ly_ir-nti_k-relemhez_-_Vend-gbefektet-_HU` | pages 1 vs 2 · placement visible {'displaced': 1} |
| `hu-gov-ENG_Tart-zkod-si_k-rtya_ki-ll-t-sa_meghosszabb-t-sa_3` | shapes 64 vs 48 · placement visible {'displaced': 7} |
| `hu-gov-tiokm-ny-ig-nyl-lap1` | text only |

## `bz33590-42590`

**Differs:** text 140 vs 125 tokens
**Words Word has that Collabora does not:** `Z`, `Z`, `Z`, `Z`

## `bz33590-53915`

**Differs:** text 82 vs 21 tokens
**Words Word has that Collabora does not:** `1`, `6`, `6`, `1`
**Pages holding less text:** p1 (82 vs 21 words)

## `bz34722-43806`

**Differs:** text 139 vs 0 tokens
**Words Word has that Collabora does not:** `Lapo`, `Nr`, `1`, `UAB`
**Pages holding less text:** p1 (139 vs 0 words)

## `bz34722-63648`

**Differs:** text 172 vs 0 tokens; shapes 76 vs 3
**Words Word has that Collabora does not:** `Zakázka`, `číslo`, `Schválil`, `Již`
**Pages holding less text:** p1 (172 vs 0 words)

## `bz36791-108642`

**Differs:** images 1 vs 0

## `bz36791-46282`


## `bz43699-57030`

**Differs:** text 83 vs 65 tokens; shapes 2 vs 0; placement visible {'displaced': 1}
**Words Word has that Collabora does not:** `0`, `20`, `40`, `60`
**Pages holding less text:** p1 (83 vs 65 words)
**Moved:** `Qtr` on page 1 by 35 pt

## `bz45284-57967`

**Differs:** text 3 vs 0 tokens
**Words Word has that Collabora does not:** `456`, `123c`, `a`
**Pages holding less text:** p1 (3 vs 0 words)

## `bz45284-57968`

**Differs:** text 3 vs 0 tokens
**Words Word has that Collabora does not:** `456`, `123c`, `a`
**Pages holding less text:** p1 (3 vs 0 words)

## `bz45386-171194`

**Differs:** pages 8 vs 7; placement breaking {'outside': 2, 'displaced': 137}
**Words Word has that Collabora does not:** `document`, `Pag`, `1`, `8`, `document`, `Pag`, `8`, `Premessa`, `document`, `Pag`, `8`
**Pages holding less text:** p1 (52 vs 29 words), p7 (502 vs 285 words)
**Outside the margin:** `bug45386-45386_example.doc` on page 2 at x=345
**Moved:** `del` on page 2 by -363 pt

## `bz47240-58329`


## `bz47596-165620`

**Differs:** text 70 vs 61 tokens; placement breaking {'outside': 1, 'displaced': 4}
**Words Word has that Collabora does not:** `7`, `8`, `9`, `7`
**Outside the margin:** `2` on page 2 at x=392
**Moved:** `` on page 2 by 156 pt

## `bz49641-61233`

**Differs:** placement breaking {'displaced': 17, 'outside': 1}
**Words Word has that Collabora does not:** `NAME`, `____________________________________________________________________________________________________`, `____________________________________________________________________________________________________`, `JOB`, `NAME`, `FROM`, `TO`, `COURSE`, `YEAR`, `NAME`, `EMPLOYER`, `JOB`
**Pages holding less text:** p4 (193 vs 114 words)
**Moved:** `YES` on page 1 by -37 pt
**Moved:** `NO` on page 1 by -37 pt

## `bz50869-154099`

**Differs:** pages 2 vs 3; shapes 30 vs 15; placement breaking {'outside': 1}
**Words Word has that Collabora does not:** `06`, `November`, `2026`, `Document1`
**Pages holding less text:** p1 (34 vs 10 words)
**Outside the margin:** `MANAGEMENT` on page 2 at x=421

## `bz51127-63083`

**Differs:** pages 4 vs 3; placement breaking {'displaced': 104, 'outside': 1}
**Words Word has that Collabora does not:** `This`, `fixcentral`, `software`, `su`, `sufficient`, `flexibility`, `settings`, `file`, `Configuring`
**Moved:** `environment` on page 1 by -33 pt
**Moved:** `for` on page 1 by -36 pt

## `bz51129-163093`

**Differs:** pages 1 vs 2

## `bz52576-180433`

**Differs:** shapes 6 vs 1
**Words Word has that Collabora does not:** `Halfday`, `Additional`, `Antara`, `Antara`, `Antara`, `Antara`

## `bz52576-64768`

**Differs:** pages 4 vs 16; text 925 vs 834 tokens; shapes 6 vs 1
**Words Word has that Collabora does not:** `Jl`, `Laksda`, `Adisucipto`, `No`, `Jl`, `Laksda`, `Adisucipto`, `No`, `Jl`, `Laksda`, `Adisucipto`, `No`
**Pages holding less text:** p1 (199 vs 23 words), p2 (298 vs 55 words), p3 (329 vs 53 words)

## `bz55459-67866`

**Differs:** pages 15 vs 21; images 65 vs 17; placement visible {'displaced': 548}
**Words Word has that Collabora does not:** `רב`, `שנתי`, `נתוני`, `טווח`, `רב`, `שנתי`, `תשס`, `ח`, `רב`, `שנתי`, `תשס`, `ח`
**Pages holding less text:** p6 (373 vs 234 words), p8 (328 vs 254 words), p9 (325 vs 192 words)
**Moved:** `"` on page 2 by -31 pt
**Moved:** `הלמידה` on page 2 by -31 pt

## `bz57725-70819`

**Differs:** pages 3 vs 2

## `bz58180-136153`

**Differs:** pages 6 vs 5; text 4521 vs 559 tokens; images 3 vs 2; shapes 4 vs 2; placement visible {'displaced': 20}
**Words Word has that Collabora does not:** `Stand`, `April`, `2005`, `auf`, `Stand`, `April`, `2005`, `Seite`, `Stand`, `April`, `2005`, `Berufsausbildungsvertrag`
**Pages holding less text:** p1 (327 vs 220 words), p2 (256 vs 67 words), p3 (321 vs 0 words)
**Moved:** `der` on page 1 by 34 pt
**Moved:** `Berufsausbildungsverhältnisse` on page 1 by 41 pt

## `bz58452-135646`

**Differs:** images 1 vs 0

## `bz59674-163608`

**Differs:** pages 2 vs 1

## `bz61213-75238`

**Differs:** pages 7 vs 6; placement visible {'displaced': 57}
**Pages holding less text:** p6 (413 vs 243 words)
**Moved:** `ОУО` on page 3 by 40 pt
**Moved:** `ОУО` on page 3 by 113 pt

## `bz61473-75540`

**Differs:** pages 2 vs 1; shapes 95 vs 36; placement visible {'displaced': 1}
**Words Word has that Collabora does not:** `𝑛𝑜`, `𝑍𝛼2`, `𝑠2`, `𝑒2`, `𝑓`, `𝑝𝑞`, `𝑛`, `𝑓`
**Moved:** `=` on page 1 by 118 pt

## `bz61995-77935`

**Differs:** shapes 18 vs 8; placement visible {'displaced': 203}
**Words Word has that Collabora does not:** `6`, `Office`, `Office`, `This`, `6`, `flash`, `first`, `first`, `6`, `afternoon`, `Attendance`, `attend`
**Moved:** `1.` on page 1 by 72 pt
**Moved:** `design` on page 1 by 72 pt

## `bz62613-157544`

**Differs:** pages 13 vs 12; images 13 vs 12; shapes 488 vs 189; placement breaking {'displaced': 56, 'outside': 2}
**Words Word has that Collabora does not:** `Rev`, `1`, `October`, `2010`, `Rev`, `1`, `October`, `2010`, `Rev`, `1`, `October`, `2010`
**Pages holding less text:** p4 (561 vs 216 words), p7 (511 vs 305 words), p8 (305 vs 7 words)
**Moved:** `is` on page 1 by -43 pt
**Moved:** `an` on page 1 by -43 pt

**Extra detail:** 12 pages vs 13; 56 words shifted 40-130 pt inside their
lines (reflow, not displacement); one revision line missing
(`Rev`, `1`, `October`, `2010`). The document is named
`bug62613-Bugged-Spacing-MSO.docx`, and the symptom matches the name:
line breaking and spacing differ, the text itself is present.

## `bz62613-77075`

**Differs:** pages 9 vs 12; shapes 487 vs 116; placement visible {'displaced': 70}
**Pages holding less text:** p2 (504 vs 78 words), p4 (523 vs 216 words), p7 (403 vs 305 words)
**Moved:** `is` on page 1 by -43 pt
**Moved:** `an` on page 1 by -43 pt

## `bz65260-80150`

**Differs:** images 1 vs 0

## `bz65266-80154`

**Differs:** text 5 vs 1 tokens
**Words Word has that Collabora does not:** `a`, `bc`, `d`, `ef`
**Pages holding less text:** p1 (5 vs 1 words)

## `bz66525-158577`

**Differs:** text 157 vs 69 tokens; placement visible {'displaced': 1}
**Words Word has that Collabora does not:** `1`, `1`, `1`, `0`
**Pages holding less text:** p1 (157 vs 69 words)
**Moved:** `M` on page 1 by 62 pt

## `bz66525-95109`

**Differs:** text 157 vs 8 tokens
**Words Word has that Collabora does not:** `1`, `1`, `1`, `0`
**Pages holding less text:** p1 (157 vs 8 words)

## `bz67339-83023`

**Differs:** pages 3 vs 4; images 9 vs 5; placement visible {'displaced': 14}
**Words Word has that Collabora does not:** `Central`
**Pages holding less text:** p1 (10 vs 1 words)
**Moved:** `to` on page 2 by -283 pt
**Moved:** `product` on page 2 by -157 pt

## `bz68326-163233`

**Differs:** pages 1 vs 2; text 465 vs 18 tokens
**Words Word has that Collabora does not:** `ЗАЯВЛЕНИЕ`, `о`, `присоединении`, `Получателя`
**Pages holding less text:** p1 (465 vs 18 words)

**Extra detail:** 447 tokens missing; Collabora renders 18 words on page 1
and an empty page 2, where Word fills one page with 451 words.
The text is in the model - `--convert-to txt/odt/docx` all contain it -
so this is layout, not import. Converting the same document to ODT and
rendering that gives 194 words, still far short of 451, so the failure
reproduces without the DOCX importer. Removing the 57 `w:trHeight`
entries, or forcing `hRule="atLeast"`, changes nothing (18 words).

## `bz68326-163238`


## `bz68326-84324`

**Differs:** pages 1 vs 23; placement visible {'displaced': 1}
**Words Word has that Collabora does not:** `ЗАЯВЛЕНИЕ`, `присоединении`, `Получателя`, `Договору`
**Pages holding less text:** p1 (465 vs 69 words)
**Moved:** `-` on page 1 by 41 pt

## `bz69175-160866`

**Differs:** placement breaking {'outside': 1}
**Words Word has that Collabora does not:** `The`, `King`, `s`, `Experience270`
**Outside the margin:** `K` on page 1 at x=576

## `bz69175-85548`

**Differs:** shapes 41 vs 29; placement visible {'displaced': 8}
**Words Word has that Collabora does not:** `The`, `King`, `s`, `Experience`, `The`, `King`, `s`, `Experience`, `The`, `King`, `s`, `Experience`
**Pages holding less text:** p5 (49 vs 14 words)
**Moved:** `you` on page 3 by 157 pt
**Moved:** `you` on page 3 by 197 pt

## `bz69686-160843`


## `bz72388-151985`

**Differs:** placement visible {'displaced': 79}
**Words Word has that Collabora does not:** `x`, `x`, `Yxxxxxxxxx`, `x`, `Yxxxxxxxxx`, `0`, `0`, `000000`, `Yxxxxxxxxx`, `x`, `000000`, `0`
**Moved:** `Yxx` on page 1 by 31 pt
**Moved:** `xxx` on page 1 by 302 pt

## `bz72388-90342`

**Differs:** placement visible {'displaced': 66}
**Words Word has that Collabora does not:** `6`, `000000`, `000000`, `000000`, `000000`, `000000`, `000000`
**Moved:** `Yxxx` on page 1 by 34 pt
**Moved:** `Yxxx` on page 1 by 42 pt

## `bz73977-125317`

**Differs:** pages 7 vs 8 — see `families/0012-long-footnote-breaks-page.html`; shapes 280 vs 98; placement visible {'displaced': 122}
**Pages holding less text:** p1 (572 vs 14 words)
**Moved:** `odio` on page 2 by 59 pt
**Moved:** `et` on page 2 by 299 pt

## `bz75154-136053`

**Differs:** pages 1 vs 2; placement visible {'displaced': 1}
**Moved:** `First` on page 1 by 206 pt

## `bz75154-163517`

**Differs:** pages 1 vs 2; placement visible {'displaced': 1}
**Moved:** `First` on page 1 by 205 pt

## `bz75154-163518`

**Differs:** pages 3 vs 2; shapes 4 vs 3
**Pages holding less text:** p2 (30 vs 6 words)

## `bz75208-157040`

**Differs:** pages 174 vs 172; images 175 vs 59; placement breaking {'displaced': 1107, 'outside': 6}
**Words Word has that Collabora does not:** `de`, `y`, `de`, `de`, `como`, `la`, `que`, `la`, `5`, `28`, `1`, `1`
**Pages holding less text:** p39 (324 vs 258 words), p111 (259 vs 148 words), p112 (161 vs 103 words)
**Moved:** `and` on page 17 by 31 pt
**Moved:** `as` on page 17 by 34 pt

## `bz75208-167513`

**Differs:** text 164 vs 119 tokens; placement visible {'displaced': 9}
**Words Word has that Collabora does not:** `de`, `de`, `de`, `cáncer`
**Pages holding less text:** p1 (164 vs 119 words)
**Moved:** `un` on page 1 by 145 pt
**Moved:** `mamografía` on page 1 by 304 pt

## `bz75208-167516`

**Differs:** text 110 vs 82 tokens; placement visible {'displaced': 15}
**Words Word has that Collabora does not:** `de`, `en`, `la`, `de`
**Pages holding less text:** p1 (110 vs 82 words)
**Moved:** `de` on page 1 by 125 pt
**Moved:** `Si` on page 1 by -58 pt

## `bz75208-94362`

**Differs:** pages 173 vs 170; images 221 vs 46; shapes 348 vs 16; placement breaking {'displaced': 817, 'outside': 6}
**Words Word has that Collabora does not:** `de`, `y`, `de`, `de`, `como`, `la`, `que`, `la`, `7`, `5`, `1`, `1`
**Pages holding less text:** p39 (324 vs 258 words), p101 (84 vs 26 words), p106 (254 vs 97 words)
**Moved:** `power.` on page 18 by -32 pt
**Moved:** `Neither` on page 18 by -37 pt

## `bz75281-136950`

**Differs:** text 23 vs 14 tokens
**Words Word has that Collabora does not:** `Počet`, `realizovaných`, `patentov`, `nových`
**Pages holding less text:** p1 (23 vs 14 words)

## `bz79920-100881`

**Differs:** images 2 vs 0; shapes 49 vs 27
**Words Word has that Collabora does not:** `ERD`, `Schema`, `customer_id`, `customer_id`

## `bz81736-103647`

**Differs:** text 157 vs 139 tokens; placement visible {'displaced': 9}
**Words Word has that Collabora does not:** `ISO`, `IEC`, `2014`, `All`, `ISO`, `IEC`, `1`, `2014`, `ISO`, `IEC`, `ISO`, `IEC`
**Pages holding less text:** p1 (36 vs 18 words)
**Moved:** `Open` on page 2 by 425 pt
**Moved:** `and` on page 2 by 247 pt

## `dk-tracked-changes-heavy-1`

**Differs:** placement visible {'displaced': 4}
**Moved:** `1inserted` on page 1 by 62 pt
**Moved:** `2inserted` on page 1 by 125 pt

## `dk-tracked-changes-heavy-2`

**Differs:** placement visible {'displaced': 4}
**Moved:** `1inserted` on page 1 by 62 pt
**Moved:** `2inserted` on page 1 by 125 pt

## `dk-tracked-changes-heavy-3`

**Differs:** placement visible {'displaced': 4}
**Moved:** `1inserted` on page 1 by 62 pt
**Moved:** `2inserted` on page 1 by 125 pt

## `hu-gov-9.11._Bet-tlap_tart-zkod-si_enged-ly_ir-nti_k-relemhez_-_Kutat-s_illetve_kutat-i_hossz-_t-v-_mobilit-s_HU`

**Differs:** pages 3 vs 4

## `hu-gov-9.13._Bet-tlap_tart-zkod-si_enged-ly_ir-nti_k-relemhez_-_Tanulm-nyok_folytat-sa_illetve_hallgat-i_mobilit-s_HU`

**Differs:** placement breaking {'outside': 1}
**Outside the margin:** `csa` on page 2 at x=584

## `hu-gov-9.16._Bet-tlap_tart-zkod-si_enged-ly_ir-nti_k-relemhez_-_Gyakornoki_tev-kenys-g_folytat-sa_HU`

**Differs:** placement breaking {'outside': 1}
**Outside the margin:** `csa` on page 1 at x=584

## `hu-gov-9.21._Appendix_to_an_application_for_a_residence_permit_-_Voluntary_service`

**Differs:** placement breaking {'outside': 1}
**Outside the margin:** `családt` on page 1 at x=566

## `hu-gov-9.21._Bet-tlap_tart-zkod-si_enged-ly_ir-nti_k-relemhez_-_-nk-ntes_tev-kenys-g_folytat-sa_HU`

**Differs:** placement breaking {'outside': 1}
**Outside the margin:** `családt` on page 1 at x=566

## `hu-gov-9.3._Bet-tlap_tart-zkod-si_enged-ly_ir-nti_k-relemhez_-_Vend-gbefektet-_HU`

**Differs:** pages 1 vs 2; placement visible {'displaced': 1}
**Moved:** `által` on page 1 by 213 pt

## `hu-gov-ENG_Tart-zkod-si_k-rtya_ki-ll-t-sa_meghosszabb-t-sa_3`

**Differs:** shapes 64 vs 48; placement visible {'displaced': 7}
**Words Word has that Collabora does not:** `Spouse`, `Domestic`
**Moved:** `_` on page 1 by 49 pt
**Moved:** `׀` on page 1 by 56 pt

## `hu-gov-tiokm-ny-ig-nyl-lap1`

**Words Word has that Collabora does not:** `______________________`
